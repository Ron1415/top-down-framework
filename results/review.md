# Top-Down Framework backtest

Run 2026-11-08 19:46 UTC. 5-minute regular-session bars, about 1250 trading days requested; trades from - to -. Results are in R, net of 0.02% per side unless marked gross. Rules and defaults are the same as Top_Down_Framework.pine.

Futures are tested through the ETFs that track them (regular session only). SPY, QQQ and IWM are in both the futures and ETF groups. The stock list is today's top 10 by dollar volume, which flatters the past (those stocks are known winners).

## 1. Groups, best first (core rules)

| group | trades | trades_per_month | win_pct | avg_r | avg_r_gross | total_r | pf | max_dd_r | t | avg_r_before_split | avg_r_after_split | avg_r_last_6m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Stocks | 0 | 0.0 |  |  |  | 0.0 |  | 0.0 |  |  |  |  |
| Futures (ETF proxies) | 0 | 0.0 |  |  |  | 0.0 |  | 0.0 |  |  |  |  |
| ETFs | 0 | 0.0 |  |  |  | 0.0 |  | 0.0 |  |  |  |  |

Split date 2025-01-01. A group is worth trading only if avg_r is positive net of costs, t is about 2 or more, and both halves and the last 6 months are positive.

## 2. Variants: the same test with one rule changed (avg R net, trades)

| run | Stocks | Futures (ETF proxies) | ETFs |
|---|---|---|---|
| core | - | - | - |
| control on a 1H CHoCH | - | - | - |
| without check 3 (control) | - | - | - |
| without check 2 (premium / discount) | - | - | - |
| Target 1 at least 1.5R | - | - | - |
| fill at 50% of the gap | - | - | - |
| displacement 0.7 ATR | - | - | - |
| relaxed: without checks 2 and 3, T1 1.5R | - | - | - |

The core rules are the framework as written. A variant that does much better in every group points to a rule that is too strict; check it in both halves before adopting it.

## 3. Symbols (core)

| group | symbol | trades | win_pct | avg_r | total_r | pf | max_dd_r | t |
|---|---|---|---|---|---|---|---|---|
| Stocks | MU | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | NVDA | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | AAPL | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | META | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | TSLA | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | AMD | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | MSFT | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | AMZN | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | GOOGL | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | INTC | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | ES (S&P 500) via SPY | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | NQ (Nasdaq 100) via QQQ | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | YM (Dow) via DIA | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | RTY (Russell 2000) via IWM | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | GC (gold) via GLD | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | SI (silver) via SLV | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | CL (crude oil) via USO | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | NG (natural gas) via UNG | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | 6E (euro) via FXE | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | 6J (yen) via FXY | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | SPY | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | QQQ | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | IWM | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | TLT | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | XLF | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | XLK | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | SMH | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | XLE | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | XLV | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | EEM | 0 |  |  | 0.0 |  | 0.0 |  |

## 7. Setup funnel, core (all symbols, counted once)

POIs reached 6261 -> sweeps 1260 -> MSS 116 (CHoCH without displacement 184) -> orders 3 -> fills 0. Not filled 3; POI failed 2484; window closed 848.

Checks that blocked an MSS (one MSS can fail several): check 1: 0, check 2: 26, check 3: 66, check 4: 89, check 6: 107, check 11: 0.


Stocks picked (20-day average dollar volume, $M): MU 26,152, NVDA 24,546, AAPL 16,781, META 16,539, TSLA 15,189, AMD 13,986, MSFT 13,744, AMZN 12,297, GOOGL 11,978, INTC 10,968

