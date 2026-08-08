#include "ops/Reconciliation.hpp"

#include <cmath>
#include <unordered_map>
#include <unordered_set>

namespace engine::ops {

ReconciliationResult reconcile_positions(
    const position::PositionKeeper& local,
    const std::vector<broker::BrokerPosition>& broker_positions, double tolerance) {
    std::unordered_map<std::string, double> broker_qty_by_symbol;
    for (const auto& bp : broker_positions) {
        broker_qty_by_symbol[bp.symbol] = bp.qty;
    }

    std::unordered_set<std::string> all_symbols;
    for (const auto& [symbol, pos] : local.all_positions()) {
        if (pos.qty != 0.0) {
            all_symbols.insert(symbol);
        }
    }
    for (const auto& bp : broker_positions) {
        all_symbols.insert(bp.symbol);
    }

    ReconciliationResult result;
    for (const auto& symbol : all_symbols) {
        const double local_qty = local.position(symbol).qty;
        const auto it = broker_qty_by_symbol.find(symbol);
        const double broker_qty = it != broker_qty_by_symbol.end() ? it->second : 0.0;

        if (std::abs(local_qty - broker_qty) > tolerance) {
            result.clean = false;
            result.breaks.push_back({symbol, local_qty, broker_qty});
        }
    }
    return result;
}

}  // namespace engine::ops
