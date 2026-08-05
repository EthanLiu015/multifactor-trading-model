#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <fstream>

#include "broker/BrokerSimulator.hpp"
#include "execution/ExecutionScheduler.hpp"

using namespace engine::broker;
using namespace engine::position;
using namespace engine::marketdata;
using namespace engine::risk;
using namespace engine::execution;

namespace {
void set_quote(MarketDataHandler& handler, const std::string& symbol, double bid, double ask) {
    handler.on_message(
        R"([{"T":"q","S":")" + symbol + R"(","bp":)" + std::to_string(bid) + R"(,"bs":1,"ap":)" +
        std::to_string(ask) + R"(,"as":1,"t":"x"}])");
}
}  // namespace

TEST_CASE("parse_target_portfolio reads status and positions", "[execution_scheduler]") {
    auto parsed = parse_target_portfolio(
        R"({"rebuild_date":"2026-08-04","status":"optimal","positions":)"
        R"([{"symbol":"AAPL","target_notional":5000000.0}]})");

    REQUIRE(parsed.status == "optimal");
    REQUIRE(parsed.positions.size() == 1);
    REQUIRE(parsed.positions[0].symbol == "AAPL");
    REQUIRE(parsed.positions[0].target_notional == 5000000.0);
}

TEST_CASE("compute_target_orders skips a symbol with no live quote", "[execution_scheduler]") {
    PositionKeeper positions;
    MarketDataHandler market_data;  // no quote set for AAPL

    auto orders = compute_target_orders({{"AAPL", 1000.0}}, positions, market_data);

    REQUIRE(orders.empty());
}

TEST_CASE("compute_target_orders builds a buy order crossing the ask", "[execution_scheduler]") {
    PositionKeeper positions;  // flat
    MarketDataHandler market_data;
    set_quote(market_data, "AAPL", 99.0, 101.0);  // mid = 100

    auto orders = compute_target_orders({{"AAPL", 10000.0}}, positions, market_data);

    REQUIRE(orders.size() == 1);
    REQUIRE(orders[0].symbol == "AAPL");
    REQUIRE(orders[0].is_buy);
    REQUIRE(orders[0].qty == 100.0);          // 10000 / mid(100) = 100 shares
    REQUIRE(orders[0].limit_price == 101.0);  // crosses the ask
}

TEST_CASE("compute_target_orders builds a sell order crossing the bid", "[execution_scheduler]") {
    PositionKeeper positions;
    positions.on_fill("AAPL", 200, 100.0, true);  // already long 200
    MarketDataHandler market_data;
    set_quote(market_data, "AAPL", 99.0, 101.0);

    // target 100 shares' worth ($10,000 / mid 100 = 100 shares), currently 200 -> sell 100
    auto orders = compute_target_orders({{"AAPL", 10000.0}}, positions, market_data);

    REQUIRE(orders.size() == 1);
    REQUIRE_FALSE(orders[0].is_buy);
    REQUIRE(orders[0].qty == 100.0);
    REQUIRE(orders[0].limit_price == 99.0);  // crosses the bid
}

TEST_CASE("compute_target_orders skips a delta under the dust threshold", "[execution_scheduler]") {
    PositionKeeper positions;
    positions.on_fill("AAPL", 100, 100.0, true);  // already at target
    MarketDataHandler market_data;
    set_quote(market_data, "AAPL", 99.0, 101.0);

    auto orders = compute_target_orders({{"AAPL", 10000.0}}, positions, market_data, 1.0);

    REQUIRE(orders.empty());
}

TEST_CASE("ExecutionScheduler::run_once submits orders that pass risk checks",
          "[execution_scheduler]") {
    MarketDataHandler market_data;
    set_quote(market_data, "AAPL", 99.0, 101.0);
    PositionKeeper positions;
    RiskChecker risk_checker(positions, 1'000'000.0, 2'000'000.0);
    BrokerSimulator broker_sim;
    ExecutionScheduler scheduler(market_data, positions, risk_checker, broker_sim);

    const auto path = std::filesystem::temp_directory_path() / "mfts_test_target_portfolio.json";
    {
        std::ofstream file(path);
        file << R"({"status":"optimal","positions":[{"symbol":"AAPL","target_notional":10000.0}]})";
    }

    auto submitted = scheduler.run_once(path.string(), 1'000'000.0);
    std::filesystem::remove(path);

    REQUIRE(submitted.size() == 1);
    REQUIRE(submitted[0].symbol == "AAPL");
}

TEST_CASE("ExecutionScheduler::run_once submits nothing when status isn't optimal",
          "[execution_scheduler]") {
    MarketDataHandler market_data;
    set_quote(market_data, "AAPL", 99.0, 101.0);
    PositionKeeper positions;
    RiskChecker risk_checker(positions, 1'000'000.0, 2'000'000.0);
    BrokerSimulator broker_sim;
    ExecutionScheduler scheduler(market_data, positions, risk_checker, broker_sim);

    const auto path = std::filesystem::temp_directory_path() / "mfts_test_target_portfolio_infeasible.json";
    {
        std::ofstream file(path);
        file << R"({"status":"infeasible","positions":[{"symbol":"AAPL","target_notional":10000.0}]})";
    }

    auto submitted = scheduler.run_once(path.string(), 1'000'000.0);
    std::filesystem::remove(path);

    REQUIRE(submitted.empty());
}

TEST_CASE("ExecutionScheduler::run_once skips an order that fails risk checks",
          "[execution_scheduler]") {
    MarketDataHandler market_data;
    set_quote(market_data, "AAPL", 99.0, 101.0);
    PositionKeeper positions;
    RiskChecker risk_checker(positions, 1'000.0, 2'000.0);  // tiny bounds -- fat-finger will fire
    BrokerSimulator broker_sim;
    ExecutionScheduler scheduler(market_data, positions, risk_checker, broker_sim);

    const auto path = std::filesystem::temp_directory_path() / "mfts_test_target_portfolio_risky.json";
    {
        std::ofstream file(path);
        file << R"({"status":"optimal","positions":[{"symbol":"AAPL","target_notional":10000.0}]})";
    }

    auto submitted = scheduler.run_once(path.string(), 1'000'000.0);
    std::filesystem::remove(path);

    REQUIRE(submitted.empty());
}
