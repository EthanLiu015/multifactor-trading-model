#include <catch2/catch_test_macros.hpp>

#include "ops/KillSwitch.hpp"

using namespace engine::ops;

TEST_CASE("a new KillSwitch is not tripped", "[kill_switch]") {
    KillSwitch switch_;

    REQUIRE_FALSE(switch_.is_tripped());
    REQUIRE(switch_.reason().empty());
}

TEST_CASE("trip sets tripped state and records the reason", "[kill_switch]") {
    KillSwitch switch_;

    switch_.trip("book drawdown exceeded -5%");

    REQUIRE(switch_.is_tripped());
    REQUIRE(switch_.reason() == "book drawdown exceeded -5%");
}

TEST_CASE("rearm clears both tripped state and the reason", "[kill_switch]") {
    KillSwitch switch_;
    switch_.trip("manual halt");

    switch_.rearm();

    REQUIRE_FALSE(switch_.is_tripped());
    REQUIRE(switch_.reason().empty());
}

TEST_CASE("a later trip overwrites the earlier reason", "[kill_switch]") {
    KillSwitch switch_;
    switch_.trip("first reason");

    switch_.trip("second reason");

    REQUIRE(switch_.reason() == "second reason");
}
