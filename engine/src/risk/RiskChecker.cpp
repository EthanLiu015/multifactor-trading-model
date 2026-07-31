#include "risk/RiskChecker.hpp"

#include <cmath>

namespace engine::risk {

RiskChecker::RiskChecker(position::PositionKeeper& positions, double max_order_notional,
                          double max_position_notional)
    : positions_(positions),
      max_order_notional_(max_order_notional),
      max_position_notional_(max_position_notional) {}

RiskResult RiskChecker::check(const broker::Order& order, double price,
                               double buying_power) const {
    const double order_notional = order.qty * price;
    if (order_notional > max_order_notional_) {
        return {false, "fat-finger: order notional exceeds max"};
    }

    const position::Position current = positions_.position(order.symbol);
    const double signed_order_qty = order.is_buy ? order.qty : -order.qty;
    const double resulting_qty = current.qty + signed_order_qty;
    if (std::abs(resulting_qty) * price > max_position_notional_) {
        return {false, "position limit: resulting position exceeds max"};
    }

    if (order.is_buy && order_notional > buying_power) {
        return {false, "insufficient buying power"};
    }

    return {true, ""};
}

}  // namespace engine::risk
