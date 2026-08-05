#include <catch2/catch_test_macros.hpp>

#include "broker/AlpacaGateway.hpp"

using namespace engine::broker;

TEST_CASE("a fill event maps to EventType::Fill with parsed qty/price",
          "[alpaca_gateway]") {
    auto event = parse_trade_update(
        R"({"stream":"trade_updates","data":{"event":"fill",)"
        R"("order":{"id":"abc-123","client_order_id":"42","symbol":"AAPL"},)"
        R"("qty":"100","price":"150.25"}})");

    REQUIRE(event.has_value());
    REQUIRE(event->id == 42);
    REQUIRE(event->type == EventType::Fill);
    REQUIRE(event->qty == 100.0);
    REQUIRE(event->price == 150.25);
}

TEST_CASE("a partial_fill event maps to EventType::PartialFill", "[alpaca_gateway]") {
    auto event = parse_trade_update(
        R"({"stream":"trade_updates","data":{"event":"partial_fill",)"
        R"("order":{"id":"abc-123","client_order_id":"7"},"qty":"40","price":"150.0"}})");

    REQUIRE(event.has_value());
    REQUIRE(event->type == EventType::PartialFill);
}

TEST_CASE("a new event maps to EventType::Ack with zero qty/price", "[alpaca_gateway]") {
    auto event = parse_trade_update(
        R"({"stream":"trade_updates","data":{"event":"new",)"
        R"("order":{"id":"abc-123","client_order_id":"1"},"qty":null,"price":null}})");

    REQUIRE(event.has_value());
    REQUIRE(event->type == EventType::Ack);
    REQUIRE(event->qty == 0.0);
    REQUIRE(event->price == 0.0);
}

TEST_CASE("an accepted event also maps to EventType::Ack", "[alpaca_gateway]") {
    // Alpaca's paper-trading environment sends "accepted" as the initial
    // acknowledgment rather than "new" -- confirmed live 2026-08-04.
    auto event = parse_trade_update(
        R"({"stream":"trade_updates","data":{"event":"accepted",)"
        R"("order":{"id":"abc-123","client_order_id":"1"},"qty":null,"price":null}})");

    REQUIRE(event.has_value());
    REQUIRE(event->type == EventType::Ack);
}

TEST_CASE("canceled and expired events both map to EventType::Cancel", "[alpaca_gateway]") {
    auto canceled = parse_trade_update(
        R"({"stream":"trade_updates","data":{"event":"canceled",)"
        R"("order":{"id":"a","client_order_id":"1"}}})");
    auto expired = parse_trade_update(
        R"({"stream":"trade_updates","data":{"event":"expired",)"
        R"("order":{"id":"a","client_order_id":"2"}}})");

    REQUIRE(canceled.has_value());
    REQUIRE(canceled->type == EventType::Cancel);
    REQUIRE(expired.has_value());
    REQUIRE(expired->type == EventType::Cancel);
}

TEST_CASE("a rejected event maps to EventType::Reject", "[alpaca_gateway]") {
    auto event = parse_trade_update(
        R"({"stream":"trade_updates","data":{"event":"rejected",)"
        R"("order":{"id":"a","client_order_id":"1"}}})");

    REQUIRE(event.has_value());
    REQUIRE(event->type == EventType::Reject);
}

TEST_CASE("an untracked event type is skipped", "[alpaca_gateway]") {
    auto event = parse_trade_update(
        R"({"stream":"trade_updates","data":{"event":"pending_new",)"
        R"("order":{"id":"a","client_order_id":"1"}}})");

    REQUIRE_FALSE(event.has_value());
}

TEST_CASE("a non-trade_updates stream message is skipped", "[alpaca_gateway]") {
    auto event = parse_trade_update(R"({"stream":"listening","data":{"streams":["trade_updates"]}})");

    REQUIRE_FALSE(event.has_value());
}

TEST_CASE("a client_order_id this gateway didn't assign is skipped", "[alpaca_gateway]") {
    auto event = parse_trade_update(
        R"({"stream":"trade_updates","data":{"event":"fill",)"
        R"("order":{"id":"a","client_order_id":"not-a-number"},"qty":"1","price":"1"}})");

    REQUIRE_FALSE(event.has_value());
}
