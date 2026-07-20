#include "journal/EventJournal.hpp"

#include <chrono>

namespace engine::journal {

EventJournal::EventJournal(const std::string& path) : out_(path, std::ios::app) {}

void EventJournal::append(const engine::broker::OrderEvent& event) {
    using namespace std::chrono;
    auto epoch_ms = duration_cast<milliseconds>(event.ts.time_since_epoch()).count();
    out_ << epoch_ms << ',' << event.id << ',' << engine::broker::to_string(event.type)
         << ',' << event.qty << ',' << event.price << ',' << event.reason << '\n';
    out_.flush();
}

}  // namespace engine::journal
