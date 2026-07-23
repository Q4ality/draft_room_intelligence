"""Select and execute project Codex task routes."""

from __future__ import annotations

import csv
import json
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from draft_room_intelligence.reports.codex_task_routing import (
    TaskRoutingRule,
    load_task_routing_rules,
)
from draft_room_intelligence.reports.codex_usage import RUN_COLUMNS, UsageRun

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
IGNORED_ROUTE_WORDS = {
    "a",
    "and",
    "for",
    "from",
    "in",
    "is",
    "of",
    "or",
    "the",
    "to",
    "with",
}


@dataclass(frozen=True)
class CodexDispatch:
    rule: TaskRoutingRule
    task: str
    project_root: Path
    model: str
    reasoning_effort: str

    @property
    def command(self) -> list[str]:
        return [
            "codex",
            "exec",
            "--json",
            "--model",
            self.model,
            "--config",
            f'model_reasoning_effort="{self.reasoning_effort}"',
            "--cd",
            str(self.project_root),
            format_routed_prompt(self.rule, self.task),
        ]

    def to_dict(self) -> dict[str, str]:
        return {
            "task_id": self.rule.task_id,
            "task_name": self.rule.task_name,
            "context_route": self.rule.recommended_context_route,
            "agent": self.rule.recommended_agent,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
            "risk_level": self.rule.risk_level,
            "validation_command": self.rule.validation_command,
            "measurement_task_id": self.rule.measurement_task_id,
            "command": shlex.join(self.command),
        }


@dataclass(frozen=True)
class CodexExecutionResult:
    usage_run: UsageRun
    response: str


def select_task_routing_rule(
    rules: Iterable[TaskRoutingRule],
    task: str,
    *,
    task_id: str | None = None,
) -> TaskRoutingRule:
    available = list(rules)
    if task_id:
        for rule in available:
            if rule.task_id == task_id:
                return rule
        raise ValueError(f"Unknown Codex routing task id: {task_id}")

    task_tokens = tokenize(task)
    scored = [
        (route_match_score(rule, task_tokens), -index, rule)
        for index, rule in enumerate(available)
    ]
    if not scored:
        raise ValueError("Codex routing manifest has no task rules.")
    score, _, selected = max(scored, key=lambda item: (item[0], item[1]))
    if score <= 0:
        raise ValueError(
            "Task did not match a routing rule. Pass --task-id for an explicit deterministic route."
        )
    return selected


def build_codex_dispatch(
    task: str,
    manifest_path: str | Path,
    *,
    project_root: str | Path,
    task_id: str | None = None,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> CodexDispatch:
    rules = load_task_routing_rules(Path(manifest_path))
    rule = select_task_routing_rule(rules, task, task_id=task_id)
    return CodexDispatch(
        rule=rule,
        task=task,
        project_root=Path(project_root).resolve(),
        model=model or rule.recommended_model,
        reasoning_effort=reasoning_effort or rule.reasoning_effort,
    )


def format_codex_dispatch(dispatch: CodexDispatch, output_format: str = "markdown") -> str:
    payload = dispatch.to_dict()
    if output_format == "json":
        return json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output_format == "shell":
        return payload["command"] + "\n"
    return "\n".join(
        [
            "# Codex Task Route",
            "",
            f"- Task class: `{payload['task_id']}` ({payload['task_name']})",
            f"- Context route: `{payload['context_route']}`",
            f"- Agent path: `{payload['agent']}`",
            f"- Model: `{payload['model']}`",
            f"- Reasoning: `{payload['reasoning_effort']}`",
            f"- Risk: `{payload['risk_level']}`",
            f"- Validation: `{payload['validation_command']}`",
            "",
            "```sh",
            payload["command"],
            "```",
            "",
        ]
    )


def run_codex_dispatch(
    dispatch: CodexDispatch,
    *,
    run_log_csv: str | Path,
    variant: str = "routed",
    quality_score: float = 0.0,
) -> CodexExecutionResult:
    started_at = datetime.now(timezone.utc)
    started = time.monotonic()
    completed = subprocess.run(
        dispatch.command,
        cwd=dispatch.project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed_seconds = max(0, round(time.monotonic() - started))
    events = parse_codex_jsonl(completed.stdout)
    usage = usage_from_events(events)
    response = response_from_events(events)
    run_id = thread_id_from_events(events) or f"local-{started_at.strftime('%Y%m%dT%H%M%SZ')}"
    run = UsageRun(
        run_id=run_id,
        run_date=started_at.isoformat(),
        task_id=dispatch.rule.measurement_task_id,
        task_name=dispatch.rule.task_name,
        variant=variant,
        route=dispatch.rule.recommended_context_route,
        model=dispatch.model,
        exact_input_tokens=max(0, usage["input_tokens"] - usage["cached_input_tokens"]),
        exact_cached_input_tokens=usage["cached_input_tokens"],
        exact_output_tokens=usage["output_tokens"],
        tool_calls=count_tool_calls(events),
        file_reads=count_file_reads(events),
        full_file_reads=0,
        tool_output_chars=count_tool_output_chars(events),
        response_chars=len(response),
        elapsed_seconds=elapsed_seconds,
        success="yes" if completed.returncode == 0 else "no",
        quality_score=quality_score,
        notes=(
            f"task_route={dispatch.rule.task_id}; agent={dispatch.rule.recommended_agent}; "
            f"exit_code={completed.returncode}"
        ),
    )
    append_usage_run(Path(run_log_csv), run)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "Codex task failed without stderr output."
        raise RuntimeError(
            f"Routed Codex task failed with exit code {completed.returncode}: {detail}"
        )
    return CodexExecutionResult(usage_run=run, response=response)


def format_routed_prompt(rule: TaskRoutingRule, task: str) -> str:
    return "\n".join(
        [
            "Use the project Codex task route below.",
            f"Route: {rule.task_id}",
            f"Context route: {rule.recommended_context_route}",
            f"Recommended agent path: {rule.recommended_agent}",
            f"Required validation: {rule.validation_command}",
            "",
            f"Task: {task}",
        ]
    )


def tokenize(value: str) -> set[str]:
    return {
        token
        for token in TOKEN_PATTERN.findall(value.lower())
        if token not in IGNORED_ROUTE_WORDS and len(token) > 1
    }


def route_match_score(rule: TaskRoutingRule, task_tokens: set[str]) -> int:
    trigger_tokens = tokenize(f"{rule.task_name} {rule.trigger}")
    return len(task_tokens & trigger_tokens)


def parse_codex_jsonl(raw: str) -> list[dict]:
    events = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def usage_from_events(events: list[dict]) -> dict[str, int]:
    usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    for event in events:
        candidate = event.get("usage")
        if not isinstance(candidate, dict):
            turn = event.get("turn")
            candidate = turn.get("usage") if isinstance(turn, dict) else None
        if not isinstance(candidate, dict):
            continue
        usage = {
            "input_tokens": integer_value(candidate.get("input_tokens")),
            "cached_input_tokens": integer_value(candidate.get("cached_input_tokens")),
            "output_tokens": integer_value(candidate.get("output_tokens")),
        }
    return usage


def response_from_events(events: list[dict]) -> str:
    messages = []
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "agent_message":
            continue
        text = item.get("text")
        if isinstance(text, str):
            messages.append(text)
    return "\n".join(messages)


def thread_id_from_events(events: list[dict]) -> str:
    for event in events:
        if event.get("type") == "thread.started" and isinstance(event.get("thread_id"), str):
            return event["thread_id"]
    return ""


def count_tool_calls(events: list[dict]) -> int:
    return sum(
        1
        for event in events
        if event.get("type") == "item.completed"
        and isinstance(event.get("item"), dict)
        and event["item"].get("type") not in {"agent_message", "reasoning"}
    )


def count_file_reads(events: list[dict]) -> int:
    read_commands = {"cat", "head", "sed", "tail", "rg"}
    count = 0
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict) or item.get("type") != "command_execution":
            continue
        command = str(item.get("command", "")).strip()
        if command and command.split()[0] in read_commands:
            count += 1
    return count


def count_tool_output_chars(events: list[dict]) -> int:
    total = 0
    for event in events:
        item = event.get("item")
        if not isinstance(item, dict):
            continue
        output = item.get("aggregated_output")
        if isinstance(output, str):
            total += len(output)
    return total


def append_usage_run(path: Path, run: UsageRun) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RUN_COLUMNS)
        if not exists:
            writer.writeheader()
        writer.writerow(run.to_row())


def integer_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
