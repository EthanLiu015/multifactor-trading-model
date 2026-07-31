#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include "position/PositionKeeper.hpp"

using namespace engine::position;
using Catch::Approx;

TEST_CASE("an untraded symbol is flat", "[position_keeper]") {
    PositionKeeper keeper;

    Position pos = keeper.position("AAPL");

    REQUIRE(pos.qty == 0.0);
}

TEST_CASE("a single buy opens a long position at the fill price", "[position_keeper]") {
    PositionKeeper keeper;

    keeper.on_fill("AAPL", 100, 10.0, true);
    Position pos = keeper.position("AAPL");

    REQUIRE(pos.qty == Approx(100.0));
    REQUIRE(pos.avg_price == Approx(10.0));
    REQUIRE(pos.realized_pnl == Approx(0.0));
}

TEST_CASE("a same-direction fill re-averages cost", "[position_keeper]") {
    PositionKeeper keeper;

    keeper.on_fill("AAPL", 100, 10.0, true);
    keeper.on_fill("AAPL", 50, 12.0, true);
    Position pos = keeper.position("AAPL");

    REQUIRE(pos.qty == Approx(150.0));
    REQUIRE(pos.avg_price == Approx(1600.0 / 150.0));
}

TEST_CASE("a partial close realizes P&L and leaves the remainder at the same cost basis",
          "[position_keeper]") {
    PositionKeeper keeper;
    keeper.on_fill("AAPL", 100, 10.0, true);
    keeper.on_fill("AAPL", 50, 12.0, true);  // qty=150, avg=10.6667

    keeper.on_fill("AAPL", 80, 15.0, false);
    Position pos = keeper.position("AAPL");

    REQUIRE(pos.qty == Approx(70.0));
    REQUIRE(pos.avg_price == Approx(1600.0 / 150.0));  // unchanged: still the same open lot
    REQUIRE(pos.realized_pnl == Approx((15.0 - 1600.0 / 150.0) * 80.0));
}

TEST_CASE("closing past zero flips to a new position on the other side", "[position_keeper]") {
    PositionKeeper keeper;
    keeper.on_fill("AAPL", 100, 10.0, true);
    keeper.on_fill("AAPL", 50, 12.0, true);   // qty=150, avg=10.6667
    keeper.on_fill("AAPL", 80, 15.0, false);  // qty=70, avg unchanged, realized ~346.67

    keeper.on_fill("AAPL", 100, 20.0, false);
    Position pos = keeper.position("AAPL");

    REQUIRE(pos.qty == Approx(-30.0));
    REQUIRE(pos.avg_price == Approx(20.0));
    REQUIRE(pos.realized_pnl == Approx(1000.0).margin(0.01));
}

TEST_CASE("a short position accumulates and closes with correctly-signed P&L",
          "[position_keeper]") {
    PositionKeeper keeper;

    keeper.on_fill("AAPL", 100, 50.0, false);  // open short 100 @ 50
    Position opened = keeper.position("AAPL");
    REQUIRE(opened.qty == Approx(-100.0));
    REQUIRE(opened.avg_price == Approx(50.0));

    keeper.on_fill("AAPL", 100, 40.0, true);  // buy back at a lower price -> profit
    Position closed = keeper.position("AAPL");

    REQUIRE(closed.qty == Approx(0.0));
    REQUIRE(closed.realized_pnl == Approx((50.0 - 40.0) * 100.0));
}

TEST_CASE("positions for different symbols are independent", "[position_keeper]") {
    PositionKeeper keeper;

    keeper.on_fill("AAPL", 100, 10.0, true);
    keeper.on_fill("MSFT", 50, 300.0, false);

    REQUIRE(keeper.position("AAPL").qty == Approx(100.0));
    REQUIRE(keeper.position("MSFT").qty == Approx(-50.0));
}
