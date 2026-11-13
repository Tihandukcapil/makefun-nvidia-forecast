# Build transcript — NVIDIA Polymarket forecaster (make.fun bounty)

Built 2026-11-13 ~22:55–23:20 WIB on this VM by the agent (Muse subagent
session 82e3ad13), for the make.fun bounty
`polymarket-nvidia-ceo-forecast-01` (ends Sat 2026-11-14 04:00 WIB).
Entry built only — NOT submitted, nothing signed, no wallet connected,
nothing paid. The parent agent creates the GitHub repo and submits.

## Sources

- Bounty page: https://make.fun/bounty/polymarket-nvidia-ceo-forecast-01
- Official agent kit (downloaded from the bounty page):
  `/tmp/kit/polymarket-nvidia-ceo-forecast-01-kit/` — RULES.txt (370 lines),
  competition.yaml, input/p00.in–p05.in (6 practice cases), input/NOTICE.txt,
  starter/main.ts + starter/LICENSE (MIT), cli/makefun.mjs, harness/.
- Corrected spec delivered by the parent agent 2026-11-13 ~22:58 WIB
  (verified live from the bounty page): program runs OFFLINE in the
  sandbox, no network; reads `/input/<id>.in` (env vars
  $MAKEFUN_INPUT_DIR / $MAKEFUN_OUTPUT_DIR override); writes
  `/output/<id>.out`, UTF-8 JSON, max 1,048,576 bytes, exactly
  `{"forecasts": [{"id": <conditionId>, "q": [[5 quantiles] x 240 rows]}]}`;
  `main.py` (Python 3.13) at repo root, 8 s / 1 CPU / 1024 MB per case,
  stdlib + vendored code only, deterministic byte-for-byte across runs.
- Polymarket CLOB API (public, used only for scoring, never by the entry):
  `https://clob.polymarket.com/prices-history?market=<yes_token>&startTs=<s>&endTs=<s>&fidelity=1`

## Commands run

```bash
# 1. Kit inspection
ls /tmp/kit/polymarket-nvidia-ceo-forecast-01-kit/input/
python3 -c "import json; ..."   # p00: 19 markets, at 2026-11-12T06:00:00Z, 3086 prices/market

# 2. Scorer (pinball loss, 100x) — /tmp/nv/score.py
#    answers p00-p04 from next case's input; p05 fetched from CLOB API:
python3 /tmp/nv/fetch_p05.py   # 24 markets, 240 points each, 02:00-06:00 UTC 2026-11-13
#    (24 grid points at 02:00 were None — filled forward from each market's
#     checkpoint price in p05; verified 0 Nones remain)

# 3. Return statistics exploration (per market, p05):
#    prices move in steps (3-51% of minutes nonzero); MAD = 0 for most
#    markets; 24h std 0.00007-0.01076; rare jumps up to 0.24 in one minute

# 4. Variant grid — /tmp/nv/variants.py, /tmp/nv/grid.py, /tmp/nv/median_test.py
#    (each variant run on all 6 practice cases and scored)

# 5. Final program + tests
time MAKEFUN_INPUT_DIR=/tmp/nv/cases MAKEFUN_OUTPUT_DIR=/tmp/nv/out_final \
  python3 ~/workspace/makefun/nvidia-forecast/main.py   # 0.33 s for 6 cases
MAKEFUN_INPUT_DIR=/tmp/nv/cases MAKEFUN_OUTPUT_DIR=/tmp/nv/out_final2 \
  python3 ~/workspace/makefun/nvidia-forecast/main.py
diff -r /tmp/nv/out_final /tmp/nv/out_final2            # IDENTICAL
python3 /tmp/nv/score.py /tmp/nv/out_final
python3 /tmp/nv/validate.py                             # format validation, all 6 cases
# synthetic edge cases (1-price market, flat market, huge-jump market,
# single-market case):
MAKEFUN_INPUT_DIR=/tmp/nv/synth_in MAKEFUN_OUTPUT_DIR=/tmp/nv/synth_out \
  python3 ~/workspace/makefun/nvidia-forecast/main.py   # 0.08 s, all valid
```

## Variant results (mean pinball loss over 6 practice cases; lower is better)

| variant | mean | per case |
|---|---|---|
| house baseline (fixed sigma 0.0025, normal) | 0.3718 | 0.536 / 0.380 / 0.408 / 0.369 / 0.299 / 0.238 |
| per-market std (24h, winsor 0.05), normal | 0.4643 | — |
| per-market std (24h, winsor 0.05), Student-t(4) | 0.5094 | — |
| **per-market mean\|return\| (24h), normal, scale 0.7 — SHIPPED** | **0.2993** | **0.481 / 0.312 / 0.359 / 0.286 / 0.221 / 0.137** |
| same, scale 1.0 | 0.3016 | 0.462 / 0.318 / 0.349 / 0.301 / 0.229 / 0.151 |
| same, Student-t(4) | 0.3121 | — |
| same, window 6h / 12h / 72h | 0.2976 / 0.2984 / 0.3067 | — |
| median absolute nonzero return, normal | 0.4008 | — |
| mean-reversion median (pull 0.1 / 0.2 to 72h mean) | 0.3199 / 0.3815 | — |

Decisions from the grid: fat tails (Student-t) hurt; std-based sigma is
jump-inflated and hurts; mean-reversion of the median hurts badly;
the scale curve is flat (0.6–0.9 all ≈ 0.296–0.299), so 0.7 is not a
knife-edge. The shipped model beats the house baseline on every case.

Note: the first shipped draft used std-based sigma + t(4) and scored
0.5072 — worse than baseline. It was rewritten after the grid above.

## Final test results

- Practice score (final `main.py`): **mean 0.2993** — p00 0.481265,
  p01 0.311977, p02 0.359150, p03 0.285538, p04 0.220632, p05 0.137109.
  90% coverage 0.805–0.985 per case (sane; the first draft's ~1.0 was
  the tell that its fan was far too wide).
- Determinism: two full runs over all 6 cases produce byte-identical
  outputs (`diff -r` clean).
- Format validation (`/tmp/nv/validate.py`): all 6 outputs parse; exactly
  one `forecasts` key; every case has all its markets (19/19/19/23/24/24);
  240 rows per market; 5 quantiles per row; every value in [0, 1];
  non-decreasing within every row; largest file 266,365 bytes
  (< 1,048,576 cap).
- Synthetic edge cases: 1-price market, all-flat market, market with a
  0.05 → 0.85 jump, single-market case — all run without crashing and
  produce valid output; 1-price/flat markets fall back to the floor
  sigma (0.0008); short-history markets (< 60 prices) use the 0.0025
  default sigma.
- Runtime: 0.33 s for 6 cases (~0.055 s/case) — far under the 8 s limit.
  Stdlib only, no network, no randomness.

## Assumptions / things to flag

1. The p05 answers are NOT official: they were fetched from the public
   Polymarket CLOB API (240 points/market, grid built as last point at
   or before each minute, carried forward from the checkpoint price).
   p00–p04 answers come from the next case's own input prices, which is
   exact. The baseline reproduces at 0.3718 vs the published 0.363589,
   so the scorer is close but not exact — treat the 0.2993 vs 0.3718
   comparison as indicative, not exact.
2. Practice is explicitly "no guide to the final" (bounty rules). The
   final phase uses fresh history to 2026-11-13 20:00 UTC and runs to
   2026-11-15 17:00 UTC; the model re-measures volatility per case, but
   a regime change (e.g. a CEO announcement) could still break it.
3. The entry program does NOT fetch live data (per the corrected spec)
   and does NOT handle a market deciding mid-window specially — the
   sandbox cases already contain only the prices up to the checkpoint.
4. The repo must be created AFTER the bounty opened (2026-11-13 09:00
   UTC) under the user's GitHub account (Tihandukcapil), with `main.py`
   at the root, MIT LICENSE, and the AI coding-agent transcripts bundled
   (make.fun requires transcripts accounting for the code). The user
   signs the entry at submission (escrow bounty) — that step is his,
   not done here.
