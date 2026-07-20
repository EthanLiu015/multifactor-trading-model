#pragma once

#include <fstream>
#include <string>

#include "broker/OrderEvent.hpp"

namespace engine::journal {

// Append-only durable log of every OrderEvent, written before the engine
// acts on it (DESIGN.md Block 5: crash recovery via event journaling).
// Skeleton: one CSV line per event, flushed synchronously on append. Binary
// framing, fsync discipline, and the replay-on-restart parser are scoped
// when the order gateway is built — this proves the write path only.
class EventJournal {
public:
    explicit EventJournal(const std::string& path);
    void append(const engine::broker::OrderEvent& event);

private:
    std::ofstream out_;
};

}  // namespace engine::journal
