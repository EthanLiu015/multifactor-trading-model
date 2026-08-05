// One-off live verification for AlpacaGateway's submit/cancel path against
// the real Alpaca paper account. Not part of the automated test suite --
// places then cancels one resting limit order (buy 1 AAPL @ $1.00, far
// below market so it never fills), verifying the real submit -> Ack event
// -> cancel -> Cancel event round trip. Run from the repo root (reads
// .env from the current directory):
//   engine/build/smoke_alpaca_gateway

#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>

#include "broker/AlpacaGateway.hpp"

namespace {
// Same minimal .env loader as tools/smoke_market_data.cpp.
void load_dotenv(const std::string& path) {
    std::ifstream file(path);
    std::string line;
    while (std::getline(file, line)) {
        auto eq = line.find('=');
        if (eq == std::string::npos) {
            continue;
        }
        std::string key = line.substr(0, eq);
        std::string value = line.substr(eq + 1);
        setenv(key.c_str(), value.c_str(), 0);
    }
}

bool wait_for_event(engine::broker::AlpacaGateway& gateway, engine::broker::OrderId id,
                     engine::broker::EventType type, int wait_seconds) {
    for (int i = 0; i < wait_seconds; ++i) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
        for (const auto& event : gateway.poll_events()) {
            std::cout << "event: id=" << event.id << " type=" << to_string(event.type) << "\n";
            if (event.id == id && event.type == type) {
                return true;
            }
        }
    }
    return false;
}
}  // namespace

int main() {
    load_dotenv(".env");

    const char* key = std::getenv("ALPACA_API_KEY_ID");
    const char* secret = std::getenv("ALPACA_API_SECRET_KEY");
    const char* base_url = std::getenv("ALPACA_BASE_URL");
    if (key == nullptr || secret == nullptr || base_url == nullptr) {
        std::cerr << "ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY / ALPACA_BASE_URL not set "
                     "(checked .env in the current directory and the environment)\n";
        return 1;
    }

    engine::broker::AlpacaGateway gateway(key, secret, base_url);
    gateway.connect();

    std::cout << "Waiting 3s for the trade_updates stream to authenticate...\n";
    std::this_thread::sleep_for(std::chrono::seconds(3));

    engine::broker::Order order{"AAPL", 1, 1.00, true};  // limit buy, far below market, won't fill
    engine::broker::OrderId id = gateway.submit_order(order);
    std::cout << "Submitted order id=" << id << "\n";

    bool acked = wait_for_event(gateway, id, engine::broker::EventType::Ack, 10);
    std::cout << (acked ? "PASS: Ack event received\n" : "FAIL: no Ack event within 10s\n");

    gateway.cancel_order(id);
    std::cout << "Cancel requested for id=" << id << "\n";

    bool canceled = wait_for_event(gateway, id, engine::broker::EventType::Cancel, 10);
    std::cout << (canceled ? "PASS: Cancel event received\n"
                           : "FAIL: no Cancel event within 10s\n");

    gateway.disconnect();
    return (acked && canceled) ? 0 : 1;
}
