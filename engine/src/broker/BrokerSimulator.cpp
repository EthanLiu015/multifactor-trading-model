#include "broker/BrokerSimulator.hpp"

#include <stdexcept>
#include <utility>

#include "journal/EventJournal.hpp"

namespace engine::broker {

namespace {
OrderEvent make_event(OrderId id, EventType type, double qty, double price,
                       std::string reason = "") {
    return OrderEvent{id, type, qty, price, std::chrono::system_clock::now(),
                       std::move(reason)};
}
}  // namespace

BrokerSimulator::BrokerSimulator(engine::journal::EventJournal* journal)
    : journal_(journal) {}

OrderId BrokerSimulator::submit_order(const Order& order) {
    OrderId id = next_id_++;
    orders_[id] = SimOrderState{order, OrderStatus::New, order.qty};
    return id;
}

void BrokerSimulator::cancel_order(OrderId id) {
    // throws std::out_of_range if unknown — validation only; real
    // pending-cancel state is scoped with the order gateway, not here.
    // Use inject_cancel_ack() to surface the actual Cancel event.
    (void)orders_.at(id);
}

std::vector<OrderEvent> BrokerSimulator::poll_events() {
    std::vector<OrderEvent> out(pending_events_.begin(), pending_events_.end());
    pending_events_.clear();
    return out;
}

void BrokerSimulator::inject_ack(OrderId id) {
    auto& state = orders_.at(id);
    state.status = OrderStatus::Acked;
    enqueue(make_event(id, EventType::Ack, 0.0, 0.0));
}

void BrokerSimulator::inject_fill(OrderId id, double qty, double price) {
    auto& state = orders_.at(id);
    const double limit = state.order.limit_price;
    if (limit != 0.0) {  // 0 = market order, no price constraint
        const bool violates_limit =
            state.order.is_buy ? (price > limit) : (price < limit);
        if (violates_limit) {
            throw std::invalid_argument(
                "inject_fill: price violates order limit_price");
        }
    }
    if (qty >= state.qty_remaining) {
        state.qty_remaining = 0.0;
        state.status = OrderStatus::Filled;
        enqueue(make_event(id, EventType::Fill, qty, price));
    } else {
        state.qty_remaining -= qty;
        state.status = OrderStatus::PartiallyFilled;
        enqueue(make_event(id, EventType::PartialFill, qty, price));
    }
}

void BrokerSimulator::inject_reject(OrderId id, const std::string& reason) {
    auto& state = orders_.at(id);
    state.status = OrderStatus::Rejected;
    enqueue(make_event(id, EventType::Reject, 0.0, 0.0, reason));
}

void BrokerSimulator::inject_cancel_ack(OrderId id) {
    auto& state = orders_.at(id);
    state.status = OrderStatus::Cancelled;
    enqueue(make_event(id, EventType::Cancel, 0.0, 0.0));
}

void BrokerSimulator::enqueue(OrderEvent event) {
    if (journal_ != nullptr) {
        journal_->append(event);
    }
    pending_events_.push_back(std::move(event));
}

}  // namespace engine::broker
