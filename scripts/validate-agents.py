#!/usr/bin/env python3
"""Validate agent .md and skill SKILL.md files against Anthropic's frontmatter spec.

Per MIT-413, this validator was rewritten to match Anthropic's published agent
and skill spec (research/agent-skill-spec-ground-truth-MIT-410.md), and
re-aligned 2026-06-19 to the June-2026 spec (research/
agent-spec-currency-2026-06.md): agent tool restriction is now `tools` /
`disallowedTools` (kebab `allowed-tools` is skills-only), `color` and
`skills` became official agent fields, and permissionMode/maxTurns/
mcpServers/memory/background/isolation/initialPrompt were added.

Checks performed:
  - HARD: frontmatter parses with strict YAML (yaml.safe_load).
  - HARD: required keys present (`name`, `description`).
  - HARD (agents): skill-only keys (`allowed-tools`, `when_to_use`, ...) —
    silently ignored by the loader, so the author's intended restriction or
    behavior never takes effect (this shipped MIT-433's restrictions inert).
  - HARD (skills only): combined len(description) + len(when_to_use) ≤ 1536
    chars. This is Anthropic's documented router truncation cap.
  - WARN (agents): description ≤ 2000 chars. No documented spec cap, but the
    spirit is "tight"; 2000 is generous to allow MIT-415 gradual migration.
  - WARN (agents): `color` outside the official 8-value enum (UI ignores it).
  - WARN: description contains XML tags (tracked separately under MIT-393).
  - WARN: non-spec frontmatter keys (grandfathered files; new files HARD).

Carve-out:
  - `scope:` on agents is an inc-repo extension consumed by install.sh's
    `is_org_agent` awk helper (filters which agents install at user scope
    by default). The validator accepts it without warning. See install.sh.

Exit codes:
  0 — no hard failures (warnings allowed)
  1 — at least one hard failure
  2 — script error (missing dir, etc.)

Usage:
  python3 scripts/validate-agents.py            # human-readable report
  python3 scripts/validate-agents.py --json     # machine-readable
  python3 scripts/validate-agents.py --quiet    # only print failures
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CATEGORIES = [
    "engineering", "product", "marketing", "sales", "testing", "writing",
    "design", "project-management", "studio-operations", "bonus",
]
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
XML_TAG_RE = re.compile(r"<[a-zA-Z/]")

# Grandfather baseline: files that currently carry non-spec frontmatter
# keys. Listed here → WARN (existing repo debt; tracked by MIT-412 + MIT-415).
# Not listed but carrying non-spec keys → HARD-fail (new debt). Shrinks as
# MIT-412 and MIT-415 progress; when both lists are empty, delete the file
# and tighten the check globally.
BASELINE_PATH = Path(__file__).resolve().parent / "validate-agents-baseline.json"

# Per Anthropic sub-agents.md spec
# (https://code.claude.com/docs/en/sub-agents.md → "Supported frontmatter
# fields"), re-verified 2026-06-19 (see research/agent-spec-currency-2026-06.md).
# NOTE the June-2026 spec changes vs the MIT-410-era snapshot:
#   - tool restriction is `tools` (allowlist) + `disallowedTools` (denylist,
#     camelCase). `allowed-tools`/`disallowed-tools` are SKILL fields and are
#     silently ignored on agents.
#   - `color`, `skills` are now official agent fields (un-grandfathered).
#   - new fields: permissionMode, maxTurns, mcpServers, memory, background,
#     isolation, initialPrompt.
#   - `user-invocable`, `disable-model-invocation`, `context`, `agent`,
#     `paths` are skills-only; no longer accepted on agents.
AGENT_SPEC_KEYS = {
    "name", "description", "tools", "disallowedTools", "model",
    "permissionMode", "maxTurns", "skills", "mcpServers", "hooks",
    "memory", "background", "effort", "isolation", "color", "initialPrompt",
}

# Official display-color enum for agents (sub-agents.md `color` row).
# Off-enum values are silently ignored by the UI — WARN so authors notice.
AGENT_COLOR_ENUM = {
    "red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan",
}

# Skill-side fields that are silently ignored if placed on an AGENT. Worse
# than unknown keys: the author believes a restriction/behavior is active
# when it is not (this bit MIT-433 — 22 agents shipped `allowed-tools`
# restrictions that never took effect). Flagged with a targeted message.
AGENT_SKILL_ONLY_KEYS = {
    "allowed-tools", "disallowed-tools", "user-invocable",
    "disable-model-invocation", "context", "agent", "paths", "when_to_use",
}

# Per Anthropic skills.md spec
# (https://code.claude.com/docs/en/skills.md → "Frontmatter reference").
SKILL_SPEC_KEYS = {
    "name", "description", "when_to_use", "argument-hint", "arguments",
    "disable-model-invocation", "user-invocable",
    "allowed-tools", "disallowed-tools",
    "model", "effort", "context", "agent", "hooks", "paths", "shell",
    # Distribution metadata per Anthropic's Jan 2026 skills guide and
    # the org-wide deployment feature shipped Dec 2025. Optional fields;
    # accept without warning. Added via MIT-437.
    "version", "deprecation-notice",
}

# inc-repo extension. `scope:` on agents is consumed by install.sh's
# is_org_agent awk helper to decide which agents install at user scope
# by default (org vs project). Not in Anthropic's spec but load-bearing
# for our installer — keep as an explicit carve-out so the validator
# doesn't WARN on agents that legitimately use it.
INC_EXTENSION_KEYS = {"scope"}

# Agent description char budget. Anthropic doesn't publish a cap for agents
# (only skills are documented at 1,536 combined). 2000 is the inc-repo
# guideline — tight enough to keep routing context lean, generous enough
# that MIT-415 can rewrite the 52 over-spec descriptions gradually.
AGENT_DESCRIPTION_MAX_CHARS = 2000

# Skill description char budget. Anthropic's documented hard cap:
# `description` + `when_to_use` together are truncated at 1,536 chars in
# the skill listing (see https://code.claude.com/docs/en/skills.md). We
# treat exceeding this as a HARD failure because content past the cap is
# silently dropped from the router's view.
SKILL_DESCRIPTION_MAX_CHARS = 1536


# Grandfathered debt is tracked in scripts/validate-agents-baseline.json:
# files listed there get WARN on non-spec keys (existing debt, tracked by
# MIT-412 and MIT-415); files NOT listed get HARD-fail (new debt). This
# keeps the validator honest about the spec while letting the existing 52
# agents migrate gradually. When the baseline empties, delete it and the
# code path here collapses to "all non-spec keys hard-fail."


def load_baseline() -> dict[str, set[str]]:
    """Read the grandfather baseline. Returns {file_path: {non_spec_keys}}.
    Missing file → empty (no grandfathered debt; all non-spec keys hard-fail)."""
    if not BASELINE_PATH.is_file():
        return {}
    data = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    out: dict[str, set[str]] = {}
    for entry in data.get("grandfathered_agents", []) + data.get("grandfathered_skills", []):
        out[entry["file"]] = set(entry["non_spec_keys"])
    return out


def _extract_first_paragraph(text: str) -> str:
    """For skills missing a frontmatter description, Anthropic's spec says
    the first paragraph of markdown content is the fallback. Used to avoid
    hard-failing spec-valid skills that rely on this behavior."""
    m = FRONTMATTER_RE.match(text)
    body = text[m.end():] if m else text
    paras = re.split(r"\n\s*\n", body.lstrip(), maxsplit=1)
    return paras[0].strip() if paras else ""


def collect_agent_files() -> list[Path]:
    """Walk agent category dirs and return all *.md files (minus READMEs)."""
    files: list[Path] = []
    for cat in CATEGORIES:
        cat_dir = REPO_ROOT / cat
        if not cat_dir.is_dir():
            continue
        for p in sorted(cat_dir.glob("*.md")):
            if p.name == "README.md":
                continue
            files.append(p)
    return files


def collect_skill_files() -> list[Path]:
    """Walk skills/<name>/SKILL.md and return paths."""
    files: list[Path] = []
    skills_dir = REPO_ROOT / "skills"
    if not skills_dir.is_dir():
        return files
    for sub in sorted(skills_dir.iterdir()):
        if not sub.is_dir():
            continue
        skill_md = sub / "SKILL.md"
        if skill_md.is_file():
            files.append(skill_md)
    return files


def _parse_frontmatter(path: Path) -> tuple[dict | None, list[str], list[str]]:
    """Common frontmatter parse step. Returns (parsed, hard_errors, warnings)."""
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    hard: list[str] = []
    warn: list[str] = []
    if not m:
        hard.append("no frontmatter delimited by '---' lines")
        return None, hard, warn
    block = m.group(1)
    try:
        parsed = yaml.safe_load(block)
    except yaml.YAMLError as exc:
        msg = str(exc).splitlines()[0] if "\n" in str(exc) else str(exc)
        hard.append(f"strict YAML parse failed: {msg}")
        return None, hard, warn
    if not isinstance(parsed, dict):
        hard.append(
            f"frontmatter did not parse to a YAML mapping (got {type(parsed).__name__})"
        )
        return None, hard, warn
    return parsed, hard, warn


def validate_agent(path: Path, baseline: dict[str, set[str]]) -> dict:
    """Check a single agent file. Returns hard_errors and warnings.

    Per Anthropic sub-agents.md, `name` is optional (defaults to the
    filename-derived identifier). `description` is the only required
    field — without it the router can't route to the agent."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    parsed, hard, warn = _parse_frontmatter(path)
    if parsed is None:
        return {"kind": "agent", "file": rel, "hard_errors": hard, "warnings": warn}

    name = parsed.get("name")
    desc = parsed.get("description")
    # name is optional per spec; only WARN if present-but-malformed
    if "name" in parsed and (not isinstance(name, str) or not name.strip()):
        warn.append("'name' field present but non-string / whitespace-only")
    if not isinstance(desc, str) or not desc.strip():
        hard.append("missing required 'description' field (or non-string / whitespace-only)")
    else:
        if len(desc) > AGENT_DESCRIPTION_MAX_CHARS:
            warn.append(
                f"description is {len(desc)} chars (inc guideline: "
                f"≤{AGENT_DESCRIPTION_MAX_CHARS}); see MIT-415"
            )
        if XML_TAG_RE.search(desc):
            warn.append("description contains XML tags (Anthropic spec: none); see MIT-415")
    # Skill-only fields on an agent are silently ignored by the loader —
    # the author believes a restriction/behavior is active when it isn't.
    # HARD-fail: this is exactly how MIT-433's `allowed-tools` restrictions
    # shipped inactive on 22 agents.
    skill_only = sorted(k for k in parsed.keys() if k in AGENT_SKILL_ONLY_KEYS)
    if skill_only:
        hard.append(
            f"skill-only frontmatter keys {skill_only!r} on an AGENT are "
            "silently ignored (tool restriction on agents is `tools` / "
            "`disallowedTools` per sub-agents.md). Rename or move to a "
            "SKILL.md."
        )

    # Off-enum colors are silently ignored by the UI.
    if "color" in parsed and parsed.get("color") not in AGENT_COLOR_ENUM:
        warn.append(
            f"color '{parsed.get('color')}' is not in the official enum "
            f"{sorted(AGENT_COLOR_ENUM)} and will be ignored by the UI"
        )

    # Non-spec keys. Allow `scope` (inc carve-out). For other non-spec keys:
    # grandfathered files get WARN, new files get HARD. This stops new debt
    # while allowing existing debt to migrate gradually.
    allowed = AGENT_SPEC_KEYS | INC_EXTENSION_KEYS | AGENT_SKILL_ONLY_KEYS
    unknown = sorted(k for k in parsed.keys() if k not in allowed)
    if unknown:
        grandfathered_keys = baseline.get(rel, set())
        new_debt = [k for k in unknown if k not in grandfathered_keys]
        existing_debt = [k for k in unknown if k in grandfathered_keys]
        if new_debt:
            hard.append(
                f"non-spec frontmatter keys {new_debt!r} on agent — Anthropic's "
                "sub-agents.md does not list these; the loader silently "
                "ignores them. This file is not "
                "in scripts/validate-agents-baseline.json so we treat the "
                "key as NEW debt and HARD-fail. Either use the spec-correct "
                "field name, or add the file to the baseline if grandfathering "
                "is intentional."
            )
        if existing_debt:
            warn.append(
                f"non-spec frontmatter keys {existing_debt!r} on agent — "
                "grandfathered per scripts/validate-agents-baseline.json. "
                "Tracked under MIT-412 (tools field) / MIT-415 (rewrite); "
                "shrink the baseline as those land."
            )

    return {"kind": "agent", "file": rel, "hard_errors": hard, "warnings": warn}


def _check_portability(text: str) -> list[str]:
    """Opt-in scan for portability issues per MIT-437. Returns informational
    warnings — does not affect exit code. Caller decides whether to surface."""
    findings: list[str] = []
    # Absolute paths outside the skill (typical user-specific paths).
    abs_path_re = re.compile(r"(?<![\w/])/(home|Users)/[a-zA-Z0-9._-]+/")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if abs_path_re.search(line):
            findings.append(
                f"line {lineno}: hardcoded user-specific absolute path "
                "(consider $HOME or relative paths for portability)"
            )
            break  # one finding per file is enough for the signal
    # `!` shell references with non-portable commands (heuristic: gnu-specific
    # tools that don't exist on macOS without homebrew).
    for tool in ("gsed", "gawk", "greadlink"):
        if f"!`{tool}" in text or f"! `{tool}" in text:
            findings.append(
                f"dynamic context uses `{tool}` — not portable to macOS "
                "without homebrew aliases"
            )
    return findings


def validate_skill(path: Path, baseline: dict[str, set[str]],
                   check_portability: bool = False) -> dict:
    """Check a single SKILL.md. Returns hard_errors and warnings.

    Per Anthropic skills.md, `name` is optional (defaults to directory name)
    and `description` is "recommended" — if omitted it falls back to the
    first paragraph of the markdown body. Validator only hard-fails when
    there is no usable routing text from either source.

    When `check_portability=True`, runs the opt-in portability scan from
    MIT-437 and appends any findings as informational warnings."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    parsed, hard, warn = _parse_frontmatter(path)
    if parsed is None:
        return {"kind": "skill", "file": rel, "hard_errors": hard, "warnings": warn}

    name = parsed.get("name")
    desc = parsed.get("description")
    when_to_use = parsed.get("when_to_use", "")
    if "name" in parsed and (not isinstance(name, str) or not name.strip()):
        warn.append("'name' field present but non-string / whitespace-only")
    if "when_to_use" in parsed and not isinstance(when_to_use, str):
        warn.append("'when_to_use' field present but not a string")
        when_to_use = ""
    # Description has a body-fallback per spec. Only hard-fail when both
    # frontmatter description and body first-paragraph are empty.
    has_fm_desc = isinstance(desc, str) and bool(desc.strip())
    body_fallback = ""
    if not has_fm_desc:
        text = path.read_text(encoding="utf-8")
        body_fallback = _extract_first_paragraph(text)
    effective_desc = desc if has_fm_desc else body_fallback
    if not effective_desc.strip():
        hard.append(
            "missing 'description' field AND no usable first-paragraph body "
            "fallback. Per Anthropic skills.md, description is recommended "
            "but can fall back to body content."
        )
    else:
        if not has_fm_desc:
            warn.append(
                "frontmatter 'description' missing — falling back to first "
                "paragraph of body per spec, but explicit frontmatter is "
                "strongly recommended."
            )
        desc_len = len(effective_desc)
        wtu_len = len(when_to_use) if isinstance(when_to_use, str) else 0
        combined = desc_len + wtu_len
        if combined > SKILL_DESCRIPTION_MAX_CHARS:
            hard.append(
                f"description + when_to_use is {combined} chars "
                f"({desc_len} + {wtu_len}); Anthropic spec caps this at "
                f"{SKILL_DESCRIPTION_MAX_CHARS} (router truncates above)."
            )
        if XML_TAG_RE.search(effective_desc):
            warn.append("description contains XML tags (Anthropic spec: none); see MIT-415")

    # Non-spec keys on skills: same grandfather model as agents. Listed
    # files WARN; new files HARD.
    unknown = sorted(k for k in parsed.keys() if k not in SKILL_SPEC_KEYS)
    if unknown:
        grandfathered_keys = baseline.get(rel, set())
        new_debt = [k for k in unknown if k not in grandfathered_keys]
        existing_debt = [k for k in unknown if k in grandfathered_keys]
        if new_debt:
            hard.append(
                f"non-spec frontmatter keys {new_debt!r} on skill — Anthropic's "
                "skills.md does not list these. NEW debt (file not in baseline) "
                "HARD-fails."
            )
        if existing_debt:
            warn.append(
                f"non-spec frontmatter keys {existing_debt!r} on skill — "
                "grandfathered per scripts/validate-agents-baseline.json."
            )

    if check_portability:
        text = path.read_text(encoding="utf-8")
        for finding in _check_portability(text):
            warn.append(f"portability: {finding}")

    return {"kind": "skill", "file": rel, "hard_errors": hard, "warnings": warn}


def _summarise(results: list[dict], kind: str) -> tuple[int, int, int]:
    """Return (clean, warn_only, hard_fail) counts for a kind."""
    subset = [r for r in results if r["kind"] == kind]
    clean = sum(1 for r in subset if not r["hard_errors"] and not r["warnings"])
    warn_only = sum(1 for r in subset if r["warnings"] and not r["hard_errors"])
    hard = sum(1 for r in subset if r["hard_errors"])
    return clean, warn_only, hard


def _count_grandfathered(results: list[dict]) -> int:
    """How many agents trip the non-spec-fields warning today.
    Surfaced once at startup as an MIT-412 progress signal."""
    return sum(
        1 for r in results
        if r["kind"] == "agent"
        and any("non-spec frontmatter keys" in w for w in r["warnings"])
    )


def emit_text(results: list[dict], quiet: bool) -> None:
    if not quiet:
        agents = [r for r in results if r["kind"] == "agent"]
        skills = [r for r in results if r["kind"] == "skill"]
        print(f"Validating {len(agents)} agents and {len(skills)} skills...\n")
        for r in results:
            tag = "agent" if r["kind"] == "agent" else "skill"
            if r["hard_errors"]:
                print(f"  ✗ HARD  [{tag}] {r['file']}")
                for e in r["hard_errors"]:
                    print(f"          → {e}")
                for w in r["warnings"]:
                    print(f"          ⚠ {w}")
            elif r["warnings"]:
                print(f"  ⚠ WARN  [{tag}] {r['file']}")
                for w in r["warnings"]:
                    print(f"          ⚠ {w}")
            else:
                print(f"  ✓       [{tag}] {r['file']}")
        print()
    else:
        for r in results:
            if r["hard_errors"]:
                tag = "agent" if r["kind"] == "agent" else "skill"
                print(f"  ✗ HARD  [{tag}] {r['file']}")
                for e in r["hard_errors"]:
                    print(f"          → {e}")

    a_clean, a_warn, a_hard = _summarise(results, "agent")
    s_clean, s_warn, s_hard = _summarise(results, "skill")
    print(
        f"Summary: "
        f"Agents: {a_clean} clean, {a_warn} warn, {a_hard} hard-fail. "
        f"Skills: {s_clean} clean, {s_warn} warn, {s_hard} hard-fail."
    )

    grandfathered = _count_grandfathered(results)
    if grandfathered:
        print(
            f"\nNote: {grandfathered} grandfathered files currently carry "
            "non-spec frontmatter keys (tracked via "
            "scripts/validate-agents-baseline.json). New debt HARD-fails; "
            "existing debt WARNs and is tracked by MIT-412 (tools field) "
            "and MIT-415 (agent rewrite). When the baseline empties, delete "
            "it and tighten the validator globally."
        )

    if a_hard or s_hard:
        print("\nHard failures block merge. Fix and re-run.", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog=(
            "Validates against Anthropic's published agent + skill spec "
            "(see research/agent-skill-spec-ground-truth-MIT-410.md). "
            "Skills HARD-fail if combined description + when_to_use > "
            f"{SKILL_DESCRIPTION_MAX_CHARS} chars (router cap). Agents WARN "
            f"if description > {AGENT_DESCRIPTION_MAX_CHARS} chars (inc "
            "guideline). Non-spec frontmatter keys WARN today; agent "
            "non-spec keys will be tightened to HARD after MIT-412."
        ),
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument("--quiet", action="store_true",
                        help="only print files with hard failures")
    parser.add_argument("--check-portability", action="store_true",
                        help=(
                            "opt-in portability scan for skills: flags "
                            "absolute paths, machine-specific hardcoded "
                            "paths, and shell-`!` references that may not "
                            "exist on typical systems. Adds informational "
                            "warnings; does not change exit code. Added "
                            "via MIT-437 per Anthropic skills guide."
                        ))
    args = parser.parse_args()

    agent_files = collect_agent_files()
    skill_files = collect_skill_files()
    if not agent_files and not skill_files:
        print("error: no agent or skill files found", file=sys.stderr)
        return 2

    baseline = load_baseline()
    results: list[dict] = []
    results.extend(validate_agent(p, baseline) for p in agent_files)
    results.extend(
        validate_skill(p, baseline, check_portability=args.check_portability)
        for p in skill_files
    )
    hard_count = sum(1 for r in results if r["hard_errors"])

    if args.json:
        a_clean, a_warn, a_hard = _summarise(results, "agent")
        s_clean, s_warn, s_hard = _summarise(results, "skill")
        print(json.dumps({
            "total": len(results),
            "hard_failures": hard_count,
            "warnings": sum(len(r["warnings"]) for r in results),
            "agents": {"clean": a_clean, "warn": a_warn, "hard": a_hard},
            "skills": {"clean": s_clean, "warn": s_warn, "hard": s_hard},
            "results": results,
        }, indent=2))
    else:
        emit_text(results, args.quiet)

    return 1 if hard_count else 0


if __name__ == "__main__":
    sys.exit(main())
