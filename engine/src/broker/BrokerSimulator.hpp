#pragma once

#include <deque>
#include <string>
#include <unordered_map>

#include "broker/IBrokerGateway.hpp"

namespace engine::journal {
class EventJournal;
}

namespace engine::broker {

enum class OrderStatus { New, Acked, PartiallyFilled, Filled, Cancelled, Rejected };

struct SimOrderState {
    Order order;
    OrderStatus status = OrderStatus::New;
    double qty_remaining = 0.0;
};

// Mock Alpaca API implementing IBrokerGateway. submit_order() only registers
// the order — nothing happens until a test scripts an event via inject_*.
// Every injected event is appended to journal (if provided) before being
// queued for poll_events(), so crash-recovery replay can be tested against
// simulated data without ever touching a live market (DESIGN.md Block 5).
class BrokerSimulator : public IBrokerGateway {
public:
    explicit BrokerSimulator(engine::journal::EventJournal* journal = nullptr);

    OrderId submit_order(const Order& order) override;
    void cancel_order(OrderId id) override;
    std::vector<OrderEvent> poll_events() override;

    // Test-scripting API — deliberately not part of IBrokerGateway; only the
    // simulator side can conjure broker behavior out of thin air.
    void inject_ack(OrderId id);
    void inject_fill(OrderId id, double qty, double price);
    void inject_reject(OrderId id, const std::string& reason);
    void inject_cancel_ack(OrderId id);

private:
    void enqueue(OrderEvent event);

    engine::journal::EventJournal* journal_;
    std::unordered_map<OrderId, SimOrderState> orders_;
    std::deque<OrderEvent> pending_events_;
    OrderId next_id_ = 1;
};

}  // namespace engine::broker
