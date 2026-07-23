# Codex Usage Measurement

This project measures routing impact with a small repeatable benchmark loop. Exact token and credit data should be recorded when the Codex UI exposes it, but the default metric is a stable proxy based on tool output, final response size, and optional exact token fields.

## Files

- `data/reference/codex_routing_benchmark_tasks.csv` - repeatable task prompts.
- `data/reference/codex_usage_run_log_template.csv` - copyable run-log template.
- `outputs/codex_usage/run_log.csv` - local working log for actual runs.
- `outputs/codex_usage_report/index.html` - generated dashboard.

`outputs/` is ignored by git, so local measurement history stays local unless explicitly exported.

## Workflow

1. Route and run a benchmark task:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli run-codex-task \
  "Generate the Codex usage dashboard" \
  --task-id usage-measurement \
  --quality-score 4
```

2. For each benchmark task, run a baseline and routed variant with the same prompt. Pass `--variant baseline` to use the project Sol/medium default, then `--variant routed` to use the selected route. `--model` and `--reasoning-effort` remain available for an explicit benchmark override.
3. `run-codex-task` automatically appends exact JSON usage and route metadata to `outputs/codex_usage/run_log.csv`.
4. Generate the dashboard:

```bash
PYTHONPATH=src python3 -m draft_room_intelligence.cli report-codex-usage \
  outputs/codex_usage/run_log.csv \
  outputs/codex_usage_report
```

5. Open `outputs/codex_usage_report/index.html`.

## Phase 4: Run Discipline

Use `data/reference/codex_task_routing.csv` before each measured task:

1. Pick the closest task rule and record its `measurement_task_id`.
2. Read the matching context route from `data/reference/codex_context_routes.csv`.
3. Run the task with the recommended model and path: `main`, `kb_explorer`, or `reviewer`.
4. Log one row in `outputs/codex_usage/run_log.csv` immediately after the task.
5. Keep the final answer short enough for the user, but record enough proxy metrics to make the run comparable.

Model routing should use the explicit GPT-5.6 slugs from the task table:

- `gpt-5.6-sol` for complex or high-risk work,
- `gpt-5.6-terra` for everyday exploration and demo updates,
- `gpt-5.6-luna` for clear repeatable edits and reporting.

Treat a routed run as valid only when:

- it used the intended route,
- it completed the requested work,
- it records a subjective `quality_score`,
- it records either exact token fields or proxy character counts,
- it records `file_reads` and `full_file_reads`.

## Phase 5: Optimization Loop

`report-codex-usage` writes:

- `normalized_runs.csv` - cleaned run rows,
- `task_comparison.csv` - latest baseline vs routed comparison per task,
- `route_summary.csv` - aggregate route performance and tuning recommendation,
- `summary.md` and `index.html` - human-readable dashboard.

Use `route_summary.csv` to tune routing rules:

- `promote_route`: keep the route as default for that task class.
- `collect_more_runs`: do not tune yet; gather at least two comparable tasks for the route.
- `simplify_or_disable_route`: reduce subagent/reviewer usage or shrink the context pack.
- `review_quality_before_promoting`: route may be cheaper, but quality fell too much.
- `keep_measuring`: no strong signal yet.

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

For high-assurance routes, do not optimize only for lower token units. Reviewer paths are allowed to cost more when they prevent ranking, ingestion, security, or data-contract regressions.
