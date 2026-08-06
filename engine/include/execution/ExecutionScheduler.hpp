#pragma once

#include <string>
#include <vector>

#include "broker/IBrokerGateway.hpp"
#include "compliance/ComplianceChecker.hpp"
#include "marketdata/MarketDataHandler.hpp"
#include "ops/KillSwitch.hpp"
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

// Book value = sum of realized P&L + mark-to-market unrealized P&L (live
// mid price from market_data) across every position. A symbol with no
// live quote yet still contributes its realized_pnl -- ignoring a whole
// position would understate drawdown, not a normal skip like
// compute_target_orders' no-quote case.
double compute_book_value(const position::PositionKeeper& positions,
                           const marketdata::MarketDataHandler& market_data);

// Orchestrates one full rebalance pass: check the kill switch, check book
// drawdown (auto-trips the kill switch on breach), read the target file,
// compute orders, risk-check + compliance-check each, submit the ones
// that pass both via the injected IBrokerGateway (BrokerSimulator for
// tests, AlpacaGateway live -- same injection convention as everywhere
// else in this codebase). Does nothing if the kill switch is tripped, or
// if the file's status isn't "optimal" -- trading off infeasible/
// non-optimal weights is a real risk, not routine.
class ExecutionScheduler {
public:
    ExecutionScheduler(marketdata::MarketDataHandler& market_data,
                        position::PositionKeeper& positions, risk::RiskChecker& risk_checker,
                        compliance::ComplianceChecker& compliance_checker,
                        broker::IBrokerGateway& broker, ops::KillSwitch& kill_switch,
                        double book_notional = 10'000'000.0, double max_drawdown_pct = 0.05);

    // Returns the orders actually submitted (those that passed both risk
    // and compliance checks) -- callers/tests can inspect what happened
    // without a live broker connection. Empty if the kill switch was
    // already tripped, just tripped by this call's drawdown check, or
    // the file's status isn't "optimal". Calls compliance_checker.reset()
    // at the start of every call -- duplicate-order detection is scoped
    // to one run_once() batch, never across separate calls/days.
    std::vector<broker::Order> run_once(const std::string& target_portfolio_path,
                                         double buying_power);

private:
    marketdata::MarketDataHandler& market_data_;
    position::PositionKeeper& positions_;
    risk::RiskChecker& risk_checker_;
    compliance::ComplianceChecker& compliance_checker_;
    broker::IBrokerGateway& broker_;
    ops::KillSwitch& kill_switch_;
    double book_notional_;
    double max_drawdown_pct_;
    double high_water_mark_ = 0.0;  // cumulative book P&L starts at 0 for a fresh book
};

}  // namespace engine::execution
