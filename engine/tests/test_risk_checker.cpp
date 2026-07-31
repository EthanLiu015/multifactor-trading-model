#include <catch2/catch_test_macros.hpp>

#include "position/PositionKeeper.hpp"
#include "risk/RiskChecker.hpp"

using namespace engine::broker;
using namespace engine::position;
using namespace engine::risk;

namespace {
// Small deterministic bounds for the whole file: max_order_notional=10,000,
// max_position_notional=20,000.
RiskChecker make_checker(PositionKeeper& positions) {
    return RiskChecker(positions, 10'000.0, 20'000.0);
}
}  // namespace

TEST_CASE("an order under every limit passes", "[risk_checker]") {
    PositionKeeper positions;
    RiskChecker checker = make_checker(positions);
    Order order{"AAPL", 10, 0.0, true};

    RiskResult result = checker.check(order, 100.0, 5000.0);

    REQUIRE(result.passed);
    REQUIRE(result.reason.empty());
}

TEST_CASE("fat-finger: order notional over the max is rejected", "[risk_checker]") {
    PositionKeeper positions;
    RiskChecker checker = make_checker(positions);
    Order order{"AAPL", 200, 0.0, true};  // 200 * 100 = 20,000 > 10,000

    RiskResult result = checker.check(order, 100.0, 100'000.0);

    REQUIRE_FALSE(result.passed);
    REQUIRE(result.reason == "fat-finger: order notional exceeds max");
}

TEST_CASE("position limit: resulting position over the max is rejected", "[risk_checker]") {
    PositionKeeper positions;
    positions.on_fill("AAPL", 190, 100.0, true);  // existing position: 19,000 notional
    RiskChecker checker = make_checker(positions);
    Order order{"AAPL", 20, 0.0, true};  // adds 2,000 -> resulting 21,000 > 20,000

    RiskResult result = checker.check(order, 100.0, 100'000.0);

    REQUIRE_FALSE(result.passed);
    REQUIRE(result.reason == "position limit: resulting position exceeds max");
}

TEST_CASE("buying power: a buy exceeding available cash is rejected", "[risk_checker]") {
    PositionKeeper positions;
    RiskChecker checker = make_checker(positions);
    Order order{"AAPL", 60, 0.0, true};  // 6,000 notional

    RiskResult result = checker.check(order, 100.0, 5000.0);

    REQUIRE_FALSE(result.passed);
    REQUIRE(result.reason == "insufficient buying power");
}

TEST_CASE("a sell is not constrained by buying power", "[risk_checker]") {
    PositionKeeper positions;
    RiskChecker checker = make_checker(positions);
    Order order{"AAPL", 60, 0.0, false};  // 6,000 notional, but a sell

    RiskResult result = checker.check(order, 100.0, 0.0);

    REQUIRE(result.passed);
}

TEST_CASE("fat-finger is checked before position limit and buying power", "[risk_checker]") {
    PositionKeeper positions;
    RiskChecker checker = make_checker(positions);
    Order order{"AAPL", 300, 0.0, true};  // fails fat-finger AND would fail the others

    RiskResult result = checker.check(order, 100.0, 0.0);

    REQUIRE_FALSE(result.passed);
    REQUIRE(result.reason == "fat-finger: order notional exceeds max");
}
