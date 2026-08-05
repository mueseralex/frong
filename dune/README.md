# Frong Dune (frong_ai)

Dune account / namespace: **frong_ai**  
Upload table: **frong_activity** (from `server/sync_dune.py`)

Suggested dashboard widgets once the CSV is live:

1. **Events over time** — count of `kind` by day  
2. **Migrations covered** — filter `kind = migration`  
3. **Track hits** — sum / avg `track_count`  
4. **Latest CA reports** — table of recent `ca`, `summary`

Example query sketch:

```sql
SELECT
  date_trunc('day', cast(created_at_iso as timestamp)) AS day,
  kind,
  count(*) AS n,
  sum(track_count) AS track_hits
FROM frong_ai.frong_activity
GROUP BY 1, 2
ORDER BY 1 DESC;
```

Bot and site both read the same activity store; sync pushes aggregates for public narrative.
