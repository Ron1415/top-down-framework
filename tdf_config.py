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
FOCUS_MIN_TRADES = 150          # the detailed sections use the run with the best avg R among runs with this many trades

# ----------------------------------------------------------------- variants (each = the core rules with some settings changed)
# SKIP_CHECKS removes checklist rows at the MSS (2 = premium / discount, 3 = who is in control, 4 = ATF trend).
SKIP_CHECKS = set()
T1_MODE = "nearest pool"        # "nearest pool" (as in the Pine file) or "daily target" (the next daily-scale pool)
RUNS = {
    "core": {},
    # ---- ladder: each step keeps the previous changes
    "L1: checks 3 and 4 graded only": {"SKIP_CHECKS": {3, 4}},
    "L2: L1 + T1 = daily target": {"SKIP_CHECKS": {3, 4}, "T1_MODE": "daily target"},
    "L3: L2 + fill at 50% of the gap": {"SKIP_CHECKS": {3, 4}, "T1_MODE": "daily target", "FILL_AT": "50% of the gap"},
    "L4: L3 + window to 15:00": {"SKIP_CHECKS": {3, 4}, "T1_MODE": "daily target", "FILL_AT": "50% of the gap",
                                 "WINDOW": (570, 900)},
    "L5: L4 + displacement 0.7 ATR": {"SKIP_CHECKS": {3, 4}, "T1_MODE": "daily target", "FILL_AT": "50% of the gap",
                                      "WINDOW": (570, 900), "DISP_MULT": 0.7},
    "L6: L5 + T1 at least 1.5R": {"SKIP_CHECKS": {3, 4}, "T1_MODE": "daily target", "FILL_AT": "50% of the gap",
                                  "WINDOW": (570, 900), "DISP_MULT": 0.7, "MIN_RR": 1.5},
    # ---- single changes from the core
    "only: T1 = daily target": {"T1_MODE": "daily target"},
    "only: fill at the far edge": {"FILL_AT": "Far edge"},
    "only: window to 15:00": {"WINDOW": (570, 900)},
    "only: displacement 0.7 ATR": {"DISP_MULT": 0.7},
}

# ----------------------------------------------------------------- bias-score + pullback model (bias_backtest.py)
PB_WINDOW = (585, 900)          # entries 9:45-15:00 New York (VWAP needs 15 minutes to settle)
PB_STOP_BUF = 0.1               # stop beyond the pullback bar and the level by 0.1 x ATR (minimum MIN_STOP_PCT)
PB_DEFAULT = dict(threshold=60, triggers=("ema8", "vwap"), exit="2R", trend=True)   # the headline version
PB_THRESHOLDS = (40, 50, 60, 70, 80)
PB_TRIGGER_SETS = {"8 EMA": ("ema8",), "VWAP": ("vwap",), "21 EMA": ("ema21",), "8 EMA or VWAP": ("ema8", "vwap")}
