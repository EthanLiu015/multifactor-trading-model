#include "execution/ExecutionScheduler.hpp"

#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>

#include <nlohmann/json.hpp>

namespace engine::execution {

ParsedTargetPortfolio parse_target_portfolio(const std::string& raw_json) {
    const auto parsed = nlohmann::json::parse(raw_json);

    ParsedTargetPortfolio result;
    result.status = parsed.value("status", std::string());
    for (const auto& p : parsed.at("positions")) {
        result.positions.push_back(
            {p.at("symbol").get<std::string>(), p.at("target_notional").get<double>()});
    }
    return result;
}

std::vector<broker::Order> compute_target_orders(
    const std::vector<TargetPosition>& targets, const position::PositionKeeper& positions,
    const marketdata::MarketDataHandler& market_data, double min_shares) {
    std::vector<broker::Order> orders;

    for (const auto& target : targets) {
        auto quote = market_data.latest_quote(target.symbol);
        if (!quote.has_value() || quote->bid_price <= 0.0 || quote->ask_price <= 0.0) {
            continue;  // no usable live price yet -- transient, not an error
        }
        const double mid_price = (quote->bid_price + quote->ask_price) / 2.0;

        const double target_shares = target.target_notional / mid_price;
        const double current_shares = positions.position(target.symbol).qty;
        const double delta = target_shares - current_shares;

        if (std::abs(delta) < min_shares) {
            continue;  // dust -- not worth trading
        }

        const bool is_buy = delta > 0.0;
        const double limit_price = is_buy ? quote->ask_price : quote->bid_price;
        orders.push_back(broker::Order{target.symbol, std::abs(delta), limit_price, is_buy});
    }

    return orders;
}

ExecutionScheduler::ExecutionScheduler(marketdata::MarketDataHandler& market_data,
                                        position::PositionKeeper& positions,
                                        risk::RiskChecker& risk_checker,
                                        broker::IBrokerGateway& broker)
    : market_data_(market_data),
      positions_(positions),
      risk_checker_(risk_checker),
      broker_(broker) {}

std::vector<broker::Order> ExecutionScheduler::run_once(const std::string& target_portfolio_path,
                                                         double buying_power) {
    std::ifstream file(target_portfolio_path);
    if (!file) {
        throw std::runtime_error("ExecutionScheduler: cannot open " + target_portfolio_path);
    }
    std::stringstream buffer;
    buffer << file.rdbuf();

    const auto parsed = parse_target_portfolio(buffer.str());
    if (parsed.status != "optimal") {
        return {};  // don't trade off infeasible/non-optimal weights
    }

    const auto candidates = compute_target_orders(parsed.positions, positions_, market_data_);

    std::vector<broker::Order> submitted;
    for (const auto& order : candidates) {
        const auto result = risk_checker_.check(order, order.limit_price, buying_power);
        if (result.passed) {
            broker_.submit_order(order);
            submitted.push_back(order);
        }
        // Rejected orders are simply not submitted, no throw -- matches
        // RiskChecker's own "surface, don't raise" posture.
    }
    return submitted;
}

}  // namespace engine::execution
