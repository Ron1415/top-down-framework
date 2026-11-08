# Top-Down Framework backtest

Run 2026-11-08 20:06 UTC. 5-minute regular-session bars, about 1250 trading days requested; trades from 2022-04-08 to 2026-10-12. Results are in R, net of 0.02% per side unless marked gross. Rules and defaults are the same as Top_Down_Framework.pine.

Futures are tested through the ETFs that track them (regular session only). SPY, QQQ and IWM are in both the futures and ETF groups. The stock list is today's top 10 by dollar volume, which flatters the past (those stocks are known winners).

**Detailed sections 1 and 3-6 describe the run "L6: L5 + T1 at least 1.5R"**, picked as the best average among runs with at least 150 trades. Picking the best of several runs flatters it, so treat its numbers as an upper bound.

## 1. Groups, best first (L6: L5 + T1 at least 1.5R)

| group | trades | trades_per_month | win_pct | avg_r | avg_r_gross | total_r | pf | max_dd_r | t | avg_r_before_split | avg_r_after_split | avg_r_last_6m |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ETFs | 13 | 0.2 | 46.2 | -0.081 | 0.063 | -1.1 | 0.86 | -4.4 | -0.24 | -0.087 | -0.07 | -0.009 |
| Futures (ETF proxies) | 10 | 0.2 | 20.0 | -0.605 | -0.438 | -6.0 | 0.24 | -4.8 | -1.96 | -0.68 | -0.491 | -0.109 |
| Stocks | 12 | 0.2 | 16.7 | -0.635 | -0.542 | -7.6 | 0.14 | -6.5 | -3.14 | -0.806 | -0.121 | -0.722 |

Split date 2025-01-01. A group is worth trading only if avg_r is positive net of costs, t is about 2 or more, and both halves and the last 6 months are positive.

## 2. All runs: avg R net (trades, t)

| run | Stocks | Futures (ETF proxies) | ETFs |
|---|---|---|---|
| core | - | - | - |
| L1: checks 3 and 4 graded only | - | -1.12 (2, t -17.85) | - |
| L2: L1 + T1 = daily target | - | - | - |
| L3: L2 + fill at 50% of the gap | - | - | - |
| L4: L3 + window to 15:00 | -0.80 (11, t -6.07) | -0.91 (10, t -6.06) | -0.26 (10, t -0.7) |
| L5: L4 + displacement 0.7 ATR | -0.80 (10, t -5.49) | -0.60 (10, t -1.96) | -0.04 (11, t -0.11) |
| L6: L5 + T1 at least 1.5R | -0.64 (12, t -3.14) | -0.60 (10, t -1.96) | -0.08 (13, t -0.24) |
| only: T1 = daily target | - | - | - |
| only: fill at the far edge | +3.00 (1, t None) | - | - |
| only: window to 15:00 | - | -0.67 (2, t -1.31) | - |
| only: displacement 0.7 ATR | - | - | - |

The core rules are the framework as written. A variant that does much better in every group points to a rule that is too strict; check it in both halves before adopting it.

## 3. Symbols (L6: L5 + T1 at least 1.5R)

| group | symbol | trades | win_pct | avg_r | total_r | pf | max_dd_r | t |
|---|---|---|---|---|---|---|---|---|
| Stocks | MU | 1 | 0.0 | -1.034 | -1.0 | 0.0 | 0.0 |  |
| Stocks | NVDA | 1 | 0.0 | -0.562 | -0.6 | 0.0 | 0.0 |  |
| Stocks | AAPL | 3 | 33.3 | -0.229 | -0.7 | 0.63 | -0.7 | -0.33 |
| Stocks | META | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | TSLA | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | AMD | 2 | 50.0 | -0.508 | -1.0 | 0.06 | -1.1 | -0.89 |
| Stocks | MSFT | 2 | 0.0 | -0.945 | -1.9 | 0.0 | -0.8 | -6.22 |
| Stocks | AMZN | 2 | 0.0 | -0.646 | -1.3 | 0.0 | -1.2 | -1.17 |
| Stocks | GOOGL | 0 |  |  | 0.0 |  | 0.0 |  |
| Stocks | INTC | 1 | 0.0 | -1.133 | -1.1 | 0.0 | 0.0 |  |
| Futures (ETF proxies) | ES (S&P 500) via SPY | 1 | 0.0 | -0.28 | -0.3 | 0.0 | 0.0 |  |
| Futures (ETF proxies) | NQ (Nasdaq 100) via QQQ | 1 | 0.0 | -1.2 | -1.2 | 0.0 | 0.0 |  |
| Futures (ETF proxies) | YM (Dow) via DIA | 2 | 50.0 | 0.316 | 0.6 | 1.53 | -1.2 | 0.21 |
| Futures (ETF proxies) | RTY (Russell 2000) via IWM | 1 | 0.0 | -1.2 | -1.2 | 0.0 | 0.0 |  |
| Futures (ETF proxies) | GC (gold) via GLD | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | SI (silver) via SLV | 2 | 50.0 | -0.568 | -1.1 | 0.05 | 0.0 | -0.9 |
| Futures (ETF proxies) | CL (crude oil) via USO | 3 | 0.0 | -0.954 | -2.9 | 0.0 | -1.7 | -4.65 |
| Futures (ETF proxies) | NG (natural gas) via UNG | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | 6E (euro) via FXE | 0 |  |  | 0.0 |  | 0.0 |  |
| Futures (ETF proxies) | 6J (yen) via FXY | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | SPY | 1 | 0.0 | -0.28 | -0.3 | 0.0 | 0.0 |  |
| ETFs | QQQ | 1 | 0.0 | -1.2 | -1.2 | 0.0 | 0.0 |  |
| ETFs | IWM | 1 | 0.0 | -1.2 | -1.2 | 0.0 | 0.0 |  |
| ETFs | TLT | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | XLF | 2 | 0.0 | -1.142 | -2.3 | 0.0 | -1.2 | -24.55 |
| ETFs | XLK | 1 | 100.0 | 2.089 | 2.1 |  | 0.0 |  |
| ETFs | SMH | 3 | 66.7 | 0.443 | 1.3 | 2.15 | 0.0 | 0.47 |
| ETFs | XLE | 0 |  |  | 0.0 |  | 0.0 |  |
| ETFs | XLV | 3 | 66.7 | -0.147 | -0.4 | 0.63 | -1.2 | -0.28 |
| ETFs | EEM | 1 | 100.0 | 0.926 | 0.9 |  | 0.0 |  |

## 4. By year, L6: L5 + T1 at least 1.5R (avg R net, trades)

| group | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| Stocks | -0.78 (3) | -0.90 (3) | -0.74 (3) | +0.18 (2) | -0.72 (1) |
| Futures (ETF proxies) |  | -1.20 (1) | -0.58 (5) | -0.87 (2) | -0.11 (2) |
| ETFs | -0.30 (2) | +1.01 (3) | -0.80 (4) | -0.13 (2) | -0.01 (2) |

## 5. Long vs short, and the optional confluences, L6: L5 + T1 at least 1.5R (avg R net, trades)

| group | long | short | v_shape | no_v_shape | double_sweep | t1_hit_pct |
|---|---|---|---|---|---|---|
| Stocks | -0.36 (6) | -0.90 (6) | -0.58 (6) | -0.69 (6) | -0.09 (1) | 0.0 |
| Futures (ETF proxies) | -0.44 (4) | -0.71 (6) | -1.20 (3) | -0.35 (7) | -0.13 (4) | 10.0 |
| ETFs | +0.02 (7) | -0.20 (6) | +0.09 (8) | -0.36 (5) | +0.44 (2) | 7.7 |

## 6. Exits, L6: L5 + T1 at least 1.5R (share of trades)

| group | stop | T1 then breakeven | final target | end of day | stop on fill bar |
|---|---|---|---|---|---|
| Stocks | 50.0 |  |  | 50.0 |  |
| Futures (ETF proxies) | 60.0 |  |  | 40.0 |  |
| ETFs | 38.5 |  |  | 53.8 | 7.7 |

## 7. Setup funnel, core (all symbols, counted once)

POIs reached 6261 -> sweeps 1260 -> MSS 116 (CHoCH without displacement 184) -> orders 3 -> fills 0. Not filled 3; POI failed 2484; window closed 848.

Checks that blocked an MSS (one MSS can fail several): check 1: 0, check 2: 26, check 3: 66, check 4: 89, check 6: 107, check 11: 0.


## 8. MSS diagnostics, core (every MSS, all symbols)

MSS: 116. Median risk 0.76% of price; median gap 0.80 ATR; median strongest body 1.32 ATR; median 6 bars from the sweep. A fresh opposing zone sat before T1 in 57.8%.

| fill | median R to nearest pool | share >= 2R (nearest pool) | median R to daily target | share >= 2R (daily target) |
|---|---|---|---|---|
| near edge | 0.94 | 25.9 | 1.94 | 48.3 |
| 50% of the gap | 1.38 | 34.5 | 2.45 | 57.8 |
| far edge | 2.02 | 51.7 | 3.22 | 73.3 |

Share of MSS passing each check (%): check 1 100.0, check 2 77.6, check 3 43.1, check 4 23.3, check 6 7.8, check 11 100.0.

Every MSS is in results/mss_log.csv.gz (all runs, with a run column).


Stocks picked (20-day average dollar volume, $M): MU 26,152, NVDA 24,546, AAPL 16,781, META 16,539, TSLA 15,189, AMD 13,986, MSFT 13,744, AMZN 12,297, GOOGL 11,978, INTC 10,968

