#pragma once

#include <string>

#include "broker/IBrokerGateway.hpp"
#include "position/PositionKeeper.hpp"

namespace engine::risk {

struct RiskResult {
    bool passed = true;
    std::string reason;  // empty when passed
};

// Pre-trade risk checks (DESIGN.md Block 5: "fat-finger, position limits,
// buying power"), run before an order reaches the broker. A failing check
// is routine, expected control flow -- returned as a RiskResult, not
// thrown, matching research/portfolio/model.py's TargetPortfolio.status
// precedent ("surface the fact, don't raise").
//
// No market data handler exists yet, so a reference `price` is passed in
// per-call rather than looked up internally -- same convention the Python
// research side uses (price/ADV always supplied externally, never invented).
// `max_order_notional`/`max_position_notional` are placeholder constants,
// same posture as this codebase's other uncalibrated defaults (e.g.
// research/portfolio/solve.py's risk_aversion=5.0) -- no backtester exists
// yet for this side of the system to calibrate against.
class RiskChecker {
public:
    explicit RiskChecker(position::PositionKeeper& positions,
                          double max_order_notional = 1'000'000.0,
                          double max_position_notional = 2'000'000.0);

    // Checked in order: fat-finger, then position limit, then buying power.
    // Returns the first failure; passing every check returns {true, ""}.
    RiskResult check(const broker::Order& order, double price, double buying_power) const;

private:
    position::PositionKeeper& positions_;
    double max_order_notional_;
    double max_position_notional_;
};

}  // namespace engine::risk
