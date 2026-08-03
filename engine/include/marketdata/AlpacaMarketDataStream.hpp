#pragma once

#include <string>
#include <vector>

#include <ixwebsocket/IXWebSocket.h>

#include "marketdata/MarketDataHandler.hpp"

namespace engine::marketdata {

// Live websocket connection to Alpaca's free IEX feed
// (wss://stream.data.alpaca.markets/v2/iex), feeding raw messages into a
// MarketDataHandler. Auth is a JSON action message sent over the wire
// after connecting (not an HTTP header) -- must complete within Alpaca's
// 10-second window or it disconnects; subscribe is sent only after the
// server acks authentication, matching Alpaca's documented request/ack
// sequence.
//
// Not unit-tested: needs a real network connection and live credentials,
// same posture as research/data/delta_store.py's DeltaPITStore
// (live-verified once, not faked).
class AlpacaMarketDataStream {
public:
    AlpacaMarketDataStream(std::string api_key, std::string api_secret,
                            MarketDataHandler& handler);

    // Connects, authenticates, and (once authenticated) subscribes to
    // trades+quotes for the given symbols. Non-blocking -- ix::WebSocket
    // runs its own background thread; messages arrive via the callback
    // installed here.
    void connect(const std::vector<std::string>& symbols);
    void disconnect();

private:
    std::string api_key_;
    std::string api_secret_;
    MarketDataHandler& handler_;
    std::vector<std::string> symbols_;
    ix::WebSocket ws_;
};

}  // namespace engine::marketdata
