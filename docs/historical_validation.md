# Historical Validation

The project now has a repeatable historical validation report:

```bash
make validate-pilot-2019
```

This writes:

- `outputs/validation_2019/summary.csv`
- `outputs/validation_2019/summary.md`

## Current 2019 Pilot Result

Dataset:

- Draft year: 2019
- Prospects: 217
- Precision@N: 25
- Board top-N: 25

Current headline:

- Consensus remains the strongest benchmark on the 2019 pilot.
- `hybrid` matches consensus on impact-player Precision@25, but trails on NHLer Precision@25, rank correlation, and top-25 games lift.
- `role-specific-hybrid` improves over raw adjusted production, but does not beat consensus yet.
- Raw adjusted production alone is not good enough as a standalone ranking signal.

| Baseline | NHLer P@25 | Impact P@25 | Spearman Games | Top 25 Games Lift |
| --- | ---: | ---: | ---: | ---: |
| consensus | 0.840 | 0.720 | 0.602 | 4.379 |
| projection | 0.760 | 0.680 | 0.432 | 3.952 |
| adjusted-production | 0.480 | 0.440 | 0.216 | 2.566 |
| contextual | 0.680 | 0.640 | 0.505 | 3.625 |
| role-aware | 0.680 | 0.600 | 0.514 | 3.475 |
| role-specific-hybrid | 0.720 | 0.640 | 0.559 | 3.715 |
| hybrid | 0.760 | 0.720 | 0.582 | 3.992 |

## Interpretation

This is useful, but not yet a business claim that the model beats public consensus.

The right takeaway is:

> The workflow is demo-ready, but the validation layer currently says consensus is the benchmark to beat. Our model-derived scores add explainability and triage value, but need more historical classes and tuning before we can claim predictive lift.

## Next Validation Work

1. Add more historical classes with mature NHL outcomes.
2. Use cross-class validation instead of single-class reporting.
3. Split metrics by role group and draft range.
4. Tune model weights against training classes and evaluate on held-out classes.
5. Compare the demo board approach directly against consensus slot order after calibration.
