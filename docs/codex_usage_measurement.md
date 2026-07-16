# Codex Usage Measurement

This project measures routing impact with a small repeatable benchmark loop. Exact token and credit data should be recorded when the Codex UI exposes it, but the default metric is a stable proxy based on tool output, final response size, and optional exact token fields.

## Files

- `data/reference/codex_routing_benchmark_tasks.csv` - repeatable task prompts.
- `data/reference/codex_usage_run_log_template.csv` - copyable run-log template.
- `outputs/codex_usage/run_log.csv` - local working log for actual runs.
- `outputs/codex_usage_report/index.html` - generated dashboard.

`outputs/` is ignored by git, so local measurement history stays local unless explicitly exported.

## Workflow

1. Copy the template once:

```bash
mkdir -p outputs/codex_usage
cp data/reference/codex_usage_run_log_template.csv outputs/codex_usage/run_log.csv
```

2. For each benchmark task, run a baseline and a routed variant.
3. Add one row per run to `outputs/codex_usage/run_log.csv`.
4. Generate the dashboard:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-codex-usage \
  outputs/codex_usage/run_log.csv \
  outputs/codex_usage_report
```

5. Open `outputs/codex_usage_report/index.html`.

## Metrics

Record exact token fields when available:

- `exact_input_tokens`
- `exact_cached_input_tokens`
- `exact_output_tokens`

If exact fields are blank or zero, the report estimates:

- input proxy from `tool_output_chars / 4`
- output proxy from `response_chars / 4`

Consumption units are:

```text
input + 0.1 * cached_input + 6 * output
```

This is not a billing statement. It is a stable comparison metric that makes output-heavy answers visibly expensive and makes routed-vs-baseline changes comparable over time.

## Useful Proxy Fields

- `tool_calls` - count shell/browser/MCP/tool calls.
- `file_reads` - count meaningful file reads.
- `full_file_reads` - count broad full-file reads; this should fall with better routing.
- `tool_output_chars` - copy from terminal output length when easy, otherwise estimate.
- `response_chars` - final assistant response length estimate.
- `elapsed_seconds` - wall-clock task duration.
- `quality_score` - 1 to 5 subjective usefulness score.

## Interpreting Results

Good routing should usually:

- reduce tool output,
- reduce full-file reads,
- reduce follow-up turns,
- keep quality flat or better,
- reserve reviewer/high-effort paths for high-risk work.

Some routed runs may cost more. That is acceptable when they improve review quality for ranking, ingestion, data-contract, or demo credibility risks.
