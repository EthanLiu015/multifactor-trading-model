#include "position/PositionKeeper.hpp"

#include <cmath>

namespace engine::position {

void PositionKeeper::on_fill(const std::string& symbol, double qty, double price,
                              bool is_buy) {
    Position& pos = positions_[symbol];
    const double signed_fill = is_buy ? qty : -qty;

    if (pos.qty == 0.0) {
        pos.qty = signed_fill;
        pos.avg_price = price;
        return;
    }

    const bool same_direction = (pos.qty > 0.0) == (signed_fill > 0.0);
    if (same_direction) {
        const double new_qty = pos.qty + signed_fill;
        pos.avg_price =
            (pos.avg_price * std::abs(pos.qty) + price * qty) / std::abs(new_qty);
        pos.qty = new_qty;
        return;
    }

    // Opposite direction: close existing qty first, realizing P&L on the
    // closed portion; an overshoot flips to a new position on the other
    // side at the fill price.
    const double closing_qty = std::min(std::abs(pos.qty), qty);
    const double direction_sign = pos.qty > 0.0 ? 1.0 : -1.0;
    pos.realized_pnl += direction_sign * (price - pos.avg_price) * closing_qty;

    const double remaining_fill = qty - closing_qty;
    if (remaining_fill > 0.0) {
        pos.qty = signed_fill > 0.0 ? remaining_fill : -remaining_fill;
        pos.avg_price = price;
    } else {
        pos.qty += signed_fill;
    }
}

Position PositionKeeper::position(const std::string& symbol) const {
    auto it = positions_.find(symbol);
    return it != positions_.end() ? it->second : Position{};
}

const std::unordered_map<std::string, Position>& PositionKeeper::all_positions() const {
    return positions_;
}

}  // namespace engine::position
