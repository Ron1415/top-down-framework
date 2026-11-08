"""Backtest the Top-Down Framework on 3 groups x 10 symbols and rank the groups.

    python tdf_backtest.py --days 1250            # about 5 years (needs Alpaca secrets)
    python tdf_backtest.py --synthetic            # offline check on simulated bars

Writes results/review.md (the report), results/summary.json, results/trades.csv.gz and results/funnel.csv.
"""
import argparse
import json
import math
import os
import datetime as dt
from multiprocessing import Pool

import numpy as np
import pandas as pd

import tdf_config as C
import tdf_engine as E


def stats(r):
    r = pd.Series(r, dtype=float)
    n = len(r)
    if n == 0:
        return dict(trades=0, win_pct=None, avg_r=None, total_r=0.0, pf=None, max_dd_r=0.0, t=None)
    eq = r.cumsum()
    dd = float((eq - eq.cummax()).min())
    wins, losses = r[r > 0].sum(), -r[r < 0].sum()
    sd = r.std(ddof=1) if n > 1 else float("nan")
    return dict(trades=n, win_pct=round(100 * (r > 0).mean(), 1), avg_r=round(r.mean(), 3), total_r=round(r.sum(), 1),
                pf=round(wins / losses, 2) if losses > 0 else None, max_dd_r=round(dd, 1),
                t=round(r.mean() / (sd / math.sqrt(n)), 2) if n > 1 and sd > 0 else None)


def synthetic(sym, days, seed):
    """Random-walk 5-minute bars with trends and ranges, for an offline end-to-end check."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end="2026-11-06", periods=days, tz="America/New_York")
    times = [d + pd.Timedelta(minutes=570 + 5 * k) for d in idx for k in range(78)]
    n = len(times)
    regime = np.repeat(rng.choice([-1, 0, 1], size=n // 780 + 1), 780)[:n]
    ret = 0.0004 * regime + rng.standard_t(4, n) * 0.0018
    close = 100 * np.exp(np.cumsum(ret))
    opn = np.r_[100, close[:-1]] * (1 + rng.normal(0, 0.0004, n))
    hi = np.maximum(opn, close) * (1 + np.abs(rng.normal(0, 0.0012, n)))
    lo = np.minimum(opn, close) * (1 - np.abs(rng.normal(0, 0.0012, n)))
    return pd.DataFrame({"open": opn, "high": hi, "low": lo, "close": close, "volume": 1e5}, index=pd.DatetimeIndex(times))


DEFAULTS = {k: getattr(C, k) for k in ("CTRL_NEEDS", "SKIP_CHECKS", "MIN_RR", "FILL_AT", "DISP_MULT")}


def work(job):
    run, sym, df = job
    for k, v in DEFAULTS.items():
        setattr(C, k, v)
    for k, v in C.RUNS[run].items():
        setattr(C, k, v)
    if df is None or len(df) < 2000:
        return run, sym, [], None, 0
    trades, fun = E.run_symbol(df, sym, "")
    return run, sym, trades, fun, df.index.normalize().nunique()


def table(rows, cols):
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join("" if r.get(c) is None else str(r.get(c)) for c in cols) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1250)
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()

    # ---- symbols
    if a.synthetic:
        stocks = ["STK%d" % k for k in range(10)]
        scores = {}
    else:
        import tdf_data as Dt
        stocks, scores = Dt.top_by_dollar_volume(C.STOCK_CANDIDATES, 10)
    groups = {"Stocks": stocks, "Futures (ETF proxies)": list(C.FUTURES_PROXIES.values()), "ETFs": list(C.ETFS)}
    uniq = sorted(set(sum(groups.values(), [])))
    print("symbols:", groups)

    # ---- data (downloaded one symbol at a time), then the rules in parallel
    jobs = []
    for k, s in enumerate(uniq):
        try:
            df = synthetic(s, min(a.days, 260), k) if a.synthetic else Dt.bars_5m(s, a.days)
        except Exception as e:
            print("data error", s, e)
            df = None
        print(s, 0 if df is None else len(df), "bars")
        jobs.append((s, df))
    with Pool(C.WORKERS) as p:
        res = p.map(work, [(run, s, df) for run in C.RUNS for s, df in jobs])
    by_run = {run: {} for run in C.RUNS}
    for run, s, t, f, nd in res:
        by_run[run][s] = (t, f, nd)
    by_sym = by_run["core"]

    # ---- trades table (a symbol in two groups is counted in both)
    rows = []
    for run in C.RUNS:
        for g, syms in groups.items():
            for s in syms:
                for t in by_run[run].get(s, ([], None, 0))[0]:
                    rows.append(dict(t, group=g, run=run))
    allt = pd.DataFrame(rows)
    tr = allt[allt["run"] == "core"].copy() if len(allt) else allt
    os.makedirs("results", exist_ok=True)
    if len(tr):
        tr = tr.sort_values("exit_time")
    if len(allt):
        allt.sort_values(["run", "exit_time"]).to_csv("results/trades.csv.gz", index=False, compression="gzip")
    funnel = pd.DataFrame({s: v[1] for s, v in by_sym.items() if v[1] is not None}).T
    funnel.to_csv("results/funnel.csv")

    # ---- report
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    first = tr["date"].min() if len(tr) else "-"
    last = tr["date"].max() if len(tr) else "-"
    md = [f"# Top-Down Framework backtest\n",
          f"Run {now}{' (SYNTHETIC DATA: pipeline check only)' if a.synthetic else ''}. 5-minute regular-session bars, "
          f"about {a.days} trading days requested; trades from {first} to {last}. Results are in R, net of "
          f"{C.COST_PCT_PER_SIDE}% per side unless marked gross. Rules and defaults are the same as Top_Down_Framework.pine.\n",
          "Futures are tested through the ETFs that track them (regular session only). SPY, QQQ and IWM are in both the "
          "futures and ETF groups. The stock list is today's top 10 by dollar volume, which flatters the past "
          "(those stocks are known winners).\n"]

    summ = {"run": now, "synthetic": a.synthetic, "groups": {}, "symbols": {}}
    grows = []
    for g, syms in groups.items():
        sub = tr[tr["group"] == g] if len(tr) else pd.DataFrame()
        sessions = sum(by_sym.get(s, ([], None, 0))[2] for s in syms)
        st = stats(sub["r_net"]) if len(sub) else stats([])
        st_g = stats(sub["r_gross"]) if len(sub) else stats([])
        months = max(1.0, sessions / 21 / max(1, len(syms)))
        row = dict(group=g, **st, avg_r_gross=st_g["avg_r"], trades_per_month=round(st["trades"] / months, 1))
        if len(sub):
            pre = sub[sub["date"] < C.SPLIT_DATE]["r_net"]
            post = sub[sub["date"] >= C.SPLIT_DATE]["r_net"]
            cut6 = (pd.Timestamp(last) - pd.DateOffset(months=6)).strftime("%Y-%m-%d")
            row.update(avg_r_before_split=stats(pre)["avg_r"], avg_r_after_split=stats(post)["avg_r"],
                       avg_r_last_6m=stats(sub[sub["date"] >= cut6]["r_net"])["avg_r"])
        grows.append(row)
        summ["groups"][g] = row
    ranked = sorted(grows, key=lambda r: (r["avg_r"] is None, -(r["avg_r"] or 0)))
    md.append("## 1. Groups, best first (core rules)\n")
    md.append(table(ranked, ["group", "trades", "trades_per_month", "win_pct", "avg_r", "avg_r_gross", "total_r", "pf",
                             "max_dd_r", "t", "avg_r_before_split", "avg_r_after_split", "avg_r_last_6m"]))
    md.append(f"\nSplit date {C.SPLIT_DATE}. A group is worth trading only if avg_r is positive net of costs, t is about 2 "
              "or more, and both halves and the last 6 months are positive.\n")

    md.append("## 2. Variants: the same test with one rule changed (avg R net, trades)\n")
    vrows = []
    for run in C.RUNS:
        sub = allt[allt["run"] == run] if len(allt) else pd.DataFrame()
        r = {"run": run}
        for g in groups:
            x = sub[sub["group"] == g]["r_net"] if len(sub) else []
            st = stats(x)
            r[g] = "-" if not st["trades"] else f"{st['avg_r']:+.2f} ({st['trades']}, t {st['t']})"
        vrows.append(r)
        summ.setdefault("variants", {})[run] = r
    md.append(table(vrows, ["run"] + list(groups)))
    md.append("\nThe core rules are the framework as written. A variant that does much better in every group points to "
              "a rule that is too strict; check it in both halves before adopting it.\n")

    md.append("## 3. Symbols (core)\n")
    srows = []
    for g, syms in groups.items():
        for s in syms:
            sub = tr[(tr["group"] == g) & (tr["symbol"] == s)] if len(tr) else pd.DataFrame()
            st = stats(sub["r_net"]) if len(sub) else stats([])
            name = s
            if g.startswith("Futures"):
                name = next(k for k, v in C.FUTURES_PROXIES.items() if v == s) + " via " + s
            srows.append(dict(group=g, symbol=name, **st))
            summ["symbols"][f"{g}|{s}"] = st
    md.append(table(srows, ["group", "symbol", "trades", "win_pct", "avg_r", "total_r", "pf", "max_dd_r", "t"]))

    if len(tr):
        md.append("\n## 4. By year, core (avg R net, trades)\n")
        tr["year"] = tr["date"].str[:4]
        yrows = []
        for g in groups:
            r = {"group": g}
            for y, sub in tr[tr["group"] == g].groupby("year"):
                r[y] = f"{sub['r_net'].mean():+.2f} ({len(sub)})"
            yrows.append(r)
        md.append(table(yrows, ["group"] + sorted(tr["year"].unique())))
        md.append("\n## 5. Long vs short, and the optional confluences, core (avg R net, trades)\n")
        crows = []
        for g in groups:
            sub = tr[tr["group"] == g]
            f = lambda x: f"{x['r_net'].mean():+.2f} ({len(x)})" if len(x) else "-"
            crows.append(dict(group=g, long=f(sub[sub.side == "long"]), short=f(sub[sub.side == "short"]),
                              v_shape=f(sub[sub.v_shape]), no_v_shape=f(sub[~sub.v_shape]),
                              double_sweep=f(sub[sub.double_sweep]), t1_hit_pct=round(100 * sub.t1_hit.mean(), 1) if len(sub) else None))
        md.append(table(crows, ["group", "long", "short", "v_shape", "no_v_shape", "double_sweep", "t1_hit_pct"]))
        md.append("\n## 6. Exits, core (share of trades)\n")
        erows = []
        for g in groups:
            sub = tr[tr["group"] == g]
            vc = (100 * sub["exit"].value_counts(normalize=True)).round(1).to_dict()
            erows.append(dict(group=g, **vc))
        md.append(table(erows, ["group", "stop", "T1 then breakeven", "final target", "end of day", "stop on fill bar"]))

    md.append("\n## 7. Setup funnel, core (all symbols, counted once)\n")
    if len(funnel):
        tot = funnel.sum().astype(int).to_dict()
        md.append(f"POIs reached {tot.get('poi', 0)} -> sweeps {tot.get('sweep', 0)} -> MSS {tot.get('mss', 0)} "
                  f"(CHoCH without displacement {tot.get('choch', 0)}) -> orders {tot.get('order', 0)} -> fills {tot.get('fill', 0)}. "
                  f"Not filled {tot.get('not_filled', 0)}; POI failed {tot.get('poi_failed', 0)}; window closed {tot.get('window_closed', 0)}.\n")
        md.append("Checks that blocked an MSS (one MSS can fail several): " + ", ".join(
            f"check {c}: {tot.get('fail_%d' % c, 0)}" for c in (1, 2, 3, 4, 6, 11)) + ".\n")
        summ["funnel"] = tot
    if scores:
        md.append("\nStocks picked (20-day average dollar volume, $M): " + ", ".join(
            f"{s} {scores[s] / 1e6:,.0f}" for s in stocks) + "\n")
    open("results/review.md", "w").write("\n".join(md) + "\n")
    json.dump(summ, open("results/summary.json", "w"), indent=1, default=str)
    print("\n".join(md))


if __name__ == "__main__":
    main()
