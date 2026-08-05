#pragma once

#include <string>
#include <unordered_map>

namespace engine::position {

// Signed qty: positive = long, negative = short. avg_price is the cost
// basis of the currently-open qty; meaningless when qty == 0.
struct Position {
    double qty = 0.0;
    double avg_price = 0.0;
    double realized_pnl = 0.0;
};

// Average-cost position/P&L tracker, built from fills (DESIGN.md Block 5's
// position keeper). Queried directly by ExecutionScheduler for per-symbol
// current position; not yet fed by OrderGateway.pump()'s output specifically
// (that wiring gap is separate from execution scheduling).
class PositionKeeper {
public:
    // A fill same-direction as the existing position grows it and
    // re-averages cost. A fill opposite the existing position closes open
    // qty first (realizing P&L on the closed portion) and, if it overshoots
    // past zero, flips to a new position on the other side at `price`.
    void on_fill(const std::string& symbol, double qty, double price, bool is_buy);

    // A symbol with no fills yet is a normal, expected state (never traded
    // it) -- returns a default flat Position{}, not a throw.
    Position position(const std::string& symbol) const;

    // Every symbol with a non-default Position, for book-level aggregation
    // (e.g. the ops layer's drawdown check needs every position's
    // realized P&L + live mark-to-market, not one symbol at a time).
    const std::unordered_map<std::string, Position>& all_positions() const;

private:
    std::unordered_map<std::string, Position> positions_;
};

}  // namespace engine::position
