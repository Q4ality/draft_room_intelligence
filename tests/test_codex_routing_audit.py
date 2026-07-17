import os

from draft_room_intelligence.reports.codex_routing_audit import write_codex_routing_audit


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def create_routing_project(root):
    write_text(root / "AGENTS.md", "# Guide\n")
    write_text(root / "docs/codex_routing.md", "# Routing\n")
    write_text(root / "docs/codex_usage_measurement.md", "# Usage\n")
    write_text(root / "data/reference/codex_context_routes.csv", "route_id\ncodex-routing\n")
    write_text(root / "data/reference/codex_task_routing.csv", "task_id\nsmall-edit\n")
    write_text(
        root / ".codex/config.toml",
        """
model = "gpt-5.6-sol"
model_reasoning_effort = "medium"
plan_mode_reasoning_effort = "high"
model_verbosity = "low"
tool_output_token_limit = 6000

[agents]
max_threads = 3
max_depth = 1

[agents.kb_explorer]
description = "Explorer"
config_file = "./agents/kb-explorer.toml"

[agents.reviewer]
description = "Reviewer"
config_file = "./agents/reviewer.toml"
""",
    )
    for name, file_name in [("kb_explorer", "kb-explorer.toml"), ("reviewer", "reviewer.toml")]:
        write_text(
            root / ".codex/agents" / file_name,
            f'''
name = "{name}"
description = "Agent"
developer_instructions = """
Do the work.
"""
''',
        )
    for skill in ["prepare-draft-demo-data", "project-context", "validate-change", "debug-ingestion"]:
        write_text(root / "skills" / skill / "SKILL.md", f"---\nname: {skill}\ndescription: Test\n---\n")
        link_dir = root / ".agents" / "skills"
        link_dir.mkdir(parents=True, exist_ok=True)
        os.symlink(f"../../skills/{skill}", link_dir / skill)


def test_write_codex_routing_audit_passes_valid_setup(tmp_path):
    create_routing_project(tmp_path)

    report = write_codex_routing_audit(tmp_path, tmp_path / "report")

    assert report.passed
    assert report.failed_count == 0
    assert (tmp_path / "report" / "summary.md").exists()
    assert (tmp_path / "report" / "checks.csv").exists()


def test_write_codex_routing_audit_fails_broken_skill_link(tmp_path):
    create_routing_project(tmp_path)
    (tmp_path / ".agents" / "skills" / "project-context").unlink()
    os.symlink("../../wrong/project-context", tmp_path / ".agents" / "skills" / "project-context")

    report = write_codex_routing_audit(tmp_path, tmp_path / "report")

    assert not report.passed
    failed = [check for check in report.checks if check.status == "fail"]
    assert len(failed) == 1
    assert failed[0].check_id == "skill_project-context"
    assert "unexpected symlink target" in failed[0].detail
