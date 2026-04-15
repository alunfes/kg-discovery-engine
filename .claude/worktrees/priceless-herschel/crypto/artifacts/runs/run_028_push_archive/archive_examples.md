# Archive Policy Examples — Run 028

Archive policy outcome metrics per configuration.

**Success criteria**: archive_churn < 0.20, resurface_rate > 0.10

## Config: `relaxed`

| Metric | Value | Verdict |
|--------|-------|---------|
| archive_rate_per_8h | 20.00 | — |
| n_archived (avg) | 20.0 | — |
| n_resurfaced (avg) | 15.1 | — |
| resurface_rate | 0.752 | PASS |
| archive_churn | 0.348 | FAIL |
| avg_archive_age_min | 131 | — |

## Config: `standard`

| Metric | Value | Verdict |
|--------|-------|---------|
| archive_rate_per_8h | 20.00 | — |
| n_archived (avg) | 20.0 | — |
| n_resurfaced (avg) | 18.2 | — |
| resurface_rate | 0.910 | PASS |
| archive_churn | 0.862 | FAIL |
| avg_archive_age_min | 70 | — |

## Config: `tight`

| Metric | Value | Verdict |
|--------|-------|---------|
| archive_rate_per_8h | 20.00 | — |
| n_archived (avg) | 20.0 | — |
| n_resurfaced (avg) | 18.7 | — |
| resurface_rate | 0.935 | PASS |
| archive_churn | 0.940 | FAIL |
| avg_archive_age_min | 43 | — |

