"""Backtest of the bias-score + pullback model on the same 3 groups x 10 symbols.

    python bias_backtest.py --days 1250
    python bias_backtest.py --synthetic

Writes results/pb_review.md, results/pb_summary.json and results/pb_signals.csv.gz (every signal, every exit).
"""
import argparse
import json
import datetime as dt
from multiprocessing import Pool

import pandas as pd

import tdf_config as C
import bias_engine as B
from tdf_backtest import stats, synthetic, table

BUCKETS = [(0, 30), (30, 50), (50, 60), (60, 70), (70, 80), (80, 90), (90, 101)]


def work(job):
    sym, df = job
    if df is None or len(df) < 2000:
        return sym, [], 0
    return sym, B.run_symbol_bias(df, sym), df.index.normalize().nunique()


def cell(x):
    st = stats(x)
    return "-" if not st["trades"] else f"{st['avg_r']:+.2f} ({st['trades']})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1250)
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()
    if a.synthetic:
        stocks, scores = ["STK%d" % k for k in range(10)], {}
    else:
        import tdf_data as Dt
        stocks, scores = Dt.top_by_dollar_volume(C.STOCK_CANDIDATES, 10)
    groups = {"Stocks": stocks, "Futures (ETF proxies)": list(C.FUTURES_PROXIES.values()), "ETFs": list(C.ETFS)}
    uniq = sorted(set(sum(groups.values(), [])))
    jobs = []
    for k, s in enumerate(uniq):
        try:
            df = synthetic(s, min(a.days, 260), k) if a.synthetic else Dt.bars_5m(s, a.days)
        except Exception as e:
            print("data error", s, e)
            df = None
        jobs.append((s, df))
    with Pool(C.WORKERS) as p:
        res = p.map(work, jobs)
    sig = pd.DataFrame([r for _, rows, _ in res for r in rows])
    sessions = {s: nd for s, _, nd in res}
    import os
    os.makedirs("results", exist_ok=True)
    if len(sig):
        sig.to_csv("results/pb_signals.csv.gz", index=False, compression="gzip")
    dflt = C.PB_DEFAULT
    dcol = "r_" + dflt["exit"]
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = [f"# Bias score + pullback backtest\n",
          f"Run {now}{' (SYNTHETIC DATA: pipeline check only)' if a.synthetic else ''}. Regular-session 5-minute bars; "
          f"signals from {sig['date'].min() if len(sig) else '-'} to {sig['date'].max() if len(sig) else '-'}. "
          f"R is net of {C.COST_PCT_PER_SIDE}% per side.\n",
          f"Bias score weights: daily structure {B.W['daily']}, 4H trend {B.W['h4']}, 1H trend {B.W['h1']}, in control {B.W['ctrl']}, "
          f"weekly {B.W['weekly']}, premium/discount {B.W['location']}. Entry: first touch of the level with a close back on the trend "
          f"side, 9:45-15:00, at the bar's close. Headline version: bias {dflt['threshold']}%+, {' or '.join(dflt['triggers'])}, "
          f"exit {dflt['exit']}, 5-minute 8 EMA above the 21 EMA (below for shorts), one trade at a time, 3 trades / 2 losses a day.\n"]
    summ = {"run": now, "synthetic": a.synthetic}
    if not len(sig):
        md.append("No signals.\n")
    else:
        # ---- 1. calibration: does a higher bias % give better trades? (every signal, before the one-at-a-time rule)
        md.append("## 1. Does a higher bias % give better trades? (every signal, 8 EMA or VWAP, trend filter on)\n")
        base = sig[sig["trigger"].isin(("ema8", "vwap")) & sig["trend_ok"]]
        crow = []
        for lo, hi in BUCKETS:
            b = base[(base["bias"] >= lo) & (base["bias"] < hi)]
            r = {"bias %": f"{lo}-{min(hi, 100)}", "signals": len(b)}
            for e in B.EXITS:
                r[e] = None if not len(b) else round(b["r_" + e].mean(), 3)
            r["win % (2R)"] = None if not len(b) else round(100 * (b["r_2R"] > 0).mean(), 1)
            crow.append(r)
        md.append(table(crow, ["bias %", "signals"] + list(B.EXITS) + ["win % (2R)"]))
        md.append("\nAvg R per signal. If the score works, the averages rise from the top rows to the bottom rows.\n")
        grow = []
        for g, syms in groups.items():
            r = {"group": g}
            for lo, hi in BUCKETS:
                b = base[base["symbol"].isin(syms) & (base["bias"] >= lo) & (base["bias"] < hi)]
                r[f"{lo}-{min(hi, 100)}"] = cell(b["r_2R"])
            grow.append(r)
        md.append("\nBy group, exit 2R (avg R, signals):\n")
        md.append(table(grow, ["group"] + [f"{lo}-{min(hi, 100)}" for lo, hi in BUCKETS]))

        # ---- 2. headline version by group
        md.append(f"\n## 2. Groups, best first (headline version)\n")
        rows = []
        for g, syms in groups.items():
            t = B.take(sig[sig["symbol"].isin(syms)], dflt["threshold"], dflt["triggers"], dflt["exit"], dflt["trend"])
            st = stats(t[dcol]) if len(t) else stats([])
            months = max(1.0, sum(sessions.get(s, 0) for s in syms) / 21 / len(syms))
            row = dict(group=g, **st, trades_per_month=round(st["trades"] / months, 1))
            if len(t):
                last = t["date"].max()
                cut6 = (pd.Timestamp(last) - pd.DateOffset(months=6)).strftime("%Y-%m-%d")
                row.update(before_split=stats(t[t["date"] < C.SPLIT_DATE][dcol])["avg_r"],
                           after_split=stats(t[t["date"] >= C.SPLIT_DATE][dcol])["avg_r"],
                           last_6m=stats(t[t["date"] >= cut6][dcol])["avg_r"])
            rows.append(row)
            summ.setdefault("groups", {})[g] = row
        rows.sort(key=lambda r: (r["avg_r"] is None, -(r["avg_r"] or 0)))
        md.append(table(rows, ["group", "trades", "trades_per_month", "win_pct", "avg_r", "total_r", "pf", "max_dd_r", "t",
                               "before_split", "after_split", "last_6m"]))
        md.append(f"\nSplit date {C.SPLIT_DATE}. Worth trading only if avg R is positive after costs, t is about 2 or more, "
                  "and both halves and the last 6 months are positive.\n")

        # ---- 3. the grid (all symbols)
        md.append("## 3. Grid: bias threshold x trigger x exit (all 27 symbols, trend filter on; avg R net, trades)\n")
        grid = []
        for th in C.PB_THRESHOLDS:
            for tn, trig in C.PB_TRIGGER_SETS.items():
                r = {"bias": f"{th}%+", "trigger": tn}
                for e in B.EXITS:
                    t = B.take(sig, th, trig, e, True)
                    r[e] = cell(t["r_" + e]) if len(t) else "-"
                grid.append(r)
        md.append(table(grid, ["bias", "trigger"] + list(B.EXITS)))
        md.append("\nThis grid holds 80 versions. The best cell is partly luck; prefer a region where neighbouring cells agree.\n")
        md.append("Without the trend filter (8 EMA or VWAP, all exits):\n")
        nt = []
        for th in C.PB_THRESHOLDS:
            r = {"bias": f"{th}%+"}
            for e in B.EXITS:
                t = B.take(sig, th, ("ema8", "vwap"), e, False)
                r[e] = cell(t["r_" + e]) if len(t) else "-"
            nt.append(r)
        md.append(table(nt, ["bias"] + list(B.EXITS)))

        # ---- 4-6. headline version detail
        hv = B.take(sig, dflt["threshold"], dflt["triggers"], dflt["exit"], dflt["trend"])
        md.append("\n## 4. Symbols (headline version)\n")
        srow = []
        for g, syms in groups.items():
            for s in syms:
                x = hv[hv["symbol"] == s][dcol] if len(hv) else []
                st = stats(x)
                nm = s if not g.startswith("Futures") else next(k for k, v in C.FUTURES_PROXIES.items() if v == s) + " via " + s
                srow.append(dict(group=g, symbol=nm, **st))
        md.append(table(srow, ["group", "symbol", "trades", "win_pct", "avg_r", "total_r", "pf", "max_dd_r", "t"]))
        if len(hv):
            md.append("\n## 5. By year (headline version; avg R, trades)\n")
            hv = hv.assign(year=hv["date"].str[:4])
            yr = []
            for g, syms in groups.items():
                r = {"group": g}
                for y, x in hv[hv["symbol"].isin(syms)].groupby("year"):
                    r[y] = cell(x[dcol])
                yr.append(r)
            md.append(table(yr, ["group"] + sorted(hv["year"].unique())))
            md.append("\n## 6. Long vs short, trigger and candle (headline version; avg R, trades)\n")
            lr = []
            for g, syms in groups.items():
                x = hv[hv["symbol"].isin(syms)]
                lr.append({"group": g, "long": cell(x[x.side == "long"][dcol]), "short": cell(x[x.side == "short"][dcol]),
                           "8 EMA": cell(x[x.trigger == "ema8"][dcol]), "VWAP": cell(x[x.trigger == "vwap"][dcol]),
                           "trend-colour bar": cell(x[x.bull_bar][dcol]), "other bar": cell(x[~x.bull_bar][dcol])})
            md.append(table(lr, ["group", "long", "short", "8 EMA", "VWAP", "trend-colour bar", "other bar"]))
    if scores:
        md.append("\nStocks picked (20-day average dollar volume, $M): " + ", ".join(f"{s} {scores[s] / 1e6:,.0f}" for s in stocks) + "\n")
    open("results/pb_review.md", "w").write("\n".join(md) + "\n")
    json.dump(summ, open("results/pb_summary.json", "w"), indent=1, default=str)
    print("\n".join(md))


if __name__ == "__main__":
    main()
