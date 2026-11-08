"""Checks of the backtest plumbing on simulated bars: with every filter off, setups must reach orders, fills and
exits, and every result must be consistent with its entry, stop and targets."""
import math
import pandas as pd
import tdf_config as C
import tdf_engine as E
from tdf_backtest import synthetic


def test_trade_path():
    C.SKIP_CHECKS = {1, 2, 3, 4, 6, 11}
    C.MIN_RR = 0.0
    C.DISP_MULT, C.ENT_GAP, C.WINDOW = 0.4, 0.2, (570, 900)
    trades, fun = [], {}
    for k in range(10):
        t, f, _ = E.run_symbol(synthetic("X%d" % k, 200, 100 + k), "X%d" % k, "test")
        trades += t
        for a, b in f.items():
            fun[a] = fun.get(a, 0) + b
    C.SKIP_CHECKS, C.MIN_RR, C.DISP_MULT, C.ENT_GAP, C.WINDOW = set(), 2.0, 1.0, 0.5, (570, 690)
    assert fun["order"] > 0 and fun["fill"] > 0, fun
    assert fun["poi"] >= fun["sweep"] >= fun["mss"] >= fun["order"] >= fun["fill"], fun
    df = pd.DataFrame(trades)
    assert len(df) == fun["fill"], (len(df), fun)       # every fill is closed by the end of its day
    for _, r in df.iterrows():
        assert r.r_gross >= -1.0 - 1e-9, r                              # never worse than the full stop
        assert r.r_net < r.r_gross                                       # costs always subtract
        if r.side == "long":
            assert r.stop < r.entry and (r.t1 is None or math.isnan(r.t1) or r.t1 > r.entry)
        else:
            assert r.stop > r.entry and (r.t1 is None or math.isnan(r.t1) or r.t1 < r.entry)
        assert r.mss_time < r.fill_time <= r.exit_time
        assert r.risk_pct >= C.MIN_STOP_PCT - 1e-6
        if r.exit == "stop":
            assert r.r_gross == -1.0
        if r.exit == "T1 then breakeven":
            assert r.t1_hit and r.r_gross > 0
    print("trades", len(df), "funnel", {k: v for k, v in fun.items() if v})
    print(df["exit"].value_counts().to_dict(), "avg gross", round(df.r_gross.mean(), 3))


def test_daily_structure():
    d = E.Daily()
    p = 100.0
    for k in range(40):                      # a clean staircase up: HH + HL -> uptrend
        up = (k // 4) % 2 == 0
        p += 3 if up else -1.5
        d.step(p + 1, p - 1, p, 1.0)
    assert d.st == 1 and d.bias() == 1, (d.st, d.nH, d.nL)
    for k in range(30):                      # a hard fall: close below the protected low -> downtrend
        p -= 4
        d.step(p + 1, p - 1, p, 1.0)
    assert d.st == -1 and d.bias() == -1, d.st
    print("daily structure ok")


def test_pullback_no_lookahead():
    """On a driftless random walk the pullback model must not make money before costs."""
    import numpy as np
    import bias_engine as B
    rows = []
    for k in range(4):
        rng = np.random.default_rng(500 + k)
        idx = pd.bdate_range(end="2026-11-06", periods=150, tz="America/New_York")
        times = [d + pd.Timedelta(minutes=570 + 5 * m) for d in idx for m in range(78)]
        n = len(times)
        c = 100 * np.exp(np.cumsum(rng.standard_t(4, n) * 0.0018))
        o = np.r_[100, c[:-1]]
        h = np.maximum(o, c) * (1 + np.abs(rng.normal(0, 0.0012, n)))
        l = np.minimum(o, c) * (1 - np.abs(rng.normal(0, 0.0012, n)))
        df = pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "volume": 1e5}, index=pd.DatetimeIndex(times))
        rows += B.run_symbol_bias(df, "R%d" % k)
    d = pd.DataFrame(rows)
    gross = (d["r_2R"] + d["cost_r"]).mean()
    assert len(d) > 500 and abs(gross) < 0.12, (len(d), gross)
    for e in B.EXITS:
        assert d["r_" + e].min() >= -1.0 - d["cost_r"].max() - 1e-6
    print("pullback model: %d random-walk signals, gross %.3fR (no edge, as expected)" % (len(d), gross))


if __name__ == "__main__":
    test_pullback_no_lookahead()
    test_daily_structure()
    test_trade_path()
