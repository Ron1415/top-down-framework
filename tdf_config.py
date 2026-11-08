"""Settings for the Top-Down Framework backtest (same rules and defaults as Top_Down_Framework.pine).
Edit on GitHub (pencil icon), then run the workflow "TDF backtest".
"""

# ----------------------------------------------------------------- symbols (3 groups x 10)
# Stocks: the 10 largest by 20-day average dollar volume on the run date, picked from these candidates.
STOCK_CANDIDATES = [
    "NVDA", "TSLA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "AMD", "AVGO", "NFLX",
    "PLTR", "MU", "COIN", "MSTR", "SMCI", "INTC", "ORCL", "CRM", "UNH", "LLY",
    "JPM", "BAC", "XOM", "WMT", "COST", "BA", "UBER", "SHOP", "ADBE", "QCOM",
]
# Futures, tested through the ETFs that track them (Alpaca has no futures data).
FUTURES_PROXIES = {
    "ES (S&P 500)": "SPY", "NQ (Nasdaq 100)": "QQQ", "YM (Dow)": "DIA", "RTY (Russell 2000)": "IWM",
    "GC (gold)": "GLD", "SI (silver)": "SLV", "CL (crude oil)": "USO", "NG (natural gas)": "UNG",
    "6E (euro)": "FXE", "6J (yen)": "FXY",
}
ETFS = ["SPY", "QQQ", "IWM", "TLT", "XLF", "XLK", "SMH", "XLE", "XLV", "EEM"]

# ----------------------------------------------------------------- 1. HTF (daily)
ATR_LEN = 14
SWING_MULT = 2.0        # daily swing = a reversal of at least 2 x daily ATR
EQ_TOL = 0.25           # equal highs / lows within 0.25 x ATR
BOS_SRC = "Close"       # "Close" or "Wick"
BOS_MARGIN = 0.0
SR_TOL = 0.25           # S/R zone: two or more daily swing points within 0.25 x daily ATR
MAX_SR = 8
RANGE_EDGE = 0.25       # consolidation: trade only in the outer 25% of the range

# ----------------------------------------------------------------- 2. ATF (4-hour = A, 1-hour = B)
ATF_A_MIN = 240
ATF_B_MIN = 60
PIV_K = 2
DISP_MULT = 1.0         # displacement: a body of at least 1 x ATR
POI_MIN_GAP = 0.5       # POI FVG at least 0.5 x ATR
ZONE_LIFE = 120         # POI expires after 120 bars of its timeframe
MAX_ZONES = 10
CTRL_NEEDS = "MSS"      # "MSS" or "CHoCH or MSS"
MAX_LIQ = 24

# ----------------------------------------------------------------- 3. ETF (5-minute)
WINDOW = (570, 690)     # New York window 9:30-11:30 (minutes after midnight NY)
ENT_GAP = 0.5           # entry FVG at least 0.5 x ATR
FILL_AT = "Near edge"   # "Near edge", "50% of the gap" or "Far edge"
EXPIRY_BARS = 12
STOP_BUF = 0.1
MIN_STOP_PCT = 0.20
MIN_RR = 2.0
MAX_TRADES = 2
MAX_LOSSES = 2
EOD_MIN = 955           # close open trades at 15:55 NY
V_BARS = 6

# ----------------------------------------------------------------- costs and reporting
COST_PCT_PER_SIDE = 0.02        # % of price per side (commission + slippage), as in earlier backtests
SPLIT_DATE = "2025-01-01"       # results before / after this date are reported separately
WORKERS = 4

# ----------------------------------------------------------------- variants (each = the core rules with some settings changed)
# SKIP_CHECKS removes checklist rows at the MSS (2 = premium / discount, 3 = who is in control, 4 = ATF trend).
SKIP_CHECKS = set()
RUNS = {
    "core": {},
    "control on a 1H CHoCH": {"CTRL_NEEDS": "CHoCH or MSS"},
    "without check 3 (control)": {"SKIP_CHECKS": {3}},
    "without check 2 (premium / discount)": {"SKIP_CHECKS": {2}},
    "Target 1 at least 1.5R": {"MIN_RR": 1.5},
    "fill at 50% of the gap": {"FILL_AT": "50% of the gap"},
    "displacement 0.7 ATR": {"DISP_MULT": 0.7},
    "relaxed: without checks 2 and 3, T1 1.5R": {"SKIP_CHECKS": {2, 3}, "MIN_RR": 1.5},
}
