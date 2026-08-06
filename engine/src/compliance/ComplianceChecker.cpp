#include "compliance/ComplianceChecker.hpp"

#include <utility>

namespace engine::compliance {

namespace {
bool orders_match(const broker::Order& a, const broker::Order& b) {
    return a.symbol == b.symbol && a.qty == b.qty && a.limit_price == b.limit_price &&
           a.is_buy == b.is_buy;
}
}  // namespace

ComplianceChecker::ComplianceChecker(std::unordered_set<std::string> restricted_symbols,
                                      double max_order_shares)
    : restricted_symbols_(std::move(restricted_symbols)), max_order_shares_(max_order_shares) {}

ComplianceResult ComplianceChecker::check(const broker::Order& order) {
    if (restricted_symbols_.contains(order.symbol)) {
        return {false, "restricted list: " + order.symbol};
    }
    if (order.qty > max_order_shares_) {
        return {false, "max order size exceeded"};
    }

    auto it = seen_this_batch_.find(order.symbol);
    if (it != seen_this_batch_.end() && orders_match(it->second, order)) {
        return {false, "duplicate order: " + order.symbol};
    }
    seen_this_batch_[order.symbol] = order;

    return {true, ""};
}

void ComplianceChecker::reset() {
    seen_this_batch_.clear();
}

}  // namespace engine::compliance
