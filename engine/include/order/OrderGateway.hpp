#pragma once

#include <unordered_map>

#include "broker/IBrokerGateway.hpp"
#include "broker/OrderEvent.hpp"

namespace engine::order {

enum class OrderState { New, Acked, PartiallyFilled, Filled, Cancelled, Rejected };

// Broker-agnostic order state machine (DESIGN.md Block 5: "order gateway
// ... new/ack/fill/cancel/reject"). Wraps any IBrokerGateway (BrokerSimulator
// today, a future live AlpacaGateway later) so downstream code (position
// keeper, risk checks) sees one canonical order lifecycle regardless of
// which broker is behind it -- BrokerSimulator's own SimOrderState is
// private bookkeeping for the mock only, not this.
class OrderGateway {
public:
    explicit OrderGateway(broker::IBrokerGateway& broker);

    broker::OrderId submit_order(const broker::Order& order);
    void cancel_order(broker::OrderId id);

    // Drains the broker's poll_events() and applies each event to
    // gateway-owned state. An event on an order already in a terminal state
    // (Filled/Cancelled/Rejected) is a broken invariant, not routine input --
    // throws std::logic_error rather than silently reapplying it.
    void pump();

    OrderState state(broker::OrderId id) const;

private:
    broker::IBrokerGateway& broker_;
    std::unordered_map<broker::OrderId, OrderState> states_;
};

}  // namespace engine::order
