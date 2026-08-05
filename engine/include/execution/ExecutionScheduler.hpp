#pragma once

#include <string>
#include <vector>

#include "broker/IBrokerGateway.hpp"
#include "marketdata/MarketDataHandler.hpp"
#include "position/PositionKeeper.hpp"
#include "risk/RiskChecker.hpp"

namespace engine::execution {

struct TargetPosition {
    std::string symbol;
    double target_notional;
};

struct ParsedTargetPortfolio {
    std::string status;
    std::vector<TargetPosition> positions;
};

// Parses a target-portfolio JSON payload (written by
// research/portfolio/export_target.py: {"status": ..., "positions":
// [{"symbol": ..., "target_notional": ...}, ...]}). Pure, offline-testable
// -- no file I/O here, that's ExecutionScheduler::run_once's job.
ParsedTargetPortfolio parse_target_portfolio(const std::string& raw_json);

// Builds one Order per symbol whose target/current share delta exceeds
// min_shares (a dust filter -- fractional-share deltas from
// notional/price rounding aren't worth trading). Prices come from
// market_data's live quotes, not looked up any other way -- symbols with
// no quote yet are skipped (a normal transient state, not an error).
// Order.limit_price crosses the spread (ask for buys, bid for sells) --
// v1's single-shot fill-likely default; order slicing (TWAP/VWAP) and
// alpha-decay-driven urgency (DESIGN.md's "limit vs market" choice) are
// deliberately deferred, not built.
std::vector<broker::Order> compute_target_orders(
    const std::vector<TargetPosition>& targets, const position::PositionKeeper& positions,
    const marketdata::MarketDataHandler& market_data, double min_shares = 1.0);

// Orchestrates one full rebalance pass: read the target file, compute
// orders, risk-check each, submit the ones that pass via the injected
// IBrokerGateway (BrokerSimulator for tests, AlpacaGateway live -- same
// injection convention as everywhere else in this codebase). Does
// nothing if the file's status isn't "optimal" -- trading off
// infeasible/non-optimal weights is a real risk, not routine.
class ExecutionScheduler {
public:
    ExecutionScheduler(marketdata::MarketDataHandler& market_data,
                        position::PositionKeeper& positions, risk::RiskChecker& risk_checker,
                        broker::IBrokerGateway& broker);

    // Returns the orders actually submitted (those that passed risk
    // checks) -- callers/tests can inspect what happened without a live
    // broker connection.
    std::vector<broker::Order> run_once(const std::string& target_portfolio_path,
                                         double buying_power);

private:
    marketdata::MarketDataHandler& market_data_;
    position::PositionKeeper& positions_;
    risk::RiskChecker& risk_checker_;
    broker::IBrokerGateway& broker_;
};

}  // namespace engine::execution
