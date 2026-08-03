#pragma once

#include <optional>
#include <string>
#include <unordered_map>

namespace engine::marketdata {

struct Trade {
    double price = 0.0;
    double size = 0.0;
    std::string timestamp;  // RFC-3339 as received from Alpaca, unparsed
};

struct Quote {
    double bid_price = 0.0;
    double bid_size = 0.0;
    double ask_price = 0.0;
    double ask_size = 0.0;
    std::string timestamp;
};

// Top-of-book only -- Alpaca's free IEX feed gives trades and quotes, not
// L2 depth, so there is no order book to maintain beyond the latest of
// each per symbol (DESIGN.md Block 5's "market data handler ... internal
// book").
//
// Pure parsing/state logic, deliberately separate from the live websocket
// connection (AlpacaMarketDataStream) so it is fully offline-testable with
// canned JSON -- the connection itself is not unit-tested, same posture as
// research/data/delta_store.py's DeltaPITStore (live-verified once, not
// faked).
class MarketDataHandler {
public:
    // raw_json is one message from Alpaca's stream: a JSON array of
    // message objects, e.g. `[{"T":"t","S":"AAPL","p":150.25,"s":100,
    // "t":"..."}]`. Malformed JSON propagates as an exception (a real feed
    // message failing to parse is a genuine anomaly, not routine input).
    // Message types this class doesn't track (auth/subscription acks,
    // errors) are skipped, not an error.
    void on_message(const std::string& raw_json);

    std::optional<Trade> latest_trade(const std::string& symbol) const;
    std::optional<Quote> latest_quote(const std::string& symbol) const;

private:
    std::unordered_map<std::string, Trade> trades_;
    std::unordered_map<std::string, Quote> quotes_;
};

}  // namespace engine::marketdata
