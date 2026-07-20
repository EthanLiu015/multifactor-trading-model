#pragma once

#include <chrono>
#include <cstdint>
#include <string>

namespace engine::broker {

using OrderId = std::uint64_t;

enum class EventType { New, Ack, PartialFill, Fill, Cancel, Reject };

inline const char* to_string(EventType type) {
    switch (type) {
        case EventType::New:         return "New";
        case EventType::Ack:         return "Ack";
        case EventType::PartialFill: return "PartialFill";
        case EventType::Fill:        return "Fill";
        case EventType::Cancel:      return "Cancel";
        case EventType::Reject:      return "Reject";
    }
    return "Unknown";
}

// Emitted by any IBrokerGateway implementation (live or simulated) into the
// same event journal, so downstream code (position keeper, crash recovery)
// never has to know which one produced it.
struct OrderEvent {
    OrderId id;
    EventType type;
    double qty = 0.0;    // shares involved in this event; 0 for New/Ack/Cancel/Reject
    double price = 0.0;  // fill price; 0 for non-fill events
    std::chrono::system_clock::time_point ts;
    std::string reason;  // populated only for Reject; empty otherwise
};

}  // namespace engine::broker
