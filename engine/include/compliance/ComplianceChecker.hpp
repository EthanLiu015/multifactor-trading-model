#pragma once

#include <string>
#include <unordered_map>
#include <unordered_set>

#include "broker/IBrokerGateway.hpp"

namespace engine::compliance {

struct ComplianceResult {
    bool passed = true;
    std::string reason;
};

// Pre-trade compliance checks (DESIGN.md ops layer: "restricted-list, max
// order size, duplicate-order suppression" -- explicitly named as checks
// "beyond fat-finger/risk", a distinct concern from RiskChecker's
// financial-risk sizing: fat-finger notional, position limits, buying
// power). Checked in order: restricted-list -> max order size ->
// duplicate-order suppression.
//
// Duplicate detection is scoped to one BATCH (e.g. one
// ExecutionScheduler::run_once() call), not this object's whole lifetime
// -- reset() must be called at the start of each batch, or a legitimate
// trade recurring on a later day would be flagged as a duplicate of
// itself (Ethan's call, 2026-08-06).
class ComplianceChecker {
public:
    explicit ComplianceChecker(std::unordered_set<std::string> restricted_symbols = {},
                                double max_order_shares = 100'000.0);

    ComplianceResult check(const broker::Order& order);

    // Clears duplicate-detection state for a new batch. Restricted-list
    // and max_order_shares are unaffected -- those are standing rules,
    // not per-batch state.
    void reset();

private:
    std::unordered_set<std::string> restricted_symbols_;
    double max_order_shares_;
    std::unordered_map<std::string, broker::Order> seen_this_batch_;
};

}  // namespace engine::compliance
