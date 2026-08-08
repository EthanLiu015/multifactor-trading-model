#pragma once

#include <string>
#include <vector>

#include "broker/IBrokerGateway.hpp"
#include "position/PositionKeeper.hpp"

namespace engine::ops {

struct ReconciliationBreak {
    std::string symbol;
    double local_qty;
    double broker_qty;  // 0.0 if the broker has no position for this symbol at all
};

struct ReconciliationResult {
    bool clean = true;
    std::vector<ReconciliationBreak> breaks;
};

// Compares PositionKeeper's local book against the broker's reported
// positions (DESIGN.md ops layer: "positions + cash vs broker records
// every day; any break halts trading until explained"). Checks both
// directions: a symbol the local book holds but the broker doesn't report
// (or reports a different qty for), and a symbol the broker reports that
// the local book doesn't know about at all.
//
// Pure comparison -- doesn't itself trip the KillSwitch. That's a policy
// decision left to whatever calls this (e.g. a daily reconciliation
// script), keeping this testable without a live broker connection.
// broker::AlpacaGateway::fetch_positions() is the live source for
// broker_positions; not called from here.
//
// Scoped to positions only -- cash reconciliation (DESIGN.md's other half
// of this bullet) needs a cash-tracking concept this codebase doesn't
// have yet (PositionKeeper only tracks share positions/P&L), a
// documented gap, not silently dropped.
ReconciliationResult reconcile_positions(const position::PositionKeeper& local,
                                          const std::vector<broker::BrokerPosition>& broker_positions,
                                          double tolerance = 1e-6);

}  // namespace engine::ops
