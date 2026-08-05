#pragma once

#include <mutex>
#include <optional>
#include <string>
#include <unordered_map>

#include <ixwebsocket/IXWebSocket.h>

#include "broker/IBrokerGateway.hpp"
#include "broker/OrderEvent.hpp"

namespace engine::broker {

// Translates one Alpaca trade_updates websocket message into an OrderEvent.
// Free function (not a private method) so it's testable with canned JSON
// without a live connection -- same live/offline split as
// engine::marketdata::MarketDataHandler vs AlpacaMarketDataStream.
//
// Returns std::nullopt for: event types this gateway doesn't track (matches
// OrderEvent's own unreachable EventType::New -- see OrderGateway.cpp), or
// a client_order_id that doesn't parse back to a numeric OrderId (e.g. an
// order placed by something other than this process). "expired" maps to
// Cancel, not Reject -- a judgment call: expiry ends a resting order
// without executing it, closer to cancellation than an outright rejection.
std::optional<OrderEvent> parse_trade_update(const std::string& raw_json);

// Live IBrokerGateway backed by Alpaca's real Trading API: REST for
// submit/cancel (DESIGN.md's execution path), the trade_updates websocket
// for async order status. Alpaca assigns its own UUID order id on submit;
// this class sets client_order_id to str(OrderId) so incoming events map
// straight back without a reverse lookup, but a forward map (OrderId ->
// Alpaca UUID) is still needed for cancel (DELETE requires Alpaca's id).
//
// The websocket delivers events on its own background thread while the
// caller's thread calls submit_order/cancel_order/poll_events -- the first
// genuinely concurrent class in this codebase (every prior engine class
// was single-threaded by construction). A mutex guards all shared state.
//
// Not unit-tested beyond parse_trade_update: REST calls and the websocket
// connection need a real account, same posture as AlpacaMarketDataStream.
class AlpacaGateway : public IBrokerGateway {
public:
    AlpacaGateway(std::string api_key, std::string api_secret, std::string base_url);

    // Connects the trade_updates stream. Must be called before events from
    // submitted orders become observable via poll_events().
    void connect();
    void disconnect();

    OrderId submit_order(const Order& order) override;
    void cancel_order(OrderId id) override;
    std::vector<OrderEvent> poll_events() override;

private:
    struct HttpResponse {
        long status_code = 0;
        std::string body;
    };
    HttpResponse send_request(const std::string& method, const std::string& path,
                               const std::string& json_body = "") const;

    std::string api_key_;
    std::string api_secret_;
    std::string base_url_;

    mutable std::mutex mutex_;
    std::vector<OrderEvent> pending_events_;
    std::unordered_map<OrderId, std::string> alpaca_order_id_;
    OrderId next_id_ = 1;

    ix::WebSocket ws_;
};

}  // namespace engine::broker
