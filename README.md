# Top-Down Framework backtest

Python version of `Top_Down_Framework.pine` (HTF direction -> ATF structure and bias -> ETF confirmation and execution),
tested on three groups of 10: the top stocks by dollar volume, futures (through the ETFs that track them) and the top ETFs.

- `tdf_config.py`: symbols, rules (same defaults as the Pine file), costs and the variant runs.
- `tdf_engine.py`: the rules, bar by bar on regular-session 5-minute bars.
- `tdf_data.py`: Alpaca bars (secrets `ALPACA_KEY_ID`, `ALPACA_SECRET_KEY`).
- `tdf_backtest.py`: runs everything and writes `results/review.md`, `summary.json`, `trades.csv.gz`, `funnel.csv`.
- `test_tdf.py`: plumbing checks on simulated bars.
- `Top_Down_Framework.pine` / `Top_Down_Framework_Strategy.pine`: the TradingView indicator and strategy versions.

Run: Actions -> "TDF backtest" -> Run workflow. Educational research only; not financial advice.
