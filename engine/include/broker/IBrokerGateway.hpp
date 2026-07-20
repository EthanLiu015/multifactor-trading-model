#pragma once

#include <string>
#include <vector>

#include "broker/OrderEvent.hpp"

namespace engine::broker {

struct Order {
    std::string symbol;
    double qty;
    double limit_price = 0.0;  // 0 = market order
    bool is_buy;
};

// Implemented by both the live Alpaca gateway (Block 5, scoped later) and
// BrokerSimulator (this skeleton) — order-gateway code calls this interface
// and never knows which one is behind it. Production callers poll this in a
// pinned, busy-spin thread over a lock-free queue (DESIGN.md Block 5
// latency discipline); BrokerSimulator never runs on the hot path so a
// plain queue is fine there.
class IBrokerGateway {
public:
    virtual ~IBrokerGateway() = default;
    virtual OrderId submit_order(const Order& order) = 0;
    virtual void cancel_order(OrderId id) = 0;
    virtual std::vector<OrderEvent> poll_events() = 0;
};

}  // namespace engine::broker
