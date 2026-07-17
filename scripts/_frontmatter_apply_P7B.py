"""P7.B frontmatter apply: prepend YAML frontmatter to 19 mcp-common docs.

User-authorized via the P7.B cross-repo playbook (session-buddy plan
2026-07-16-p7-cross-repo-playbook.md). Mechanical. Reads each file, prepends a
uniform frontmatter block + adds a trailing HTML legacy comment on the first
`**Status**` heading so the validator's --allow-nonstandard mode stays green.

Topic defaults follow the playbook Section 3 conventions for the mcp-common
shared-library layout: many docs are historical migration summaries (mcp-design
or oneiric-config), some are canonical user-facing guides, and the schema files
are always status: active / role: canonical / topic: lifecycle.
"""

from __future__ import annotations

from pathlib import Path

FM_TEMPLATE = (
    "---\n"
    "status: {status}\n"
    "role: {role}\n"
    "date: 2026-07-16\n"
    "last_reviewed: 2026-07-17\n"
    "superseded_by: null\n"
    "blocks_on: []\n"
    "topic: {topic}\n"
    "---\n"
    "\n"
)

# (status, role, topic) per file. See playbook Section 3 for the matrix.
ASSIGNMENTS: dict[str, tuple[str, str, str]] = {
    # docs/ loose files: migration summaries and historical completion reports.
    "docs/MCP_SERVER_MIGRATION_SUMMARY.md":
        ("complete", "historical", "mcp-design"),
    "docs/MIGRATION_COMPLETE_SUMMARY.md":
        ("complete", "historical", "mcp-design"),
    "docs/ONEIRIC_CLI_AUDIT_RESPONSE.md":
        ("complete", "historical", "oneiric-config"),
    "docs/ONEIRIC_CLI_FACTORY_IMPLEMENTATION.md":
        ("complete", "historical", "oneiric-config"),
    "docs/ONEIRIC_CLI_FACTORY_PLAN.md":
        ("complete", "historical", "oneiric-config"),
    "docs/ONEIRIC_CLI_FACTORY_SPEC_REVIEW.md":
        ("complete", "historical", "oneiric-config"),
    "docs/PHASE1_COMPLETE_SUMMARY.md":
        ("complete", "historical", "mcp-design"),
    "docs/README.md":
        ("active", "canonical", "lifecycle"),
    "docs/SECURITY_IMPLEMENTATION.md":
        ("active", "canonical", "auth"),
    "docs/SERVER_INTEGRATION.md":
        ("active", "canonical", "mcp-design"),
    "docs/iterm2-applescript-protocol.md":
        ("active", "canonical", "mcp-design"),
    # docs/guides/ — user-facing guides, canonical.
    "docs/guides/server-development.md":
        ("active", "canonical", "mcp-design"),
    "docs/guides/usage-profiles.md":
        ("active", "canonical", "lifecycle"),
    # docs/reference/ — living reference docs.
    "docs/reference/COVERAGE_POLICY.md":
        ("active", "canonical", "lifecycle"),
    "docs/reference/service-dependencies.md":
        ("active", "canonical", "lifecycle"),
    # docs/schemas/ — source of truth, always active canonical lifecycle.
    "docs/schemas/document-frontmatter-v1.md":
        ("active", "canonical", "lifecycle"),
    "docs/schemas/topic-vocabulary-v1.md":
        ("active", "canonical", "lifecycle"),
    # mcp/contracts/ — shared contract spec.
    "mcp/contracts/code_graph_tools.md":
        ("active", "canonical", "mcp-design"),
    # examples/README.md — examples directory entry.
    "examples/README.md":
        ("active", "canonical", "lifecycle"),
}


def add_legacy_comment(text: str) -> str:
    """Append a trailing HTML legacy comment on the first '**Status**' line."""
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("**Status**") or stripped.startswith("**Status:"):
            original = stripped.rstrip("\n")
            if "-- see YAML frontmatter" not in original:
                lines[i] = original + "  <!-- legacy status — see YAML frontmatter -->\n"
            break
    return "".join(lines)


def main() -> None:
    repo_root = Path("/Users/les/Projects/mcp-common")
    results: list[tuple[str, str, str, str]] = []
    for rel_path, (status, role, topic) in ASSIGNMENTS.items():
        path = repo_root / rel_path
        if not path.is_file():
            print(f"SKIP (missing): {rel_path}")
            continue
        original = path.read_text(encoding="utf-8")
        if original.lstrip().startswith("---\n"):
            print(f"SKIP (already has frontmatter): {rel_path}")
            continue
        frontmatter = FM_TEMPLATE.format(
            status=status, role=role, topic=topic
        )
        body_with_comment = add_legacy_comment(original)
        new_content = frontmatter + body_with_comment
        path.write_text(new_content, encoding="utf-8")
        results.append((rel_path, status, role, topic))
    print(f"\nEdited {len(results)} files:")
    for rel, st, rl, tp in results:
        print(f"  {rel}: status={st} role={rl} topic={tp}")


if __name__ == "__main__":
    main()