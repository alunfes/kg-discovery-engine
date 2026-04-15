# Delivery Policy Recommendation — Run 028

## Run 027 Baseline (45min cadence)

| Metric | Value |
|--------|-------|
| cadence | 45 min |
| precision | 0.560 |
| stale_rate | 0.210 |
| reviews/day | 32 |

## Experiment 1: Push-based surfacing

| Config | push/8h | precision | cards/push | meets constraints? |
|--------|---------|-----------|------------|-------------------|
| aggressive | 17.0 | 0.513 | 20.00 | NO |
| balanced | 16.0 | 0.552 | 20.06 | NO |
| conservative | 16.0 | 0.554 | 20.18 | NO |

**Recommended push config**: `conservative`
- push_rate_per_8h: 16.0
- avg_precision: 0.554 (↓0.006 vs 45min baseline)
- push_rate delta vs 45min baseline: -16.0 reviews/8h

## Experiment 2: Card archive policy

| Config | archived/8h | resurface_rate | churn | meets constraints? |
|--------|-------------|----------------|-------|--------------------|
| relaxed | 20.00 | 0.752 | 0.348 | NO |
| standard | 20.00 | 0.910 | 0.862 | NO |
| tight | 20.00 | 0.935 | 0.940 | NO |

**Recommended archive config**: `relaxed`
- archive_rate_per_8h: 20.00
- resurface_rate: 0.752
- archive_churn: 0.348
- avg_archive_age_min: 131

## Combined Policy for Run 029

| Setting | Value |
|---------|-------|
| push_config | conservative |
| archive_config | relaxed |
| cadence (fallback) | 45 min |
| family_collapse | ON |
| surface_unit | DigestCard |

## State Machine (updated)

```
fresh → active → aging → digest_only → expired → archive → [archive_resurface]
```

## Next Steps

1. Run 029: integrate push_trigger into production-shadow pipeline
2. Validate push_precision on live data (not synthetic)
3. Monitor archive_churn over 48h production shadow
