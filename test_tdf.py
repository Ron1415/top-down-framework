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
        t, f = E.run_symbol(synthetic("X%d" % k, 200, 100 + k), "X%d" % k, "test")
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


if __name__ == "__main__":
    test_daily_structure()
    test_trade_path()
