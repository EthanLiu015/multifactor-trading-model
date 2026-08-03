#include "marketdata/AlpacaMarketDataStream.hpp"

#include <iostream>

#include <nlohmann/json.hpp>

namespace engine::marketdata {

namespace {
constexpr const char* kFeedUrl = "wss://stream.data.alpaca.markets/v2/iex";
}

AlpacaMarketDataStream::AlpacaMarketDataStream(std::string api_key, std::string api_secret,
                                                MarketDataHandler& handler)
    : api_key_(std::move(api_key)), api_secret_(std::move(api_secret)), handler_(handler) {
    ws_.setUrl(kFeedUrl);
}

void AlpacaMarketDataStream::connect(const std::vector<std::string>& symbols) {
    symbols_ = symbols;

    ws_.setOnMessageCallback([this](const ix::WebSocketMessagePtr& msg) {
        if (msg->type == ix::WebSocketMessageType::Open) {
            std::cerr << "[AlpacaMarketDataStream] connected, sending auth\n";
            const nlohmann::json auth = {
                {"action", "auth"}, {"key", api_key_}, {"secret", api_secret_}};
            ws_.send(auth.dump());
            return;
        }
        if (msg->type == ix::WebSocketMessageType::Close) {
            std::cerr << "[AlpacaMarketDataStream] closed: " << msg->closeInfo.reason << "\n";
            return;
        }
        if (msg->type == ix::WebSocketMessageType::Error) {
            std::cerr << "[AlpacaMarketDataStream] error: " << msg->errorInfo.reason << "\n";
            return;
        }
        if (msg->type != ix::WebSocketMessageType::Message) {
            return;
        }

        handler_.on_message(msg->str);

        // Subscribe only after the server acks authentication -- sending
        // it earlier races Alpaca's own auth-then-subscribe sequence.
        const auto parsed = nlohmann::json::parse(msg->str);
        for (const auto& entry : parsed) {
            const std::string type = entry.value("T", std::string());
            if (type == "success" && entry.value("msg", std::string()) == "authenticated") {
                std::cerr << "[AlpacaMarketDataStream] authenticated, subscribing\n";
                nlohmann::json subscribe = {{"action", "subscribe"}};
                subscribe["trades"] = symbols_;
                subscribe["quotes"] = symbols_;
                ws_.send(subscribe.dump());
            } else if (type == "subscription") {
                std::cerr << "[AlpacaMarketDataStream] subscription ack: " << entry.dump() << "\n";
            } else if (type == "error") {
                std::cerr << "[AlpacaMarketDataStream] server error: " << entry.dump() << "\n";
            }
        }
    });

    ws_.start();
}

void AlpacaMarketDataStream::disconnect() {
    ws_.stop();
}

}  // namespace engine::marketdata
