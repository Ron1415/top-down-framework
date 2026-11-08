"""Python port of Top_Down_Framework.pine (HTF -> ATF -> ETF), bar by bar on regular-session 5-minute bars.

The order of work on each 5-minute bar follows the Pine script:
  1. a new daily bar completed -> daily structure, S/R zones (same as request.security(..., [1], lookahead_on))
  2. dealing range, session bias, prior day / week levels
  3. a new 4-hour / 1-hour bar completed -> ATF engines (swings, liquidity, FVG / OB / breaker / mitigation / IFVG,
     BOS / CHoCH / MSS) and "who is in control"
  4. 5-minute swings, then the setup state machine on the closed bar (POI -> sweep -> MSS -> order -> trade)
  5. spent liquidity is removed
Drawings are left out; every rule that decides a trade is kept.
"""
import math
import numpy as np
import pandas as pd
import tdf_config as C

NAN = float("nan")


def isnan(x):
    return x is None or (isinstance(x, float) and math.isnan(x))


def rma_atr(h, l, c, n):
    """Pine ta.atr: RMA of the true range, seeded with the simple average of the first n values."""
    h, l, c = np.asarray(h, float), np.asarray(l, float), np.asarray(c, float)
    tr = h - l
    if len(c) > 1:
        pc = np.r_[np.nan, c[:-1]]
        tr = np.where(np.isnan(pc), h - l, np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc))))
    out = np.full(len(tr), np.nan)
    if len(tr) >= n:
        out[n - 1] = tr[:n].mean()
        for i in range(n, len(tr)):
            out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


# ================================================================ 1. HTF: daily structure
class Daily:
    def __init__(self):
        self.st = 0
        self.protLow = self.protHigh = NAN
        self.rangeHi = self.rangeLo = NAN
        self.dir = 0
        self.extP = NAN
        self.extB = 0
        self.h0 = self.h1 = self.l0 = self.l1 = NAN
        self.h1B = self.l1B = None
        self.nH = self.nL = 0
        self.H, self.L = [], []
        self.srs = []                       # dicts: top, bot, res
        self.swHP, self.swLP = [], []
        self.dC = NAN

    def _sr_make(self, top, bot, res):
        for s in self.srs:
            if s["top"] >= bot and s["bot"] <= top:
                s["top"], s["bot"] = max(s["top"], top), min(s["bot"], bot)
                return
        self.srs.append(dict(top=top, bot=bot, res=res))
        while len(self.srs) > C.MAX_SR:
            self.srs.pop(0)

    def _sr_check(self, ps, p, tol, res):
        for q in range(len(ps) - 1, max(0, len(ps) - 10) - 1, -1):
            if abs(ps[q] - p) <= tol:
                self._sr_make(max(ps[q], p), min(ps[q], p), res)
                break
        ps.append(p)

    def _enter_range(self, hi, lo):
        self.st, self.rangeHi, self.rangeLo = 2, hi, lo

    def step(self, hH, hL, hC, hA):
        self.H.append(hH)
        self.L.append(hL)
        self.dC = hC
        i = len(self.H) - 1
        newHigh = newLow = False
        swP, swB = NAN, None
        if self.dir == 0:
            self.dir, self.extP, self.extB = 1, hH, i
        elif self.dir == 1:
            if hH >= self.extP:
                self.extP, self.extB = hH, i
            elif not isnan(hA) and hL <= self.extP - C.SWING_MULT * hA:
                newHigh, swP, swB, self.dir = True, self.extP, self.extB, -1
                lo, lb = hL, i
                for j in range(self.extB + 1, i + 1):
                    if self.L[j] < lo:
                        lo, lb = self.L[j], j
                self.extP, self.extB = lo, lb
        else:
            if hL <= self.extP:
                self.extP, self.extB = hL, i
            elif not isnan(hA) and hH >= self.extP + C.SWING_MULT * hA:
                newLow, swP, swB, self.dir = True, self.extP, self.extB, 1
                hi, hb = hH, i
                for j in range(self.extB + 1, i + 1):
                    if self.H[j] > hi:
                        hi, hb = self.H[j], j
                self.extP, self.extB = hi, hb
        a = 0.0 if isnan(hA) else hA
        tol = C.EQ_TOL * a
        if newHigh:
            kind = "H" if self.nH == 0 else ("HH" if swP > self.h1 + tol else "LH" if swP < self.h1 - tol else "EQH")
            self._sr_check(self.swHP, swP, C.SR_TOL * a, True)
            prevH = self.h1
            self.h0, self.h1, self.h1B = self.h1, swP, swB
            self.nH += 1
            if self.st == 1 and kind != "HH":
                self._enter_range(max(prevH, swP), self.protLow)
            elif self.st == -1:
                if kind == "HH" and swP > self.protHigh:
                    self._enter_range(swP, self.l1)
                else:
                    self.protHigh = swP
            elif self.st == 2 and swP > self.rangeHi:
                self.rangeHi = swP
        if newLow:
            kind = "L" if self.nL == 0 else ("LL" if swP < self.l1 - tol else "HL" if swP > self.l1 + tol else "EQL")
            self._sr_check(self.swLP, swP, C.SR_TOL * a, False)
            prevL = self.l1
            self.l0, self.l1, self.l1B = self.l1, swP, swB
            self.nL += 1
            if self.st == -1 and kind != "LL":
                self._enter_range(self.protHigh, min(prevL, swP))
            elif self.st == 1:
                if kind == "LL" and swP < self.protLow:
                    self._enter_range(self.h1, swP)
                else:
                    self.protLow = swP
            elif self.st == 2 and swP < self.rangeLo:
                self.rangeLo = swP
        if self.st == 0 and self.nH >= 2 and self.nL >= 2 and (newHigh or newLow):
            if self.h1 > self.h0 and self.l1 > self.l0:
                self.st, self.protLow = 1, self.l1
            elif self.h1 < self.h0 and self.l1 < self.l0:
                self.st, self.protHigh = -1, self.h1
            else:
                self._enter_range(max(self.h0, self.h1), min(self.l0, self.l1))
        m = C.BOS_MARGIN * a
        upPx = hC if C.BOS_SRC == "Close" else hH
        dnPx = hC if C.BOS_SRC == "Close" else hL
        bosUp = bosDn = False
        if self.st == 1 and dnPx < self.protLow - m:
            bosDn = True
        elif self.st == -1 and upPx > self.protHigh + m:
            bosUp = True
        elif self.st == 2:
            if upPx > self.rangeHi + m:
                bosUp = True
            elif dnPx < self.rangeLo - m:
                bosDn = True
        if bosUp:
            self.st, self.protLow = 1, self.l1
        elif bosDn:
            self.st, self.protHigh = -1, self.h1
        for s in self.srs:
            if s["res"] and hC > s["top"]:
                s["res"] = False
            elif not s["res"] and hC < s["bot"]:
                s["res"] = True

    def dealing(self):
        if self.dir == 1:
            hi = max(self.extP if isnan(self.h1) else self.h1, self.extP)
            lo = self.l1
        else:
            hi = self.h1
            lo = min(self.extP if isnan(self.l1) else self.l1, self.extP)
        eq = (hi + lo) / 2 if not (isnan(hi) or isnan(lo)) else NAN
        return hi, lo, eq

    def bias(self):
        if self.st == 1:
            return 1
        if self.st == -1:
            return -1
        if self.st == 2 and self.rangeHi > self.rangeLo:
            pos = (self.dC - self.rangeLo) / (self.rangeHi - self.rangeLo)
            if pos <= C.RANGE_EDGE:
                return 1
            if pos >= 1 - C.RANGE_EDGE:
                return -1
        return 0


# ================================================================ 2. ATF engines
KIND = {1: "FVG", 2: "OB", 3: "Breaker", 4: "Mitigation", 5: "IFVG"}


class Engine:
    def __init__(self, tag, liqs):
        self.tag = tag
        self.liqs = liqs                 # shared list of dicts: p, hi, live, eq
        self.t, self.o, self.h, self.l, self.c, self.a = [], [], [], [], [], []
        self.zs = []                     # dicts: kind, bull, top, bot, t0, born, fresh, cause
        self.sh1 = self.sh0 = self.sl1 = self.sl0 = NAN
        self.sh1i = self.sl1i = None
        self.shDone = self.slDone = True
        self.trend = 0
        self.ev = 0
        self.lastEv = 0
        self.bullTouchT = self.bearTouchT = None
        self.bullBroken = self.bearBroken = False

    def _liq_add(self, p, hi, aa):
        eqv = any(o["live"] and o["hi"] == hi and abs(o["p"] - p) <= C.EQ_TOL * aa for o in self.liqs)
        self.liqs.append(dict(p=p, hi=hi, live=True, eq=eqv))
        while len(self.liqs) > C.MAX_LIQ:
            self.liqs.pop(0)

    def _z_add(self, kind, bull, top, bot, t0, cause):
        if top > bot:
            self.zs.append(dict(kind=kind, bull=bull, top=top, bot=bot, t0=t0, born=len(self.t) - 1, fresh=True, cause=cause))
            while len(self.zs) > C.MAX_ZONES:
                self.zs.pop(0)

    def _leg_ok(self, s, e, up):
        f = max(s, e - 40, 0)
        body_ok = gap_ok = False
        for m in range(f + 1, e + 1):
            aa = self.a[m]
            body = self.c[m] - self.o[m]
            if (body if up else -body) >= C.DISP_MULT * aa:
                body_ok = True
            if m - 2 >= f:
                g = (self.l[m] - self.h[m - 2]) if up else (self.l[m - 2] - self.h[m])
                if g > 0 and g >= C.POI_MIN_GAP * aa:
                    gap_ok = True
        return body_ok and gap_ok

    def _ob_add(self, s, i, up):
        f = max(s, i - 30, 0)
        best, bp = None, NAN
        for m in range(f, i):
            opp = self.c[m] < self.o[m] if up else self.c[m] > self.o[m]
            p = self.l[m] if up else self.h[m]
            if opp and (best is None or (p < bp if up else p > bp)):
                best, bp = m, p
        if best is None:
            best = f
        if not any(z["kind"] == 2 and z["t0"] == self.t[best] for z in self.zs):
            self._z_add(2, up, self.h[best], self.l[best], self.t[best], True)

    def push(self, t, o, h, l, c, a):
        self.t.append(t)
        self.o.append(o)
        self.h.append(h)
        self.l.append(l)
        self.c.append(c)
        self.a.append(h - l if isnan(a) else a)
        self._step()

    def _step(self):
        i = len(self.t) - 1
        self.ev = 0
        self.bullBroken = self.bearBroken = False
        k = C.PIV_K
        if i >= 2 * k:
            j = i - k
            isH = isL = True
            for m in range(j - k, j + k + 1):
                if m < j:
                    if self.h[m] >= self.h[j]:
                        isH = False
                    if self.l[m] <= self.l[j]:
                        isL = False
                if m > j:
                    if self.h[m] > self.h[j]:
                        isH = False
                    if self.l[m] < self.l[j]:
                        isL = False
            if isH:
                self.sh0, self.sh1, self.sh1i, self.shDone = self.sh1, self.h[j], j, False
                self._liq_add(self.h[j], True, self.a[j])
            if isL:
                self.sl0, self.sl1, self.sl1i, self.slDone = self.sl1, self.l[j], j, False
                self._liq_add(self.l[j], False, self.a[j])
        aa = self.a[i]
        if i >= 2:
            if self.l[i] > self.h[i - 2] and self.l[i] - self.h[i - 2] >= C.POI_MIN_GAP * aa:
                self._z_add(1, True, self.l[i], self.h[i - 2], self.t[i - 2], False)
            if self.h[i] < self.l[i - 2] and self.l[i - 2] - self.h[i] >= C.POI_MIN_GAP * aa:
                self._z_add(1, False, self.l[i - 2], self.h[i], self.t[i - 2], False)
        cc = self.c[i]
        if not self.shDone and cc > self.sh1:
            self.shDone = True
            s0 = i if self.sl1i is None else self.sl1i
            ev = (3 if self._leg_ok(s0, i, True) else 2) if self.trend == -1 else 1
            self.ev = self.lastEv = ev
            self.trend = 1
            self._ob_add(s0, i, True)
            for z in self.zs:
                if z["kind"] == 1 and z["bull"] and z["born"] >= s0:
                    z["cause"] = True
        if not self.slDone and cc < self.sl1:
            self.slDone = True
            s1 = i if self.sh1i is None else self.sh1i
            ev = (-3 if self._leg_ok(s1, i, False) else -2) if self.trend == 1 else -1
            self.ev = self.lastEv = ev
            self.trend = -1
            self._ob_add(s1, i, False)
            for z in self.zs:
                if z["kind"] == 1 and not z["bull"] and z["born"] >= s1:
                    z["cause"] = True
        hh, ll = self.h[i], self.l[i]
        for q in range(len(self.zs) - 1, -1, -1):
            z = self.zs[q]
            if z["born"] >= i:
                continue
            if i - z["born"] > C.ZONE_LIFE:
                self.zs.pop(q)
                continue
            if z["bull"]:
                if ll <= z["top"]:
                    self.bullTouchT = self.t[i]
                    z["fresh"] = False
                if cc < z["bot"]:
                    self.bullBroken = True
                    if z["kind"] in (1, 2):
                        nk = 5 if z["kind"] == 1 else (3 if self.sh1 > self.sh0 else 4)
                        z.update(kind=nk, bull=False, fresh=True, cause=True, born=i)
                    else:
                        self.zs.pop(q)
            else:
                if hh >= z["bot"]:
                    self.bearTouchT = self.t[i]
                    z["fresh"] = False
                if cc > z["top"]:
                    self.bearBroken = True
                    if z["kind"] in (1, 2):
                        nk = 5 if z["kind"] == 1 else (3 if self.sl1 < self.sl0 else 4)
                        z.update(kind=nk, bull=True, fresh=True, cause=True, born=i)
                    else:
                        self.zs.pop(q)


# ================================================================ HTF bars from 5-minute bars
def htf_ids(df):
    """Period ids for each 5-minute bar: day, week, 4-hour and 1-hour (sessions start at 9:30 like TradingView)."""
    ts = df.index
    day = ts.normalize()
    mins = (ts.hour * 60 + ts.minute - 570)
    week = (day - pd.to_timedelta(ts.dayofweek, unit="D"))
    a = day + pd.to_timedelta((mins // C.ATF_A_MIN) * C.ATF_A_MIN + 570, unit="m")
    b = day + pd.to_timedelta((mins // C.ATF_B_MIN) * C.ATF_B_MIN + 570, unit="m")
    return {"D": day, "W": week, "A": a, "B": b}


def agg(df, key, atr_len):
    g = df.groupby(key, sort=True)
    out = pd.DataFrame({"o": g["open"].first(), "h": g["high"].max(), "l": g["low"].min(), "c": g["close"].last()})
    out["atr"] = rma_atr(out["h"].values, out["l"].values, out["c"].values, atr_len)
    return out


# ================================================================ 3. the full run on one symbol
def run_symbol(df, symbol, group):
    """df: regular-session 5-minute bars (index = New York time, columns open/high/low/close/volume).
    Returns (trades, funnel)."""
    df = df.sort_index()
    ids = htf_ids(df)
    bars = {k: agg(df, ids[k].values, C.ATR_LEN if k == "D" else 14) for k in ids}
    pos = {k: bars[k].index.get_indexer(ids[k].values) for k in ids}
    O, H, L, Cl = (df[c].values.astype(float) for c in ("open", "high", "low", "close"))
    T = df.index
    n = len(df)
    atrC = rma_atr(H, L, Cl, 14)
    nyMin = (T.hour * 60 + T.minute).values
    dayKey = ids["D"].values

    D = Daily()
    liqs = []
    eA, eB = Engine("4H", liqs), Engine("1H", liqs)
    ctrl = 0
    cph, cpl = [], []
    lastPH = lastPL = NAN
    S = dict(st=0, sd=0, poiTop=NAN, poiBot=NAN, poi="", swX=NAN, swBar=0, nSw=0, mss=NAN, legBody=0.0, legX=NAN,
             fTop=NAN, fBot=NAN, ent=NAN, stp=NAN, rsk=NAN, tg1=NAN, tg2=NAN, mssBar=0, t1=False, rr=0.0,
             trades=0, losses=0, choch=False, mssT=None, fillT=None, vshape=False, dbl=False, bias=0, ctrl=0, atf=False)
    trades = []
    mlog = []
    fun = dict(poi=0, sweep=0, choch=0, mss=0, order=0, fill=0, poi_failed=0, window_closed=0, not_filled=0)
    for c in range(1, 12):
        fun["fail_%d" % c] = 0

    def zone_opp(e, up, a, b):
        for z in e.zs:
            if z["fresh"] and z["bull"] != up:
                edge = z["bot"] if up else z["top"]
                if (edge > a and edge < b) if up else (edge < a and edge > b):
                    return True
        return False

    def sr_opp(up, a, b):
        for s in D.srs:
            if s["res"] == up:
                edge = s["bot"] if up else s["top"]
                if (edge > a and edge < b) if up else (edge < a and edge > b):
                    return True
        return False

    def inside_opp(e, bull, tp, bt):
        return any(z["fresh"] and z["bull"] != bull and z["top"] >= bt and z["bot"] <= tp for z in e.zs)

    def find_poi(e, d, eqv, lo, hi):
        for z in e.zs:
            if z["fresh"] and z["cause"] and z["bull"] == (d == 1):
                loc = (z["top"] <= eqv) if d == 1 else (z["bot"] >= eqv)
                if loc and lo <= z["top"] and hi >= z["bot"]:
                    return True, z["top"], z["bot"], e.tag + " " + KIND[z["kind"]]
        return False, NAN, NAN, ""

    def closer(best, p, x, up):
        if isnan(p) or not (p > x if up else p < x):
            return best
        return p if (isnan(best) or abs(p - x) < abs(best - x)) else best

    def atf_ok(d):
        return d != 0 and eB.trend == d and (eA.trend == d or eB.lastEv == 2 * d or eB.lastEv == 3 * d)

    pdH = pdL = pwH = pwL = NAN
    for i in range(n):
        # ---- 1. completed daily bar
        if i > 0 and pos["D"][i] != pos["D"][i - 1]:
            k = pos["D"][i] - 1
            if k >= 0:
                r = bars["D"].iloc[k]
                D.step(r.h, r.l, r.c, r.atr)
                pdH, pdL = r.h, r.l
        if i > 0 and pos["W"][i] != pos["W"][i - 1]:
            k = pos["W"][i] - 1
            if k >= 0:
                r = bars["W"].iloc[k]
                pwH, pwL = r.h, r.l
        dlHi, dlLo, eq = D.dealing()
        bias = D.bias()
        # ---- 2. completed ATF bars
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
        # ---- 3. 5-minute swings (pivot 2 / 2, confirmed two bars later)
        if i >= 4:
            j = i - 2
            if H[j] > max(H[j - 2:j]) and H[j] >= max(H[j + 1:i + 1]):
                lastPH = H[j]
                cph.append(H[j])
                if len(cph) > 10:
                    cph.pop(0)
            if L[j] < min(L[j - 2:j]) and L[j] <= min(L[j + 1:i + 1]):
                lastPL = L[j]
                cpl.append(L[j])
                if len(cpl) > 10:
                    cpl.pop(0)
        hh10 = H[max(0, i - 9):i + 1].max()
        ll10 = L[max(0, i - 9):i + 1].min()
        a5 = atrC[i]
        if isnan(a5):
            continue
        o, h, l, cl = O[i], H[i], L[i], Cl[i]
        inWin = C.WINDOW[0] <= nyMin[i] < C.WINDOW[1]
        newDay = i > 0 and dayKey[i] != dayKey[i - 1]
        bullGap = i >= 2 and l > H[i - 2] and l - H[i - 2] >= C.ENT_GAP * a5
        bearGap = i >= 2 and h < L[i - 2] and L[i - 2] - h >= C.ENT_GAP * a5

        def is_sweep(p, lg):
            return not isnan(p) and ((l < p and cl > p) if lg else (h > p and cl < p))

        def any_sweep(lg):
            fixed = (pdL, pwL) if lg else (pdH, pwH)
            if any(is_sweep(p, lg) for p in fixed):
                return True
            if any(o_["live"] and o_["hi"] != lg and is_sweep(o_["p"], lg) for o_ in liqs):
                return True
            return any(is_sweep(p, lg) for p in (cpl if lg else cph))

        def nearest_pool(x, up):
            best = NAN
            for p in ((pdH, pwH) if up else (pdL, pwL)):
                best = closer(best, p, x, up)
            for o_ in liqs:
                if o_["live"] and o_["hi"] == up:
                    best = closer(best, o_["p"], x, up)
            for p in (cph if up else cpl):
                best = closer(best, p, x, up)
            return best

        def final_pool(x, up):
            best = NAN
            for p in ((pdH, pwH, D.h1, dlHi) if up else (pdL, pwL, D.l1, dlLo)):
                best = closer(best, p, x, up)
            for s in D.srs:
                if s["res"] == up:
                    best = closer(best, s["bot"] if up else s["top"], x, up)
            return best

        # ---- 4. the state machine
        if newDay:
            S["trades"] = S["losses"] = 0
            if 0 < S["st"] < 4:
                S["st"] = 0
        lg = S["sd"] == 1
        st = S["st"]
        if st == 0:
            if bias != 0 and S["trades"] < C.MAX_TRADES and S["losses"] < C.MAX_LOSSES:
                fA, tA_, bA_, nA = find_poi(eA, bias, eq, l, h)
                fB, tB_, bB_, nB = find_poi(eB, bias, eq, l, h)
                okB = fB and not inside_opp(eA, bias == 1, tB_, bB_)
                if fA or okB:
                    S.update(st=1, sd=bias, poiTop=tA_ if fA else tB_, poiBot=bA_ if fA else bB_, poi=nA if fA else nB)
                    fun["poi"] += 1
        elif st == 1:
            failed = cl < S["poiBot"] if lg else cl > S["poiTop"]
            near = (l <= S["poiTop"] + 0.5 * a5) if lg else (h >= S["poiBot"] - 0.5 * a5)
            if failed:
                S["st"] = 0
                fun["poi_failed"] += 1
            elif inWin and near and any_sweep(lg):
                mss = (lastPH if (not isnan(lastPH) and lastPH > cl) else hh10) if lg else (lastPL if (not isnan(lastPL) and lastPL < cl) else ll10)
                S.update(st=2, swX=l if lg else h, swBar=i, nSw=1, mss=mss, legBody=0.0, legX=h if lg else l, fTop=NAN, fBot=NAN, choch=False)
                fun["sweep"] += 1
        elif st == 2:
            deeper = l < S["swX"] if lg else h > S["swX"]
            failed = cl < S["poiBot"] if lg else cl > S["poiTop"]
            if failed or not inWin:
                S["st"] = 0
                fun["poi_failed" if failed else "window_closed"] += 1
            elif deeper:
                if any_sweep(lg):
                    S["nSw"] += 1
                mss = (lastPH if (not isnan(lastPH) and lastPH > cl) else hh10) if lg else (lastPL if (not isnan(lastPL) and lastPL < cl) else ll10)
                S.update(swX=l if lg else h, swBar=i, mss=mss, legBody=0.0, legX=h if lg else l, fTop=NAN, fBot=NAN)
            else:
                S["legBody"] = max(S["legBody"], (cl - o) if lg else (o - cl))
                S["legX"] = max(S["legX"], h) if lg else min(S["legX"], l)
                if lg and bullGap:
                    S["fTop"], S["fBot"] = l, H[i - 2]
                if not lg and bearGap:
                    S["fTop"], S["fBot"] = L[i - 2], h
                broke = cl > S["mss"] if lg else cl < S["mss"]
                if broke:
                    if S["legBody"] >= C.DISP_MULT * a5 and not isnan(S["fTop"]):
                        fun["mss"] += 1
                        fT, fB_ = S["fTop"], S["fBot"]
                        if C.FILL_AT == "Near edge":
                            ent = fT if lg else fB_
                        elif C.FILL_AT == "50% of the gap":
                            ent = (fT + fB_) / 2
                        else:
                            ent = fB_ if lg else fT
                        stp = S["swX"] - C.STOP_BUF * a5 if lg else S["swX"] + C.STOP_BUF * a5
                        minRisk = C.MIN_STOP_PCT / 100 * ent
                        if abs(ent - stp) < minRisk:
                            stp = ent - minRisk if lg else ent + minRisk
                        rsk = abs(ent - stp)
                        base = max(S["legX"], ent) if lg else min(S["legX"], ent)
                        near = nearest_pool(base, lg)
                        daily = final_pool(base, lg)
                        if C.T1_MODE == "daily target":
                            tg1 = daily
                            tg2 = NAN if isnan(tg1) else final_pool(tg1, lg)
                        else:
                            tg1 = near
                            tg2 = NAN if isnan(tg1) else final_pool(tg1, lg)
                        rr = 0.0 if (isnan(tg1) or rsk <= 0) else abs(tg1 - ent) / rsk
                        opp = (not isnan(tg1)) and (zone_opp(eA, lg, ent, tg1) or zone_opp(eB, lg, ent, tg1) or sr_opp(lg, ent, tg1))
                        checks = {1: bias == S["sd"], 2: (ent < eq) if lg else (ent > eq), 3: ctrl == S["sd"],
                                  4: atf_ok(S["sd"]), 6: rr >= C.MIN_RR and not opp,
                                  11: S["trades"] < C.MAX_TRADES and S["losses"] < C.MAX_LOSSES}
                        fails = [c for c, ok in checks.items() if not ok and c not in C.SKIP_CHECKS]
                        for c in fails:
                            fun["fail_%d" % c] += 1
                        # ---- diagnostics: every MSS, with the numbers each fill level and target would give
                        def _rr(e_, t_):
                            r_ = abs(e_ - stp_at(e_)) if not isnan(e_) else NAN
                            return round(abs(t_ - e_) / r_, 2) if not (isnan(t_) or isnan(r_) or r_ <= 0) else None

                        def stp_at(e_):
                            s_ = S["swX"] - C.STOP_BUF * a5 if lg else S["swX"] + C.STOP_BUF * a5
                            mr = C.MIN_STOP_PCT / 100 * e_
                            return (e_ - mr if lg else e_ + mr) if abs(e_ - s_) < mr else s_
                        eNear, eMid, eFar = (fT if lg else fB_), (fT + fB_) / 2, (fB_ if lg else fT)
                        mlog.append(dict(symbol=symbol, time=str(T[i]), side="long" if lg else "short", poi=S["poi"],
                                         risk_pct=round(100 * rsk / ent, 3), gap_atr=round((fT - fB_) / a5, 2),
                                         leg_body_atr=round(S["legBody"] / a5, 2), bars_from_sweep=i - S["swBar"],
                                         rr_t1=round(rr, 2), opposing_zone=opp,
                                         rr_near_pool=_rr(eNear, near), rr_mid_pool=_rr(eMid, near), rr_far_pool=_rr(eFar, near),
                                         rr_near_daily=_rr(eNear, daily), rr_mid_daily=_rr(eMid, daily), rr_far_daily=_rr(eFar, daily),
                                         c1=checks[1], c2=checks[2], c3=checks[3], c4=checks[4], c6=checks[6], c11=checks[11],
                                         bias=bias, ctrl=ctrl, atf_a=eA.trend, atf_b=eB.trend, ordered=not fails))
                        if not fails:
                            fun["order"] += 1
                            S.update(st=3, ent=ent, stp=stp, rsk=rsk, tg1=tg1, tg2=tg2, rr=rr, mssBar=i, mssT=T[i],
                                     vshape=(i - S["swBar"]) <= C.V_BARS, dbl=S["nSw"] >= 2, bias=bias, ctrl=ctrl, atf=atf_ok(S["sd"]))
                        else:
                            S["st"] = 0
                    elif not S["choch"]:
                        S["choch"] = True
                        fun["choch"] += 1
        elif st == 3:
            filled = i > S["mssBar"] and ((l <= S["ent"]) if lg else (h >= S["ent"]))
            if filled:
                fun["fill"] += 1
                S.update(st=4, t1=False, fillT=T[i], stp0=S["stp"])
                S["trades"] += 1
                if (l <= S["stp"]) if lg else (h >= S["stp"]):
                    _close(trades, S, symbol, group, -1.0, "stop on fill bar", T[i])
                    S["losses"] += 1
                    S["st"] = 0
            elif i - S["mssBar"] >= C.EXPIRY_BARS or ((l < S["swX"]) if lg else (h > S["swX"])) or not inWin:
                S["st"] = 0
                fun["not_filled"] += 1
        elif st == 4:
            ent, rsk, tg1, tg2 = S["ent"], S["rsk"], S["tg1"], S["tg2"]
            r1 = 0.0 if isnan(tg1) else abs(tg1 - ent) / rsk
            exitR, why = NAN, ""
            if (l <= S["stp"]) if lg else (h >= S["stp"]):
                exitR, why = (0.5 * r1, "T1 then breakeven") if S["t1"] else (-1.0, "stop")
            else:
                if not S["t1"] and not isnan(tg1) and ((h >= tg1) if lg else (l <= tg1)):
                    S["t1"] = True
                    S["stp"] = ent
                if not isnan(tg2) and ((h >= tg2) if lg else (l <= tg2)):
                    exitR, why = 0.5 * r1 + 0.5 * abs(tg2 - ent) / rsk, "final target"
                elif nyMin[i] >= C.EOD_MIN:
                    rc = ((cl - ent) if lg else (ent - cl)) / rsk
                    exitR, why = (0.5 * r1 + 0.5 * rc if S["t1"] else rc), "end of day"
            if not isnan(exitR):
                _close(trades, S, symbol, group, exitR, why, T[i])
                if exitR < 0:
                    S["losses"] += 1
                S["st"] = 0
        # ---- 5. spent liquidity
        for q in range(len(liqs) - 1, -1, -1):
            o_ = liqs[q]
            if (h > o_["p"]) if o_["hi"] else (l < o_["p"]):
                liqs.pop(q)
        cph[:] = [p for p in cph if not h > p]
        cpl[:] = [p for p in cpl if not l < p]
    return trades, fun, mlog


def _close(trades, S, symbol, group, r, why, t):
    cost = 2 * C.COST_PCT_PER_SIDE / 100 * S["ent"] / S["rsk"] if S["rsk"] > 0 else 0.0
    trades.append(dict(symbol=symbol, group=group, date=str(S["mssT"].date()), mss_time=str(S["mssT"]),
                       fill_time=str(S["fillT"]), exit_time=str(t), side="long" if S["sd"] == 1 else "short", poi=S["poi"],
                       entry=round(S["ent"], 4), stop=round(S.get("stp0", S["stp"]), 4), t1=round(S["tg1"], 4),
                       t2=None if isnan(S["tg2"]) else round(S["tg2"], 4), risk_pct=round(100 * S["rsk"] / S["ent"], 3),
                       rr_t1=round(S["rr"], 2), t1_hit=S["t1"], exit=why, r_gross=round(r, 3), r_net=round(r - cost, 3),
                       v_shape=S["vshape"], double_sweep=S["dbl"]))
