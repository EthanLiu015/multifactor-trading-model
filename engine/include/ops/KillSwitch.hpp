#pragma once

#include <string>

namespace engine::ops {

// Halts all order flow (DESIGN.md's ops layer: "one command/flag halts
// all order flow immediately; engine refuses new orders until manually
// re-armed"). Deliberately no automatic rearm -- whatever trips it
// (a manual command, or the drawdown check) requires a human to clear it;
// auto-clearing a safety gate would defeat its purpose.
class KillSwitch {
public:
    bool is_tripped() const;
    void trip(const std::string& reason);
    void rearm();  // clears both tripped state and the last reason

    const std::string& reason() const;  // last trip reason; empty if never tripped or after rearm

private:
    bool tripped_ = false;
    std::string reason_;
};

}  // namespace engine::ops
