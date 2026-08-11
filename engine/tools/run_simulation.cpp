// One-off end-to-end verification: runs the real trading engine (risk +
// compliance checks, order submission, simulated fills, position keeping,
// reconciliation, kill switch) against a real optimizer solve
// (common/target_portfolio.json, written by
// research/portfolio/export_target.py) and real last-close prices (no
// live feed exists in this offline run, so quotes are seeded from real
// closes with a synthetic spread -- labeled as such in the output, never
// presented as live tick data). Not part of the automated test suite --
// a demonstration driver, same posture as smoke_alpaca_gateway.cpp. Run
// from the repo root:
//   engine/build/run_simulation <prices.json> [target_portfolio.json]

#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

#include "broker/BrokerSimulator.hpp"
#include "compliance/ComplianceChecker.hpp"
#include "execution/ExecutionScheduler.hpp"
#include "marketdata/MarketDataHandler.hpp"
#include "ops/KillSwitch.hpp"
#include "ops/Reconciliation.hpp"
#include "position/PositionKeeper.hpp"
#include "risk/RiskChecker.hpp"

using namespace engine;

namespace {

// Same wire shape AlpacaMarketDataStream feeds MarketDataHandler::on_message
// (see engine/tests/test_execution_scheduler.cpp's set_quote helper) -- a
// synthetic 5bps spread around a real last close, not a live tick.
void seed_quote(marketdata::MarketDataHandler& handler, const std::string& symbol,
                 double last_close) {
    const double bid = last_close * 0.9995;
    const double ask = last_close * 1.0005;
    handler.on_message("[{\"T\":\"q\",\"S\":\"" + symbol + "\",\"bp\":" + std::to_string(bid) +
                        ",\"bs\":1,\"ap\":" + std::to_string(ask) + ",\"as\":1,\"t\":\"x\"}]");
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::cerr << "usage: run_simulation <prices.json> [target_portfolio.json]\n";
        return 1;
    }
    const std::string prices_path = argv[1];
    const std::string target_path = argc > 2 ? argv[2] : "common/target_portfolio.json";

    std::ifstream prices_file(prices_path);
    if (!prices_file) {
        std::cerr << "cannot open " << prices_path << "\n";
        return 1;
    }
    std::stringstream prices_buf;
    prices_buf << prices_file.rdbuf();
    const auto prices = nlohmann::json::parse(prices_buf.str());

    marketdata::MarketDataHandler market_data;
    for (auto it = prices.begin(); it != prices.end(); ++it) {
        seed_quote(market_data, it.key(), it.value().get<double>());
    }

    // Fresh book -- this is a real first rebalance (w_prev=None on the
    // Python side), not a continuation of a prior simulated day.
    position::PositionKeeper positions;
    risk::RiskChecker risk_checker(positions, /*max_order_notional=*/1'000'000.0,
                                    /*max_position_notional=*/2'000'000.0);
    broker::BrokerSimulator broker_sim;
    ops::KillSwitch kill_switch;
    compliance::ComplianceChecker compliance_checker;
    execution::ExecutionScheduler scheduler(market_data, positions, risk_checker,
                                             compliance_checker, broker_sim, kill_switch,
                                             /*book_notional=*/10'000'000.0,
                                             /*max_drawdown_pct=*/0.05);

    const double buying_power = 10'000'000.0;
    auto submitted = scheduler.run_once(target_path, buying_power);

    // run_once() only returns what passed both checks. To report *why* the
    // rest didn't, re-derive candidates and re-check them against fresh
    // RiskChecker/ComplianceChecker instances (same limits) so this
    // diagnostic pass can't perturb the real compliance_checker's
    // duplicate-detection state used by the actual submitted-orders result
    // above.
    std::ifstream target_file(target_path);
    std::stringstream target_buf;
    target_buf << target_file.rdbuf();
    const auto parsed = execution::parse_target_portfolio(target_buf.str());
    const auto candidates =
        execution::compute_target_orders(parsed.positions, positions, market_data);

    risk::RiskChecker diag_risk(positions, 1'000'000.0, 2'000'000.0);
    compliance::ComplianceChecker diag_compliance;

    nlohmann::json orders_json = nlohmann::json::array();
    for (const auto& order : candidates) {
        const auto risk_result = diag_risk.check(order, order.limit_price, buying_power);
        const auto compliance_result = diag_compliance.check(order);
        const bool passed = risk_result.passed && compliance_result.passed;
        std::string reason;
        if (!risk_result.passed) reason = risk_result.reason;
        else if (!compliance_result.passed) reason = compliance_result.reason;

        orders_json.push_back({
            {"symbol", order.symbol},
            {"side", order.is_buy ? "BUY" : "SELL"},
            {"qty", order.qty},
            {"limit_price", order.limit_price},
            {"notional", order.qty * order.limit_price},
            {"status", passed ? "submitted" : "rejected"},
            {"reason", reason},
        });
    }

    // BrokerSimulator assigns OrderId sequentially from 1, and run_once()
    // is the only thing that has called submit_order on broker_sim so far
    // in this process -- so submitted[i] is OrderId (i+1). Simulate a full
    // fill at the limit price for each: v1's documented "single-shot
    // fill-likely default" (ExecutionScheduler.hpp), no fill-probability
    // model.
    for (std::size_t i = 0; i < submitted.size(); ++i) {
        const broker::OrderId id = static_cast<broker::OrderId>(i + 1);
        broker_sim.inject_ack(id);
        broker_sim.inject_fill(id, submitted[i].qty, submitted[i].limit_price);
    }
    nlohmann::json events_json = nlohmann::json::array();
    for (const auto& event : broker_sim.poll_events()) {
        events_json.push_back({{"id", event.id}, {"type", to_string(event.type)}});
        if (event.type == broker::EventType::Fill) {
            const auto& order =
                submitted[static_cast<std::size_t>(event.id) - 1];
            positions.on_fill(order.symbol, order.qty, order.limit_price, order.is_buy);
        }
    }

    const double book_value = execution::compute_book_value(positions, market_data);

    // BrokerSimulator carries no independent position record (see
    // IBrokerGateway.hpp's BrokerPosition comment) -- reconciling against
    // it is inherently a trivial/clean check here; a real divergence is
    // only possible against a live broker (AlpacaGateway::fetch_positions()).
    std::vector<broker::BrokerPosition> broker_positions;
    for (const auto& [symbol, pos] : positions.all_positions()) {
        broker_positions.push_back({symbol, pos.qty});
    }
    const auto recon = ops::reconcile_positions(positions, broker_positions);

    nlohmann::json out;
    out["rebuild_date"] = "2023-06-30";
    out["n_candidates"] = candidates.size();
    out["n_submitted"] = submitted.size();
    out["orders"] = orders_json;
    out["events"] = events_json;
    out["book_value"] = book_value;
    out["kill_switch_tripped"] = kill_switch.is_tripped();
    out["kill_switch_reason"] = kill_switch.reason();
    out["reconciliation_clean"] = recon.clean;
    out["reconciliation_break_count"] = recon.breaks.size();
    out["n_positions"] = positions.all_positions().size();

    std::cout << out.dump(2) << "\n";
    return 0;
}
