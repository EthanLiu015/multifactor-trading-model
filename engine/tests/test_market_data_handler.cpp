#include <catch2/catch_test_macros.hpp>

#include "marketdata/MarketDataHandler.hpp"

using namespace engine::marketdata;

TEST_CASE("an untraded symbol has no trade or quote", "[market_data_handler]") {
    MarketDataHandler handler;

    REQUIRE_FALSE(handler.latest_trade("AAPL").has_value());
    REQUIRE_FALSE(handler.latest_quote("AAPL").has_value());
}

TEST_CASE("a trade message updates the latest trade", "[market_data_handler]") {
    MarketDataHandler handler;

    handler.on_message(
        R"([{"T":"t","S":"AAPL","i":123,"x":"V","p":150.25,"s":100,)"
        R"("c":["@"],"z":"C","t":"2026-08-02T14:30:00.123456789Z"}])");

    auto trade = handler.latest_trade("AAPL");
    REQUIRE(trade.has_value());
    REQUIRE(trade->price == 150.25);
    REQUIRE(trade->size == 100.0);
    REQUIRE(trade->timestamp == "2026-08-02T14:30:00.123456789Z");
}

TEST_CASE("a quote message updates the latest quote", "[market_data_handler]") {
    MarketDataHandler handler;

    handler.on_message(
        R"([{"T":"q","S":"AAPL","bx":"V","bp":150.20,"bs":2,)"
        R"("ax":"V","ap":150.30,"as":3,"c":["R"],"z":"C",)"
        R"("t":"2026-08-02T14:30:00.000000000Z"}])");

    auto quote = handler.latest_quote("AAPL");
    REQUIRE(quote.has_value());
    REQUIRE(quote->bid_price == 150.20);
    REQUIRE(quote->bid_size == 2.0);
    REQUIRE(quote->ask_price == 150.30);
    REQUIRE(quote->ask_size == 3.0);
}

TEST_CASE("a batch can carry multiple symbols and message types", "[market_data_handler]") {
    MarketDataHandler handler;

    handler.on_message(
        R"([{"T":"t","S":"AAPL","p":150.25,"s":100,"t":"x"},)"
        R"({"T":"t","S":"MSFT","p":300.00,"s":50,"t":"x"},)"
        R"({"T":"q","S":"AAPL","bp":150.20,"bs":2,"ap":150.30,"as":3,"t":"x"}])");

    REQUIRE(handler.latest_trade("AAPL")->price == 150.25);
    REQUIRE(handler.latest_trade("MSFT")->price == 300.00);
    REQUIRE(handler.latest_quote("AAPL")->ask_price == 150.30);
}

TEST_CASE("an unrecognized message type is skipped, not an error", "[market_data_handler]") {
    MarketDataHandler handler;

    handler.on_message(R"([{"T":"success","msg":"authenticated"}])");

    REQUIRE_FALSE(handler.latest_trade("AAPL").has_value());
}

TEST_CASE("a later trade for the same symbol overwrites the earlier one",
          "[market_data_handler]") {
    MarketDataHandler handler;

    handler.on_message(R"([{"T":"t","S":"AAPL","p":150.00,"s":100,"t":"x"}])");
    handler.on_message(R"([{"T":"t","S":"AAPL","p":151.00,"s":50,"t":"y"}])");

    REQUIRE(handler.latest_trade("AAPL")->price == 151.00);
}

TEST_CASE("malformed JSON throws instead of failing silently", "[market_data_handler]") {
    MarketDataHandler handler;

    REQUIRE_THROWS(handler.on_message("not json"));
}
