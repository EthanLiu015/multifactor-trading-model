#include <catch2/catch_test_macros.hpp>

#include "broker/BrokerSimulator.hpp"
#include "order/OrderGateway.hpp"

using namespace engine::broker;
using namespace engine::order;

TEST_CASE("submit_order starts in state New", "[order_gateway]") {
    BrokerSimulator sim;
    OrderGateway gw(sim);
    Order order{"AAPL", 100, 0.0, true};

    OrderId id = gw.submit_order(order);

    REQUIRE(gw.state(id) == OrderState::New);
}

TEST_CASE("pump applies an Ack event", "[order_gateway]") {
    BrokerSimulator sim;
    OrderGateway gw(sim);
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = gw.submit_order(order);

    sim.inject_ack(id);
    gw.pump();

    REQUIRE(gw.state(id) == OrderState::Acked);
}

TEST_CASE("out-of-order fill before ack still reaches Filled", "[order_gateway]") {
    // Same stress case BrokerSimulator's own tests cover: the gateway must
    // not require Acked status before accepting a fill.
    BrokerSimulator sim;
    OrderGateway gw(sim);
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = gw.submit_order(order);

    sim.inject_fill(id, 100, 150.25);
    gw.pump();

    REQUIRE(gw.state(id) == OrderState::Filled);
}

TEST_CASE("partial fill then fill moves through PartiallyFilled", "[order_gateway]") {
    BrokerSimulator sim;
    OrderGateway gw(sim);
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = gw.submit_order(order);

    sim.inject_fill(id, 40, 150.0);
    gw.pump();
    REQUIRE(gw.state(id) == OrderState::PartiallyFilled);

    sim.inject_fill(id, 60, 150.5);
    gw.pump();
    REQUIRE(gw.state(id) == OrderState::Filled);
}

TEST_CASE("reject moves the order to Rejected", "[order_gateway]") {
    BrokerSimulator sim;
    OrderGateway gw(sim);
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = gw.submit_order(order);

    sim.inject_reject(id, "insufficient buying power");
    gw.pump();

    REQUIRE(gw.state(id) == OrderState::Rejected);
}

TEST_CASE("cancel ack moves the order to Cancelled", "[order_gateway]") {
    BrokerSimulator sim;
    OrderGateway gw(sim);
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = gw.submit_order(order);

    sim.inject_cancel_ack(id);
    gw.pump();

    REQUIRE(gw.state(id) == OrderState::Cancelled);
}

TEST_CASE("an event on an already-terminal order throws", "[order_gateway]") {
    BrokerSimulator sim;
    OrderGateway gw(sim);
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = gw.submit_order(order);

    sim.inject_fill(id, 100, 150.0);
    gw.pump();
    REQUIRE(gw.state(id) == OrderState::Filled);

    sim.inject_ack(id);  // broker-side misuse: order is already terminal
    REQUIRE_THROWS_AS(gw.pump(), std::logic_error);
}

TEST_CASE("state on an unknown id throws", "[order_gateway]") {
    BrokerSimulator sim;
    OrderGateway gw(sim);
    REQUIRE_THROWS_AS(gw.state(999), std::out_of_range);
}

TEST_CASE("cancel_order on an unknown id throws", "[order_gateway]") {
    BrokerSimulator sim;
    OrderGateway gw(sim);
    REQUIRE_THROWS_AS(gw.cancel_order(999), std::out_of_range);
}
