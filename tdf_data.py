"""5-minute and daily bars from Alpaca (SIP feed, split-adjusted), regular session only (9:30-16:00 New York).
Needs the repository secrets ALPACA_KEY_ID and ALPACA_SECRET_KEY (free Alpaca account).
Bars are cached in cache/<SYMBOL>_5m.csv.gz so a re-run only downloads what is new.
"""
import os
import time
import datetime as dt
import pandas as pd
import requests

URL = "https://data.alpaca.markets/v2/stocks/{sym}/bars"
NY = "America/New_York"


def _headers():
    k, s = os.environ.get("ALPACA_KEY_ID"), os.environ.get("ALPACA_SECRET_KEY")
    if not k or not s:
        raise SystemExit("Missing ALPACA_KEY_ID / ALPACA_SECRET_KEY repository secrets.")
    return {"APCA-API-KEY-ID": k, "APCA-API-SECRET-KEY": s}


def _fetch(sym, timeframe, start, end):
    rows, token = [], None
    while True:
        params = dict(timeframe=timeframe, start=start.isoformat(), end=end.isoformat(), limit=10000,
                      adjustment="all", feed="sip", sort="asc")
        if token:
            params["page_token"] = token
        for attempt in range(5):
            r = requests.get(URL.format(sym=sym), headers=_headers(), params=params, timeout=60)
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()
            break
        js = r.json()
        rows += js.get("bars") or []
        token = js.get("next_page_token")
        if not token:
            break
    if not rows:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = pd.DataFrame(rows).rename(columns={"t": "time", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
    df["time"] = pd.to_datetime(df["time"], utc=True).dt.tz_convert(NY)
    return df.set_index("time")[["open", "high", "low", "close", "volume"]]


def rth(df):
    m = df.index.hour * 60 + df.index.minute
    return df[(m >= 570) & (m < 960) & (df.index.dayofweek < 5)]


def bars_5m(sym, days):
    """Regular-session 5-minute bars for about `days` trading days, from the cache plus new downloads."""
    os.makedirs("cache", exist_ok=True)
    path = f"cache/{sym}_5m.csv.gz"
    end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=20)       # SIP data older than 15 minutes is free
    start = end - dt.timedelta(days=int(days * 7 / 5) + 10)
    old = None
    if os.path.exists(path):
        old = pd.read_csv(path, index_col=0)
        old.index = pd.to_datetime(old.index, utc=True).tz_convert(NY)
        if len(old) and old.index[0] <= start.astimezone(dt.timezone.utc) + dt.timedelta(days=5):
            start = old.index[-1].to_pydatetime().astimezone(dt.timezone.utc) + dt.timedelta(minutes=5)
        else:
            old = None
    new = _fetch(sym, "5Min", start, end)
    df = new if old is None else pd.concat([old, new])
    df = rth(df[~df.index.duplicated(keep="last")].sort_index())
    df.to_csv(path, compression="gzip")
    cutoff = df.index[-1] - pd.Timedelta(days=int(days * 7 / 5) + 3) if len(df) else None
    return df if cutoff is None else df[df.index >= cutoff]


def top_by_dollar_volume(symbols, n=10, lookback=20):
    end = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=20)
    start = end - dt.timedelta(days=45)
    scores = {}
    for s in symbols:
        try:
            d = _fetch(s, "1Day", start, end).tail(lookback)
            if len(d):
                scores[s] = float((d["close"] * d["volume"]).mean())
        except Exception as e:                      # one bad symbol must not stop the run
            print("skip", s, e)
    ranked = sorted(scores, key=scores.get, reverse=True)[:n]
    return ranked, scores
