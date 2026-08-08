#include <catch2/catch_test_macros.hpp>

#include "ops/Reconciliation.hpp"

using namespace engine::broker;
using namespace engine::position;
using namespace engine::ops;

TEST_CASE("matching positions are clean", "[reconciliation]") {
    PositionKeeper local;
    local.on_fill("AAPL", 100, 150.0, true);

    auto result = reconcile_positions(local, {{"AAPL", 100.0}});

    REQUIRE(result.clean);
    REQUIRE(result.breaks.empty());
}

TEST_CASE("a tiny float difference within tolerance is still clean", "[reconciliation]") {
    PositionKeeper local;
    local.on_fill("AAPL", 100, 150.0, true);

    auto result = reconcile_positions(local, {{"AAPL", 100.0000001}}, 1e-6);

    REQUIRE(result.clean);
}

TEST_CASE("a local position the broker doesn't report is a break", "[reconciliation]") {
    PositionKeeper local;
    local.on_fill("AAPL", 100, 150.0, true);

    auto result = reconcile_positions(local, {});

    REQUIRE_FALSE(result.clean);
    REQUIRE(result.breaks.size() == 1);
    REQUIRE(result.breaks[0].symbol == "AAPL");
    REQUIRE(result.breaks[0].local_qty == 100.0);
    REQUIRE(result.breaks[0].broker_qty == 0.0);
}

TEST_CASE("a broker position the local book doesn't know about is a break", "[reconciliation]") {
    PositionKeeper local;  // flat -- never traded MSFT

    auto result = reconcile_positions(local, {{"MSFT", 50.0}});

    REQUIRE_FALSE(result.clean);
    REQUIRE(result.breaks.size() == 1);
    REQUIRE(result.breaks[0].symbol == "MSFT");
    REQUIRE(result.breaks[0].local_qty == 0.0);
    REQUIRE(result.breaks[0].broker_qty == 50.0);
}

TEST_CASE("a quantity mismatch on the same symbol is a break", "[reconciliation]") {
    PositionKeeper local;
    local.on_fill("AAPL", 100, 150.0, true);

    auto result = reconcile_positions(local, {{"AAPL", 80.0}});

    REQUIRE_FALSE(result.clean);
    REQUIRE(result.breaks.size() == 1);
    REQUIRE(result.breaks[0].local_qty == 100.0);
    REQUIRE(result.breaks[0].broker_qty == 80.0);
}

TEST_CASE("multiple independent breaks are all captured", "[reconciliation]") {
    PositionKeeper local;
    local.on_fill("AAPL", 100, 150.0, true);  // mismatched vs broker
    local.on_fill("GOOG", 10, 2000.0, true);  // local-only

    auto result = reconcile_positions(local, {{"AAPL", 90.0}, {"MSFT", 50.0}});  // MSFT broker-only

    REQUIRE_FALSE(result.clean);
    REQUIRE(result.breaks.size() == 3);
}
