#include "ops/KillSwitch.hpp"

namespace engine::ops {

bool KillSwitch::is_tripped() const {
    return tripped_;
}

void KillSwitch::trip(const std::string& reason) {
    tripped_ = true;
    reason_ = reason;
}

void KillSwitch::rearm() {
    tripped_ = false;
    reason_.clear();
}

const std::string& KillSwitch::reason() const {
    return reason_;
}

}  // namespace engine::ops
