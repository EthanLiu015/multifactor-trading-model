#include "marketdata/MarketDataHandler.hpp"

#include <nlohmann/json.hpp>

namespace engine::marketdata {

void MarketDataHandler::on_message(const std::string& raw_json) {
    const auto messages = nlohmann::json::parse(raw_json);
    for (const auto& msg : messages) {
        const std::string type = msg.at("T").get<std::string>();
        const std::string symbol = msg.value("S", std::string());

        if (type == "t") {
            trades_[symbol] = Trade{
                msg.at("p").get<double>(),
                msg.at("s").get<double>(),
                msg.value("t", std::string()),
            };
        } else if (type == "q") {
            quotes_[symbol] = Quote{
                msg.at("bp").get<double>(),
                msg.at("bs").get<double>(),
                msg.at("ap").get<double>(),
                msg.at("as").get<double>(),
                msg.value("t", std::string()),
            };
        }
        // Other message types (success/error/subscription acks) aren't
        // tracked here -- skipped, not an error.
    }
}

std::optional<Trade> MarketDataHandler::latest_trade(const std::string& symbol) const {
    auto it = trades_.find(symbol);
    return it != trades_.end() ? std::optional<Trade>(it->second) : std::nullopt;
}

std::optional<Quote> MarketDataHandler::latest_quote(const std::string& symbol) const {
    auto it = quotes_.find(symbol);
    return it != quotes_.end() ? std::optional<Quote>(it->second) : std::nullopt;
}

}  // namespace engine::marketdata
