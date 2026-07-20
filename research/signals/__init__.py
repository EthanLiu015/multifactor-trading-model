"""Signal registry — every signal follows the same contract.

Each ``compute_*`` function: ``fn(bars: pl.LazyFrame, rebuild_date: date)
-> pl.DataFrame[effective_date, security_id, signal_value]``. Tunable
window sizes are keyword-only with defaults, never required at the call
site, so the driving loop (research/alpha/ic.py) and this registry can
call every signal identically regardless of what it computes internally.

To add a signal: write research/signals/<name>.py following that contract
(copy an existing one), then add one line below. Nothing else changes.
"""

from research.signals.low_vol import compute_low_vol
from research.signals.momentum import compute_momentum
from research.signals.reversal import compute_reversal

SIGNAL_REGISTRY = {
    "momentum": compute_momentum,
    "reversal": compute_reversal,
    "low_vol": compute_low_vol,
}
