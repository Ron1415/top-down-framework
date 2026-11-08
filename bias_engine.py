"""Bias-score + pullback model (Nov 8, 2026).

1. TOP-DOWN BIAS SCORE, from completed higher-timeframe bars only (same engines as the framework):
       daily structure 25, 4-hour trend 20, 1-hour trend 20, who is in control (4H) 15, weekly trend 10,
       daily premium / discount 10.  Score -100..+100: the sign is the direction, the size is the confidence %.
2. ENTRY on the 5-minute chart: in the bias direction only, on the first touch of a pullback level
   (8 EMA, session VWAP or 21 EMA): the bar trades to the level and CLOSES back on the trend side.
   The entry is at that bar's close. Stop beyond the pullback bar (and the level) by 0.1 ATR, at least 0.20%.
3. EXITS (each tested): fixed 1.5R / 2R / 3R, or a trail that exits on the first close back through the 8 EMA.
   Anything open is closed at 15:55. Costs 0.02% of price per side.
Every signal is recorded with its bias score and its outcome under every exit; the report applies the
thresholds, one trade at a time per symbol and the daily limits.
"""
import math
import numpy as np
import pandas as pd

import tdf_config as C
from tdf_engine import Daily, Engine, htf_ids, agg, rma_atr, isnan, NAN

W = dict(daily=25, h4=20, h1=20, ctrl=15, weekly=10, location=10)
TRIGGERS = ("ema8", "vwap", "ema21")
EXITS = {"1.5R": 1.5, "2R": 2.0, "3R": 3.0, "trail 8 EMA": None}


def ema(x, n):
    a = 2 / (n + 1)
    out = np.empty(len(x))
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def weekly_states(wb):
    """Weekly trend from 2/2 pivots, known once the week has closed (1 up, -1 down, 0 range / unknown)."""
    h, l = wb["h"].values, wb["l"].values
    n = len(h)
    st = np.zeros(n, int)
    ph, pl = [], []
    for k in range(n):
        j = k - 2
        if j >= 2:
            if h[j] > max(h[j - 2:j]) and h[j] >= max(h[j + 1:k + 1]):
                ph.append(h[j])
            if l[j] < min(l[j - 2:j]) and l[j] <= min(l[j + 1:k + 1]):
                pl.append(l[j])
        if len(ph) >= 2 and len(pl) >= 2:
            st[k] = 1 if (ph[-1] > ph[-2] and pl[-1] > pl[-2]) else -1 if (ph[-1] < ph[-2] and pl[-1] < pl[-2]) else 0
    return st


def bias_score(D, close, wk, ctrl, eA, eB):
    s = 0.0
    b = D.bias()
    s += W["daily"] * (b if D.st in (1, -1) else 0.4 * b)       # range edge counts 40%
    s += W["h4"] * eA.trend + W["h1"] * eB.trend + W["ctrl"] * ctrl + W["weekly"] * wk
    _, _, eq = D.dealing()
    if not isnan(eq):
        s += W["location"] * (1 if close < eq else -1)
    return s


def run_symbol_bias(df, symbol):
    df = df.sort_index()
    ids = htf_ids(df)
    bars = {k: agg(df, ids[k].values, C.ATR_LEN if k == "D" else 14) for k in ids}
    pos = {k: bars[k].index.get_indexer(ids[k].values) for k in ids}
    wst = weekly_states(bars["W"])
    O, H, L, Cl = (df[c].values.astype(float) for c in ("open", "high", "low", "close"))
    V = df["volume"].values.astype(float)
    T = df.index
    n = len(df)
    atr = rma_atr(H, L, Cl, 14)
    e8, e21 = ema(Cl, 8), ema(Cl, 21)
    day = ids["D"].values
    mins = (T.hour * 60 + T.minute).values
    # session VWAP (typical price)
    tp = (H + L + Cl) / 3
    vwap = np.empty(n)
    cpv = cv = 0.0
    for i in range(n):
        if i == 0 or day[i] != day[i - 1]:
            cpv = cv = 0.0
        cpv += tp[i] * V[i]
        cv += V[i]
        vwap[i] = cpv / cv if cv > 0 else tp[i]
    lvl = {"ema8": e8, "vwap": vwap, "ema21": e21}
    # last bar index of each day (for the forward walk)
    day_end = np.zeros(n, int)
    last = n - 1
    for i in range(n - 1, -1, -1):
        if i < n - 1 and day[i] != day[i + 1]:
            last = i
        day_end[i] = last

    D = Daily()
    liqs = []
    eA, eB = Engine("4H", liqs), Engine("1H", liqs)
    ctrl = 0
    wk = 0
    sig = []
    for i in range(n):
        if i > 0 and pos["D"][i] != pos["D"][i - 1] and pos["D"][i] >= 1:
            r = bars["D"].iloc[pos["D"][i] - 1]
            D.step(r.h, r.l, r.c, r.atr)
        if i > 0 and pos["W"][i] != pos["W"][i - 1] and pos["W"][i] >= 1:
            wk = int(wst[pos["W"][i] - 1])
        newA = newB = False
        if i > 0 and pos["A"][i] != pos["A"][i - 1] and pos["A"][i] >= 1:
            r = bars["A"].iloc[pos["A"][i] - 1]
            eA.push(bars["A"].index[pos["A"][i] - 1], r.o, r.h, r.l, r.c, r.atr)
            newA = True
        if i > 0 and pos["B"][i] != pos["B"][i - 1] and pos["B"][i] >= 1:
            r = bars["B"].iloc[pos["B"][i] - 1]
            eB.push(bars["B"].index[pos["B"][i] - 1], r.o, r.h, r.l, r.c, r.atr)
            newB = True
        if newB:
            upOk = eB.ev == 3 if C.CTRL_NEEDS == "MSS" else eB.ev >= 2
            dnOk = eB.ev == -3 if C.CTRL_NEEDS == "MSS" else eB.ev <= -2
            if upOk and eA.bullTouchT is not None and (eA.bearTouchT is None or eA.bullTouchT >= eA.bearTouchT):
                ctrl = 1
            if dnOk and eA.bearTouchT is not None and (eA.bullTouchT is None or eA.bearTouchT >= eA.bullTouchT):
                ctrl = -1
        if newA:
            if ctrl == 1 and eA.bullBroken:
                ctrl = -1
            elif ctrl == -1 and eA.bearBroken:
                ctrl = 1
        liqs.clear()                                    # liquidity is not used by this model
        if i < 1 or isnan(atr[i]) or not (C.PB_WINDOW[0] <= mins[i] < C.PB_WINDOW[1]):
            continue
        score = bias_score(D, Cl[i], wk, ctrl, eA, eB)
        if score == 0:
            continue
        lg = score > 0
        trend_ok = (e8[i] > e21[i]) if lg else (e8[i] < e21[i])
        for tname in TRIGGERS:
            lv = lvl[tname]
            if lg:
                touch = L[i] <= lv[i] < Cl[i] and L[i - 1] > lv[i - 1]
            else:
                touch = H[i] >= lv[i] > Cl[i] and H[i - 1] < lv[i - 1]
            if not touch:
                continue
            ent = Cl[i]
            stp = (min(L[i], lv[i]) - C.PB_STOP_BUF * atr[i]) if lg else (max(H[i], lv[i]) + C.PB_STOP_BUF * atr[i])
            mr = C.MIN_STOP_PCT / 100 * ent
            if abs(ent - stp) < mr:
                stp = ent - mr if lg else ent + mr
            rsk = abs(ent - stp)
            cost = 2 * C.COST_PCT_PER_SIDE / 100 * ent / rsk
            j0, j1 = i + 1, day_end[i]
            row = dict(symbol=symbol, time=str(T[i]), date=str(T[i].date()), trigger=tname, side="long" if lg else "short",
                       bias=round(abs(score), 1), trend_ok=bool(trend_ok), bull_bar=bool(Cl[i] > O[i]) if lg else bool(Cl[i] < O[i]),
                       risk_pct=round(100 * rsk / ent, 3), cost_r=round(cost, 3))
            for ename, k in EXITS.items():
                r, jx = _walk(H, L, Cl, e8, mins, j0, j1, ent, stp, rsk, lg, k)
                row["r_" + ename] = round(r - cost, 3)
                row["exit_" + ename] = str(T[jx]) if jx is not None else str(T[i])
            sig.append(row)
    return sig


def _walk(H, L, Cl, e8, mins, j0, j1, ent, stp, rsk, lg, k):
    """Outcome in R (gross) and the exit bar. Stop first when a bar touches both."""
    if j0 > j1:
        return 0.0, None
    hs, ls, cs, es, ms = H[j0:j1 + 1], L[j0:j1 + 1], Cl[j0:j1 + 1], e8[j0:j1 + 1], mins[j0:j1 + 1]
    stop_hit = (ls <= stp) if lg else (hs >= stp)
    eod = ms >= C.EOD_MIN
    if k is not None:
        tgt = ent + k * rsk if lg else ent - k * rsk
        tgt_hit = (hs >= tgt) if lg else (ls <= tgt)
        trail = np.zeros(len(hs), bool)
    else:
        tgt_hit = np.zeros(len(hs), bool)
        trail = (cs < es) if lg else (cs > es)
    events = stop_hit | tgt_hit | trail | eod
    if not events.any():
        x = len(hs) - 1
        return ((cs[x] - ent) if lg else (ent - cs[x])) / rsk, j0 + x
    x = int(np.argmax(events))
    if stop_hit[x]:
        return -1.0, j0 + x
    if tgt_hit[x]:
        return float(k), j0 + x
    return ((cs[x] - ent) if lg else (ent - cs[x])) / rsk, j0 + x


def take(sig, threshold, triggers, ename, trend_filter=True, max_trades=3, max_losses=2):
    """Apply the rules a trader would: bias at least `threshold`, chosen triggers, one trade at a time per symbol,
    at most `max_trades` a day and none after `max_losses` losses that day."""
    if sig is None or len(sig) == 0:
        return sig
    s = sig[(sig["bias"] >= threshold) & sig["trigger"].isin(triggers)]
    if trend_filter:
        s = s[s["trend_ok"]]
    s = s.sort_values(["symbol", "time"]).drop_duplicates(["symbol", "time"])
    keep = []
    rcol, xcol = "r_" + ename, "exit_" + ename
    for sym, g in s.groupby("symbol", sort=False):
        busy_until, cur_day, nt, nl = "", "", 0, 0
        for idx, t, d, r, x in zip(g.index, g["time"], g["date"], g[rcol], g[xcol]):
            if d != cur_day:
                cur_day, nt, nl = d, 0, 0
            if t <= busy_until or nt >= max_trades or nl >= max_losses:
                continue
            keep.append(idx)
            busy_until = x
            nt += 1
            if r < 0:
                nl += 1
    return s.loc[keep]
