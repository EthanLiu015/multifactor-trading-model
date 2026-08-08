#include "broker/AlpacaGateway.hpp"

#include <curl/curl.h>

#include <chrono>
#include <iostream>
#include <mutex>
#include <stdexcept>

#include <nlohmann/json.hpp>

namespace engine::broker {

namespace {
double parse_optional_double(const nlohmann::json& j, const std::string& key) {
    if (!j.contains(key) || j.at(key).is_null()) {
        return 0.0;
    }
    return std::stod(j.at(key).get<std::string>());
}

size_t write_callback(char* ptr, size_t size, size_t nmemb, void* userdata) {
    auto* body = static_cast<std::string*>(userdata);
    body->append(ptr, size * nmemb);
    return size * nmemb;
}

std::once_flag curl_global_init_flag;
}  // namespace

std::optional<OrderEvent> parse_trade_update(const std::string& raw_json) {
    const auto msg = nlohmann::json::parse(raw_json);
    if (msg.value("stream", std::string()) != "trade_updates") {
        return std::nullopt;
    }

    const auto& data = msg.at("data");
    const std::string event = data.value("event", std::string());

    EventType type;
    if (event == "new" || event == "accepted") {
        // Both mean "order acknowledged, now live" -- Alpaca's paper
        // environment sends "accepted" as the initial event rather than
        // "new" (confirmed live 2026-08-04); mapping both is safe even if
        // a live account ever emits both, since a second Ack on a
        // non-terminal state is not an illegal transition.
        type = EventType::Ack;
    } else if (event == "fill") {
        type = EventType::Fill;
    } else if (event == "partial_fill") {
        type = EventType::PartialFill;
    } else if (event == "canceled" || event == "expired") {
        type = EventType::Cancel;
    } else if (event == "rejected") {
        type = EventType::Reject;
    } else {
        return std::nullopt;  // untracked event type (accepted/pending_new/replaced/...)
    }

    const auto& order = data.at("order");
    OrderId id;
    try {
        id = std::stoull(order.at("client_order_id").get<std::string>());
    } catch (const std::exception&) {
        return std::nullopt;  // not an id this gateway assigned
    }

    const double qty = parse_optional_double(data, "qty");
    const double price = parse_optional_double(data, "price");

    return OrderEvent{id, type, qty, price, std::chrono::system_clock::now(), ""};
}

AlpacaGateway::AlpacaGateway(std::string api_key, std::string api_secret, std::string base_url)
    : api_key_(std::move(api_key)),
      api_secret_(std::move(api_secret)),
      base_url_(std::move(base_url)),
      run_id_(std::to_string(
          std::chrono::system_clock::now().time_since_epoch().count())) {
    std::call_once(curl_global_init_flag, [] { curl_global_init(CURL_GLOBAL_DEFAULT); });
}

AlpacaGateway::HttpResponse AlpacaGateway::send_request(const std::string& method,
                                                         const std::string& path,
                                                         const std::string& json_body) const {
    CURL* curl = curl_easy_init();
    if (curl == nullptr) {
        throw std::runtime_error("AlpacaGateway: curl_easy_init failed");
    }

    const std::string url = base_url_ + path;
    HttpResponse response;

    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, ("APCA-API-KEY-ID: " + api_key_).c_str());
    headers = curl_slist_append(headers, ("APCA-API-SECRET-KEY: " + api_secret_).c_str());
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response.body);

    if (method == "POST") {
        curl_easy_setopt(curl, CURLOPT_POSTFIELDS, json_body.c_str());
    } else if (method == "DELETE") {
        curl_easy_setopt(curl, CURLOPT_CUSTOMREQUEST, "DELETE");
    }

    const CURLcode result = curl_easy_perform(curl);
    if (result != CURLE_OK) {
        const std::string error = curl_easy_strerror(result);
        curl_slist_free_all(headers);
        curl_easy_cleanup(curl);
        throw std::runtime_error("AlpacaGateway: curl request failed: " + error);
    }

    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &response.status_code);

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    return response;
}

OrderId AlpacaGateway::submit_order(const Order& order) {
    OrderId id;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        id = next_id_++;
    }

    nlohmann::json body = {
        {"symbol", order.symbol},
        {"qty", std::to_string(order.qty)},
        {"side", order.is_buy ? "buy" : "sell"},
        {"type", order.limit_price == 0.0 ? "market" : "limit"},
        {"time_in_force", "day"},  // placeholder default -- Order has no TIF field yet
        {"client_order_id", std::to_string(id) + "-" + run_id_},
    };
    if (order.limit_price != 0.0) {
        body["limit_price"] = std::to_string(order.limit_price);
    }

    const HttpResponse response = send_request("POST", "/v2/orders", body.dump());
    if (response.status_code < 200 || response.status_code >= 300) {
        throw std::runtime_error("AlpacaGateway::submit_order failed (HTTP " +
                                  std::to_string(response.status_code) + "): " + response.body);
    }

    const auto parsed = nlohmann::json::parse(response.body);
    {
        std::lock_guard<std::mutex> lock(mutex_);
        alpaca_order_id_[id] = parsed.at("id").get<std::string>();
    }
    return id;
}

void AlpacaGateway::cancel_order(OrderId id) {
    std::string alpaca_id;
    {
        std::lock_guard<std::mutex> lock(mutex_);
        alpaca_id = alpaca_order_id_.at(id);  // throws std::out_of_range if unknown
    }
    // A 422 ("no longer cancelable") is a normal outcome the trade_updates
    // stream will reflect asynchronously, not a code-level error -- not
    // checked here, matching BrokerSimulator::cancel_order's own posture.
    send_request("DELETE", "/v2/orders/" + alpaca_id);
}

std::vector<OrderEvent> AlpacaGateway::poll_events() {
    std::lock_guard<std::mutex> lock(mutex_);
    std::vector<OrderEvent> out = std::move(pending_events_);
    pending_events_.clear();
    return out;
}

std::vector<BrokerPosition> AlpacaGateway::fetch_positions() const {
    const HttpResponse response = send_request("GET", "/v2/positions");
    if (response.status_code < 200 || response.status_code >= 300) {
        throw std::runtime_error("AlpacaGateway::fetch_positions failed (HTTP " +
                                  std::to_string(response.status_code) + "): " + response.body);
    }

    const auto parsed = nlohmann::json::parse(response.body);
    std::vector<BrokerPosition> positions;
    for (const auto& p : parsed) {
        positions.push_back(
            {p.at("symbol").get<std::string>(), std::stod(p.at("qty").get<std::string>())});
    }
    return positions;
}

void AlpacaGateway::connect() {
    ws_.setUrl(base_url_.find("paper") != std::string::npos
                   ? "wss://paper-api.alpaca.markets/stream"
                   : "wss://api.alpaca.markets/stream");

    ws_.setOnMessageCallback([this](const ix::WebSocketMessagePtr& msg) {
        if (msg->type == ix::WebSocketMessageType::Open) {
            std::cerr << "[AlpacaGateway] connected, sending auth\n";
            const nlohmann::json auth = {
                {"action", "auth"}, {"key", api_key_}, {"secret", api_secret_}};
            ws_.send(auth.dump());
            return;
        }
        if (msg->type == ix::WebSocketMessageType::Close) {
            std::cerr << "[AlpacaGateway] closed: " << msg->closeInfo.reason << "\n";
            return;
        }
        if (msg->type == ix::WebSocketMessageType::Error) {
            std::cerr << "[AlpacaGateway] error: " << msg->errorInfo.reason << "\n";
            return;
        }
        if (msg->type != ix::WebSocketMessageType::Message) {
            return;
        }

        const auto parsed_msg = nlohmann::json::parse(msg->str);
        const std::string stream = parsed_msg.value("stream", std::string());
        if (stream == "authorization") {
            const std::string status = parsed_msg.at("data").value("status", std::string());
            if (status != "authorized") {
                std::cerr << "[AlpacaGateway] authentication failed: " << status << "\n";
                return;
            }
            std::cerr << "[AlpacaGateway] authenticated, subscribing to trade_updates\n";
            const nlohmann::json listen = {
                {"action", "listen"}, {"data", {{"streams", {"trade_updates"}}}}};
            ws_.send(listen.dump());
            return;
        }
        if (stream == "listening") {
            std::cerr << "[AlpacaGateway] subscription ack: " << parsed_msg.dump() << "\n";
            return;
        }

        auto event = parse_trade_update(msg->str);
        if (event.has_value()) {
            std::lock_guard<std::mutex> lock(mutex_);
            pending_events_.push_back(*event);
        } else if (stream == "trade_updates") {
            std::cerr << "[AlpacaGateway] trade_updates message not mapped to an OrderEvent: "
                      << msg->str << "\n";
        }
    });

    ws_.start();
}

void AlpacaGateway::disconnect() {
    ws_.stop();
}

}  // namespace engine::broker
