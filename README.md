# NVIDIA CEO Price Forecaster — make.fun bounty entry

Forecasts Polymarket's **"Next CEO of NVIDIA?"** Yes prices minute by
minute, 4 hours ahead. Entry for the make.fun bounty
`polymarket-nvidia-ceo-forecast-01` ($250, 100 places paid).

## What it does

`main.py` reads one case file per checkpoint (72 hours of 1-minute Yes
prices for every trading market of the event, up to the checkpoint) and
writes, for each market and each of the 240 minutes after the checkpoint,
five quantiles (0.05, 0.25, 0.5, 0.75, 0.95) of that minute's price.

**Model:** persistence median (last price) + per-market volatility.
Each market's sigma is `1.2533 * mean absolute 1-minute return` over its
last 24 hours, returns winsorized at 5 points, floored at 0.0008, capped
at 0.012, scaled by 0.7; quantiles are `x + z_tau * sigma * sqrt(h)` with
normal z-values, clamped to [0, 1]. See the docstring in `main.py` for
the full rationale and the practice results.

## How to run

```bash
python3 main.py            # reads /input/*.in, writes /output/*.out
```

Or with explicit directories:

```bash
MAKEFUN_INPUT_DIR=./input MAKEFUN_OUTPUT_DIR=./output python3 main.py
```

Requirements: Python 3.13, standard library only, no network, no
dependencies. Runs in ~0.05 s per case (limit: 8 s). Deterministic:
two runs produce byte-identical output.

## Practice results

Scored on the 6 practice cases (p00–p05) from the official agent kit,
answers taken from the next case's prices (p00–p04) and from the
Polymarket CLOB API (p05):

| model | mean pinball loss |
|---|---|
| **this entry** | **0.2993** (per case: 0.481 / 0.312 / 0.359 / 0.286 / 0.221 / 0.137) |
| house baseline (fixed sigma 0.0025, normal) | 0.3718 on the same scorer (published 0.363589) |

This entry beats the house baseline on every practice case. The practice
window is explicitly "no guide to the final" — the model re-measures
volatility from whatever history each case carries, so it adapts to the
final phase.

## Files

- `main.py` — the entry program (root, as required)
- `LICENSE` — MIT
- `README.md` — this file
- `BUILD_TRANSCRIPT.md` — how it was built and tested
