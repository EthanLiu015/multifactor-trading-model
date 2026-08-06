#include <catch2/catch_test_macros.hpp>

#include "compliance/ComplianceChecker.hpp"

using namespace engine::broker;
using namespace engine::compliance;

TEST_CASE("an order under every rule passes", "[compliance_checker]") {
    ComplianceChecker checker;
    Order order{"AAPL", 100, 0.0, true};

    ComplianceResult result = checker.check(order);

    REQUIRE(result.passed);
    REQUIRE(result.reason.empty());
}

TEST_CASE("a restricted symbol is rejected", "[compliance_checker]") {
    ComplianceChecker checker({"AAPL"});
    Order order{"AAPL", 100, 0.0, true};

    ComplianceResult result = checker.check(order);

    REQUIRE_FALSE(result.passed);
    REQUIRE(result.reason == "restricted list: AAPL");
}

TEST_CASE("an order over max_order_shares is rejected", "[compliance_checker]") {
    ComplianceChecker checker({}, 1000.0);
    Order order{"AAPL", 1500, 0.0, true};

    ComplianceResult result = checker.check(order);

    REQUIRE_FALSE(result.passed);
    REQUIRE(result.reason == "max order size exceeded");
}

TEST_CASE("an identical order resubmitted in the same batch is a duplicate",
          "[compliance_checker]") {
    ComplianceChecker checker;
    Order order{"AAPL", 100, 0.0, true};

    REQUIRE(checker.check(order).passed);
    ComplianceResult second = checker.check(order);

    REQUIRE_FALSE(second.passed);
    REQUIRE(second.reason == "duplicate order: AAPL");
}

TEST_CASE("a different order for the same symbol is not a duplicate", "[compliance_checker]") {
    ComplianceChecker checker;
    Order first{"AAPL", 100, 0.0, true};
    Order second{"AAPL", 50, 0.0, false};  // different qty and side

    REQUIRE(checker.check(first).passed);
    REQUIRE(checker.check(second).passed);
}

TEST_CASE("reset clears duplicate-detection state for a new batch", "[compliance_checker]") {
    ComplianceChecker checker;
    Order order{"AAPL", 100, 0.0, true};
    REQUIRE(checker.check(order).passed);
    REQUIRE_FALSE(checker.check(order).passed);  // duplicate within the batch

    checker.reset();

    REQUIRE(checker.check(order).passed);  // legitimate repeat in a new batch
}

TEST_CASE("restricted-list is checked before max order size and duplicate suppression",
          "[compliance_checker]") {
    ComplianceChecker checker({"AAPL"}, 10.0);  // would also fail max size
    Order order{"AAPL", 1000, 0.0, true};

    ComplianceResult result = checker.check(order);

    REQUIRE_FALSE(result.passed);
    REQUIRE(result.reason == "restricted list: AAPL");
}
