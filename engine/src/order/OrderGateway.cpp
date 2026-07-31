#include "order/OrderGateway.hpp"

#include <stdexcept>

namespace engine::order {

namespace {
bool is_terminal(OrderState state) {
    return state == OrderState::Filled || state == OrderState::Cancelled ||
           state == OrderState::Rejected;
}
}  // namespace

OrderGateway::OrderGateway(broker::IBrokerGateway& broker) : broker_(broker) {}

broker::OrderId OrderGateway::submit_order(const broker::Order& order) {
    broker::OrderId id = broker_.submit_order(order);
    states_[id] = OrderState::New;
    return id;
}

void OrderGateway::cancel_order(broker::OrderId id) {
    (void)states_.at(id);  // validate known id before delegating to the broker
    broker_.cancel_order(id);
}

void OrderGateway::pump() {
    for (auto& event : broker_.poll_events()) {
        auto& state = states_.at(event.id);
        if (is_terminal(state)) {
            throw std::logic_error(
                "OrderGateway::pump: event on an order already in a terminal state");
        }
        switch (event.type) {
            case broker::EventType::Ack:
                state = OrderState::Acked;
                break;
            case broker::EventType::PartialFill:
                state = OrderState::PartiallyFilled;
                break;
            case broker::EventType::Fill:
                state = OrderState::Filled;
                break;
            case broker::EventType::Cancel:
                state = OrderState::Cancelled;
                break;
            case broker::EventType::Reject:
                state = OrderState::Rejected;
                break;
            case broker::EventType::New:
                break;  // never emitted by poll_events(); submit_order sets New directly
        }
    }
}

OrderState OrderGateway::state(broker::OrderId id) const {
    return states_.at(id);
}

}  // namespace engine::order
