#!/usr/bin/env python3
"""Forecast Polymarket's "Next CEO of NVIDIA?" Yes prices, minute by minute.

make.fun bounty: polymarket-nvidia-ceo-forecast-01
Entry program (Python 3.13, standard library only, NO network).

Reads every <id>.in case in the input directory and writes <id>.out to the
output directory. A case is one checkpoint: every trading market of the
event with its Yes price at every minute of the 72 hours up to the
checkpoint. The forecast is, for each market and each of the 240 minutes
after the checkpoint, five quantiles (0.05, 0.25, 0.5, 0.75, 0.95) of
that minute's price. Score: mean pinball loss over every market, minute
and quantile; the entry must beat the best house entry to take a place.

Model (persistence median + per-market volatility, normal quantiles)
--------------------------------------------------------------------
These prices move in steps: most minutes nothing happens, then a tick,
now and then a jump of several points (e.g. Colette Kress 0.3535 ->
0.59 in one minute). The house baseline (one fixed sigma of 0.0025 for
every market) is beaten by measuring each market's own volatility:

* sigma: 1.2533 * mean absolute 1-minute return over the market's last
  24 hours (1440 minutes), returns winsorized at 5 points so one freak
  jump does not set the scale, floored at 0.0008 and capped at 0.012,
  then scaled by 0.7. The 1.2533 converts mean absolute deviation to a
  normal sigma; the 0.7 is an empirical calibration (the practice-case
  loss curve is flat between 0.6 and 0.9, so 0.7 is not a knife-edge).
  Quiet markets get a narrow fan, jumpy ones a wide one.
* quantiles: q_tau(h) = x + z_tau * sigma * sqrt(h), z the normal
  quantiles [-1.644854, -0.674490, 0, 0.674490, 1.644854]. Fat-tailed
  (Student-t) multipliers were tested and scored WORSE on the practice
  cases, so the normal is used.
* median: the last price (persistence). Mean reversion toward the
  72-hour mean was tested and scored much worse, so there is no drift.

Practice results (6 cases p00-p05, answers from the next case's prices
for p00-p04 and from the Polymarket CLOB API for p05):
  this model  0.2993 mean pinball loss (0.481 / 0.312 / 0.359 / 0.286 /
              0.221 / 0.137 per case), beating the house baseline on
              every case.
  house base  0.3718 on the same scorer (published practice loss
              0.363589; the small gap is my p05 answers being fetched,
              not official).

Caveats: the practice window is explicitly "no guide to the final" —
the final phase uses fresh history to 2026-11-13 20:00 UTC and the
final window runs to 2026-11-15 17:00 UTC. The model re-measures
volatility from whatever history each case carries, so it adapts.

Deterministic: no randomness, no time or network access, markets
processed in the case's order. Runs in ~0.05 s per case.
"""

import json
import math
import os
import sys

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
# Normal quantiles at the five levels.
Z_TAU = [-1.644854, -0.674490, 0.0, 0.674490, 1.644854]

# Volatility window: last 24 hours of 1-minute returns (1440 minutes).
VOL_WINDOW = 1440
# Clip single-minute moves at 5 points when measuring volatility, so one
# freak jump does not set the scale for the whole next 4 hours.
WINSOR = 0.05
# Floor / cap on sigma (price units per square-root minute).
SIGMA_FLOOR = 0.0008
SIGMA_CAP = 0.012
# Fallback sigma when a market has too little history to measure.
SIGMA_DEFAULT = 0.0025
# Empirical calibration of the mean-absolute-return sigma (see docstring).
SIGMA_SCALE = 0.7


def price6(x):
    """Clamp to [0, 1] and round to 6 decimals (0, never -0)."""
    v = round(min(1.0, max(0.0, x)) * 1e6) / 1e6
    return v + 0.0


def market_sigma(prices):
    """Per-minute volatility from the market's recent 1-minute returns."""
    n = len(prices)
    if n < 60:
        return SIGMA_DEFAULT
    rets = prices[-VOL_WINDOW - 1:] if n > VOL_WINDOW + 1 else prices
    total = 0.0
    cnt = 0
    for i in range(1, len(rets)):
        r = rets[i] - rets[i - 1]
        if r > WINSOR:
            r = WINSOR
        elif r < -WINSOR:
            r = -WINSOR
        total += abs(r)
        cnt += 1
    if cnt == 0:
        return SIGMA_DEFAULT
    # 1.2533 = sqrt(pi/2): mean |return| -> normal sigma.
    sigma = 1.2533 * (total / cnt) * SIGMA_SCALE
    if sigma < SIGMA_FLOOR:
        sigma = SIGMA_FLOOR
    elif sigma > SIGMA_CAP:
        sigma = SIGMA_CAP
    return sigma


def forecast_market(prices, horizon):
    """`horizon` rows of five quantiles for one market."""
    x = prices[-1]
    sigma = market_sigma(prices)
    rows = []
    for h in range(1, horizon + 1):
        s = sigma * math.sqrt(h)
        row = [price6(x + k * s) for k in Z_TAU]
        # Enforce non-decreasing (clamping can only break it at 0/1).
        for j in range(1, 5):
            if row[j] < row[j - 1]:
                row[j] = row[j - 1]
        rows.append(row)
    return rows


def run_case(case):
    horizon = int(case["horizon_minutes"])
    forecasts = []
    for m in case["markets"]:
        prices = m["prices"]
        if not prices:
            raise ValueError("market %s has no prices" % m["id"])
        forecasts.append({"id": m["id"], "q": forecast_market(prices, horizon)})
    return {"forecasts": forecasts}


def main():
    in_dir = INPUT_DIR
    out_dir = OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    names = sorted(f for f in os.listdir(in_dir) if f.endswith(".in"))
    if not names:
        sys.stderr.write("no .in cases in %s\n" % in_dir)
        return 1
    for name in names:
        cid = name[: -len(".in")]
        with open(os.path.join(in_dir, name), "r", encoding="utf-8") as fh:
            case = json.load(fh)
        if list(case.get("quantiles", [])) != QUANTILES:
            raise ValueError(
                "%s asks for quantiles %r, not %r"
                % (name, case.get("quantiles"), QUANTILES)
            )
        out = run_case(case)
        with open(os.path.join(out_dir, cid + ".out"), "w", encoding="utf-8") as fh:
            fh.write(json.dumps(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
