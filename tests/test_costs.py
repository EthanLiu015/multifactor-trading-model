import numpy as np

from research.backtest.costs import trade_cost


def test_zero_trade_gives_zero_cost():
    delta_w = np.zeros(3)
    adv = np.array([1e6, 2e6, 3e6])
    cost = trade_cost(delta_w, adv, book_notional=10_000_000.0)

    assert cost.shape == (3,)
    assert np.all(cost == 0.0)


def test_impact_rate_scales_sublinearly_with_trade_size():
    """Square-root impact: the cost RATE (bps) grows as sqrt(size), not the
    total $ cost -- total $ cost = rate * size actually grows *faster*
    than linear (~size**1.5) since the rate itself rises with size. Flat
    components zeroed out to isolate the impact term."""
    adv = np.array([5e6])
    book_notional = 10_000_000.0
    kwargs = dict(half_spread_bps=0.0, fee_bps=0.0)
    small = trade_cost(np.array([0.01]), adv, book_notional, **kwargs)
    large = trade_cost(np.array([0.02]), adv, book_notional, **kwargs)

    small_notional = 0.01 * book_notional
    large_notional = 0.02 * book_notional
    rate_small = small[0] / small_notional
    rate_large = large[0] / large_notional

    assert rate_large > rate_small
    assert rate_large < 2 * rate_small
    # total $ cost still grows (impact is real), just faster than the rate
    assert large[0] > 2 * small[0]


def test_lower_adv_gives_higher_cost_for_same_trade():
    delta_w = np.array([0.02, 0.02])
    adv = np.array([1e6, 1e8])  # first name much less liquid
    cost = trade_cost(delta_w, adv, book_notional=10_000_000.0)

    assert cost[0] > cost[1]
