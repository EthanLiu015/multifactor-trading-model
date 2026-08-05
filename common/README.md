# common/

Shared schemas between the Python research stack and the C++ engine
(DESIGN.md's repo-layout line: "shared schemas: target portfolio
file/IPC format, symbol master").

## target_portfolio.json

The file contract between `research/portfolio/export_target.py` (writer)
and `engine`'s `ExecutionScheduler` (reader, `engine/include/execution/ExecutionScheduler.hpp`).
Written once per rebalance, holds target **dollar notional** per symbol —
deliberately not shares or weights, so the execution side converts to
shares using its own live price rather than a research-side price that
may be stale by execution time.

```json
{
  "rebuild_date": "2026-08-04",
  "status": "optimal",
  "positions": [
    {"symbol": "AAPL", "target_notional": 5000000.0},
    {"symbol": "MSFT", "target_notional": -3000000.0}
  ]
}
```

- `status`: `TargetPortfolio.status` passed through as-is (e.g. `"optimal"`,
  `"infeasible"`). The execution scheduler refuses to trade off anything
  other than `"optimal"` — a non-optimal solve is a real signal, not
  something to silently act on.
- `positions`: zero-weight symbols are omitted by the writer. Symbols are
  ticker strings (yfinance's native `security_id`, already resolved by
  the research pipeline — NOT `security_master`'s `internal_id`, a
  separate, not-yet-integrated identifier system).
- No file exists here until something calls `export_target_portfolio()` —
  this directory has no other content yet.
