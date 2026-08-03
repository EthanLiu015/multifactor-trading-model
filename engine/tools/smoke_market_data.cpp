// One-off live verification for AlpacaMarketDataStream + MarketDataHandler
// against the real Alpaca IEX feed. Not part of the automated test suite --
// needs real credentials and a live network connection, same posture as
// research/data/delta_store.py's DeltaPITStore (live-verified once, not
// faked). Run from the repo root (reads .env from the current directory):
//   engine/build/tools/smoke_market_data [symbol] [wait_seconds]

#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>

#include "marketdata/AlpacaMarketDataStream.hpp"
#include "marketdata/MarketDataHandler.hpp"

namespace {
// Minimal .env loader: KEY=VALUE lines, no quoting/escaping -- only needs
// to handle this repo's own .env file, not a general-purpose parser.
// Doesn't overwrite variables already set in the real environment.
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
}  // namespace

int main(int argc, char** argv) {
    load_dotenv(".env");

    const char* key = std::getenv("ALPACA_API_KEY_ID");
    const char* secret = std::getenv("ALPACA_API_SECRET_KEY");
    if (key == nullptr || secret == nullptr) {
        std::cerr << "ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY not set "
                     "(checked .env in the current directory and the environment)\n";
        return 1;
    }

    const std::string symbol = argc > 1 ? argv[1] : "AAPL";
    const int wait_seconds = argc > 2 ? std::stoi(argv[2]) : 20;

    engine::marketdata::MarketDataHandler handler;
    engine::marketdata::AlpacaMarketDataStream stream(key, secret, handler);
    stream.connect({symbol});

    std::cout << "Waiting up to " << wait_seconds << "s for " << symbol << " data...\n";
    for (int i = 0; i < wait_seconds; ++i) {
        std::this_thread::sleep_for(std::chrono::seconds(1));

        auto trade = handler.latest_trade(symbol);
        auto quote = handler.latest_quote(symbol);
        if (trade.has_value()) {
            std::cout << "TRADE " << symbol << " price=" << trade->price
                      << " size=" << trade->size << " ts=" << trade->timestamp << "\n";
        }
        if (quote.has_value()) {
            std::cout << "QUOTE " << symbol << " bid=" << quote->bid_price
                      << " ask=" << quote->ask_price << " ts=" << quote->timestamp << "\n";
        }
        if (trade.has_value() || quote.has_value()) {
            stream.disconnect();
            return 0;
        }
    }

    std::cerr << "No trade or quote received in " << wait_seconds
              << "s -- check the diagnostic log above (connected/authenticated/subscribed?) "
                 "and confirm the market is open (IEX only streams live ticks during US "
                 "market hours).\n";
    stream.disconnect();
    return 1;
}
