# Repost threshold report (2026-10-28)

300 random catalog photos, each transformed 6 ways (known duplicates), vs. 44,850 pairs of different photos. Distances are Hamming bits out of 64.

| Pair type | median | 95th pct | max | within threshold |
|---|---|---|---|---|
| resized 50% | 0 | 2 | 2 | 100.0% |
| cropped 5% per side | 12 | 18 | 26 | 38.7% |
| cropped 10% per side | 23 | 32 | 34 | 0.3% |
| JPEG quality 20 | 0 | 2 | 4 | 100.0% |
| color-shifted (+25% bright, -40% sat) | 2 | 6 | 10 | 100.0% |
| all of the above | 12 | 18 | 26 | 34.0% |
| **different photos** | 32 | 5th pct 24 | min 10 | 0.009% (false matches) |

## Threshold sweep

| threshold | recall (all transforms) | false-match rate (different photos) |
|---|---|---|
| 4 | 48.8% | 0.000% |
| 6 | 51.1% | 0.000% |
| 8 | 54.7% | 0.000% |
| 10 | 62.2% | 0.009% |
| 12 | 71.3% | 0.016% |
| 14 | 76.6% | 0.078% |
| 16 | 80.9% | 0.241% |
| 18 | 84.6% | 0.696% |
| 20 | 87.8% | 1.868% |

Current `REPOST_THRESHOLD` = **10**.
