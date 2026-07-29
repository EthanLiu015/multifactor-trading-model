#include <catch2/catch_test_macros.hpp>

#include "broker/BrokerSimulator.hpp"

using namespace engine::broker;

TEST_CASE("submit then ack surfaces exactly one Ack event", "[broker_simulator]") {
    BrokerSimulator sim;
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = sim.submit_order(order);

    sim.inject_ack(id);
    auto events = sim.poll_events();

    REQUIRE(events.size() == 1);
    REQUIRE(events[0].id == id);
    REQUIRE(events[0].type == EventType::Ack);
}

TEST_CASE("out-of-order fill before ack still queues correctly", "[broker_simulator]") {
    // Deliberate stress case DESIGN.md Block 5 calls for: a fill arriving
    // before any ack. The simulator must not require Acked status first.
    BrokerSimulator sim;
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = sim.submit_order(order);

    sim.inject_fill(id, 100, 150.25);
    auto events = sim.poll_events();

    REQUIRE(events.size() == 1);
    REQUIRE(events[0].type == EventType::Fill);
    REQUIRE(events[0].qty == 100);
    REQUIRE(events[0].price == 150.25);
}

TEST_CASE("partial fill leaves the order open for a second fill", "[broker_simulator]") {
    BrokerSimulator sim;
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = sim.submit_order(order);

    sim.inject_fill(id, 40, 150.0);
    sim.inject_fill(id, 60, 150.5);
    auto events = sim.poll_events();

    REQUIRE(events.size() == 2);
    REQUIRE(events[0].type == EventType::PartialFill);
    REQUIRE(events[1].type == EventType::Fill);
}

TEST_CASE("reject carries its reason", "[broker_simulator]") {
    BrokerSimulator sim;
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = sim.submit_order(order);

    sim.inject_reject(id, "insufficient buying power");
    auto events = sim.poll_events();

    REQUIRE(events.size() == 1);
    REQUIRE(events[0].type == EventType::Reject);
    REQUIRE(events[0].reason == "insufficient buying power");
}

TEST_CASE("poll_events drains the queue", "[broker_simulator]") {
    BrokerSimulator sim;
    Order order{"AAPL", 100, 0.0, true};
    OrderId id = sim.submit_order(order);
    sim.inject_ack(id);

    REQUIRE(sim.poll_events().size() == 1);
    REQUIRE(sim.poll_events().empty());
}

TEST_CASE("cancel_order on an unknown id throws", "[broker_simulator]") {
    BrokerSimulator sim;
    REQUIRE_THROWS_AS(sim.cancel_order(999), std::out_of_range);
}

TEST_CASE("inject_fill above a buy limit throws", "[broker_simulator]") {
    BrokerSimulator sim;
    Order order{"AAPL", 100, 150.0, true};
    OrderId id = sim.submit_order(order);

    REQUIRE_THROWS_AS(sim.inject_fill(id, 100, 150.01), std::invalid_argument);
}

TEST_CASE("inject_fill below a sell limit throws", "[broker_simulator]") {
    BrokerSimulator sim;
    Order order{"AAPL", 100, 150.0, false};
    OrderId id = sim.submit_order(order);

    REQUIRE_THROWS_AS(sim.inject_fill(id, 100, 149.99), std::invalid_argument);
}

TEST_CASE("inject_fill exactly at the limit price is legal", "[broker_simulator]") {
    BrokerSimulator sim;
    Order order{"AAPL", 100, 150.0, true};
    OrderId id = sim.submit_order(order);

    sim.inject_fill(id, 100, 150.0);
    auto events = sim.poll_events();

    REQUIRE(events.size() == 1);
    REQUIRE(events[0].type == EventType::Fill);
}
