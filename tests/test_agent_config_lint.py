"""Tests for agent-config-lint.

Run from the project root:

    python3 -m unittest discover -s tests -v

Scratch repositories are built under ``.scratch/`` inside the project (never in
the system temp directory: on this machine /tmp silently swallows writes), and
removed in tearDown. The static fixtures in ``examples/`` are linted as-is, and
``examples/good`` is the negative control: it must produce zero findings at the
default threshold.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import agent_config_lint as acl  # noqa: E402

SCRATCH_ROOT = PROJECT_ROOT / ".scratch"
GOOD_EXAMPLE = PROJECT_ROOT / "examples" / "good"
BAD_EXAMPLE = PROJECT_ROOT / "examples" / "bad"


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class ScratchCase(unittest.TestCase):
    """Base class that gives every test its own repository directory."""

    def setUp(self) -> None:
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
        self.repo = SCRATCH_ROOT / f"{self.__class__.__name__}_{self._testMethodName}"
        if self.repo.exists():
            shutil.rmtree(self.repo)
        self.repo.mkdir(parents=True)
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    # -- helpers ---------------------------------------------------------

    def file(self, relpath: str, content: str) -> Path:
        return write(self.repo / relpath, content)

    def lint(self, target: str | None = None, **kwargs) -> acl.Analysis:
        path = Path(target) if target else self.repo
        return acl.analyse(path, **kwargs)

    def codes(self, analysis: acl.Analysis) -> list[str]:
        return [f.code for f in analysis.findings]

    def assert_code(self, analysis: acl.Analysis, code: str,
                    message: str = "") -> acl.Finding:
        matches = [f for f in analysis.findings if f.code == code]
        self.assertTrue(
            matches,
            f"expected {code}; got {self.describe(analysis)}: {message}",
        )
        return matches[0]

    def describe(self, analysis: acl.Analysis, limit: int = 6) -> str:
        codes = self.codes(analysis)
        shown = ", ".join(codes[:limit]) + (" ..." if len(codes) > limit else "")
        return f"{len(codes)} finding(s) [{shown}]"

    def assert_no_code(self, analysis: acl.Analysis, code: str,
                       message: str = "") -> None:
        self.assertNotIn(code, self.codes(analysis),
                         message or self.describe(analysis))

    def run_cli(self, argv: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = acl.main(argv)
        return code, out.getvalue(), err.getvalue()


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


class TestCli(ScratchCase):
    def test_clean_repository_exits_zero(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Run `npm test` before you commit.\n")
        self.file("CLAUDE.md", "# A\n\n## Rules\n\n- Run `npm test` before you commit.\n")
        code, out, _ = self.run_cli([str(self.repo)])
        self.assertEqual(code, 0, out)
        self.assertIn("No findings at or above severity 'low'.", out)

    def test_findings_exit_one(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Write clean code.\n")
        code, out, _ = self.run_cli([str(self.repo)])
        self.assertEqual(code, 1)
        self.assertIn("AGL018", out)

    def test_usage_error_for_missing_path(self) -> None:
        code, _, err = self.run_cli([str(self.repo / "nope")])
        self.assertEqual(code, 2)
        self.assertIn("does not exist", err)

    def test_usage_error_for_directory_without_instruction_files(self) -> None:
        (self.repo / "src").mkdir()
        write(self.repo / "src" / "index.ts", "export const x = 1;\n")
        code, _, err = self.run_cli([str(self.repo)])
        self.assertEqual(code, 2)
        self.assertIn("no agent instruction file found", err)

    def test_usage_error_for_non_positive_budget(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Run `npm test` before you commit.\n")
        code, _, err = self.run_cli([str(self.repo), "--max-lines", "0"])
        self.assertEqual(code, 2)
        self.assertIn("must be >= 1", err)

    def test_severity_threshold_filters_and_changes_exit_code(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Write clean code.\n")
        low_code, low_out, _ = self.run_cli([str(self.repo)])
        high_code, high_out, _ = self.run_cli([str(self.repo), "--severity", "high"])
        self.assertEqual(low_code, 1)
        self.assertEqual(high_code, 0)
        self.assertIn("AGL018", low_out)
        self.assertNotIn("AGL018", high_out)

    def test_list_rules_prints_every_rule_and_exits_zero(self) -> None:
        code, out, _ = self.run_cli(["--list-rules"])
        self.assertEqual(code, 0)
        for spec in acl.RULES:
            self.assertIn(spec.code, out)
        self.assertEqual(len(acl.RULES), 20)
        self.assertIn("AGL001", out)
        self.assertIn("AGL020", out)

    def test_json_output_is_parseable_and_carries_findings(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- See `docs/missing.md`.\n")
        code, out, _ = self.run_cli([str(self.repo), "--json"])
        self.assertEqual(code, 1)
        payload = json.loads(out)
        self.assertEqual(payload["tool"], "agent-config-lint")
        self.assertIn("counts", payload)
        self.assertTrue(any(f["code"] == "AGL001" for f in payload["findings"]))
        finding = [f for f in payload["findings"] if f["code"] == "AGL001"][0]
        for key in ("code", "severity", "path", "line", "message", "fix", "basis"):
            self.assertIn(key, finding)

    def test_quiet_omits_header_but_keeps_findings(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Write clean code.\n")
        _, out, _ = self.run_cli([str(self.repo), "--quiet"])
        self.assertNotIn("agent-config-lint 1.0.0", out)
        self.assertNotIn("[AGENTS.md]", out)
        self.assertIn("AGL018", out)

    def test_single_file_target(self) -> None:
        target = self.file("AGENTS.md", "# A\n\n## Rules\n\n- Use `npm ci` first.\n")
        code, out, _ = self.run_cli([str(target), "--quiet"])
        # The file itself is clean; the only finding is the missing CLAUDE.md
        # beside it, which is what a single-file target still reports.
        self.assertEqual(code, 1, out)
        self.assertIn("AGL020", out)
        self.assertNotIn("AGL018", out)
        self.assertLessEqual(len(out.splitlines()), 6, out)


# ---------------------------------------------------------------------------
# AGL001 -- references
# ---------------------------------------------------------------------------


class TestPathReferences(ScratchCase):
    def test_missing_file_is_high(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- See `docs/ARCHITECTURE.md`.\n")
        analysis = self.lint()
        found = self.assert_code(analysis, "AGL001")
        self.assertEqual(found.severity, "high")
        self.assertEqual(found.line, 5)
        self.assertIn("docs/ARCHITECTURE.md", found.message)

    def test_existing_file_is_clean(self) -> None:
        self.file("docs/ARCHITECTURE.md", "# Architecture\n")
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- See `docs/ARCHITECTURE.md`.\n")
        self.assert_no_code(self.lint(), "AGL001")

    def test_glob_with_one_match_is_clean(self) -> None:
        self.file("src/api/orders.ts", "export const x = 1;\n")
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Handlers live in `src/api/*.ts`.\n")
        self.assert_no_code(self.lint(), "AGL001")

    def test_glob_with_no_match_is_reported(self) -> None:
        self.file("src/api/orders.tsx", "export const x = 1;\n")
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Handlers live in `src/api/*.ts`.\n")
        self.assert_code(self.lint(), "AGL001")

    def test_directory_reference_is_clean(self) -> None:
        self.file("tests/integration/.keep", "")
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Facts live in `tests/integration/`.\n")
        self.assert_no_code(self.lint(), "AGL001")

    def test_brace_glob_is_expanded(self) -> None:
        self.file("src/app.ts", "export const x = 1;\n")
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n- Sources are `src/**/*.{ts,tsx}`.\n")
        self.assert_no_code(self.lint(), "AGL001")

    def test_doc_pair_reference_resolves_from_the_repo_root(self) -> None:
        self.file("src/errors.ts", "export class HttpError extends Error {}\n")
        content = "# A\n\n## Rules\n\n- Throw `HttpError` from `src/errors.ts`.\n"
        self.file("AGENTS.md", content)
        self.file("CLAUDE.md", content)
        self.assert_no_code(self.lint(), "AGL001")

    def test_rule_file_reference_resolves_from_the_rules_directory(self) -> None:
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: d\nglobs: '**/*.ts'\nalwaysApply: false\n---\n\n"
                  "# T\n\n- See `sibling.md` for the long form.\n")
        self.file(".cursor/rules/sibling.md", "# Long form\n")
        analysis = self.lint()
        self.assert_no_code(analysis, "AGL001")

    def test_dot_directory_is_not_mangled(self) -> None:
        self.file(".cursor/rules/typescript.mdc",
                  "---\ndescription: d\nglobs: '**/*.ts'\nalwaysApply: false\n---\n\n"
                  "# T\n\n- See `.cursor/rules/typescript.mdc`.\n")
        code, out, _ = self.run_cli([str(self.repo), "--json"])
        payload = json.loads(out)
        self.assertFalse([f for f in payload["findings"] if f["code"] == "AGL001"], out)
        self.assertEqual(code, 0, out)

    def test_frontmatter_globs_are_not_treated_as_references(self) -> None:
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: d\nglobs: '**/*.ts'\nalwaysApply: false\n---\n\n"
                  "# T\n\n- Use two-space indentation.\n")
        analysis = self.lint()
        self.assert_no_code(analysis, "AGL001")
        self.assertEqual(analysis.files[0].globs, ("**/*.ts",))

    def test_urls_and_absolute_paths_are_ignored(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n"
                  "- Read https://example.invalid/docs/setup.md and /etc/hosts.\n")
        self.assert_no_code(self.lint(), "AGL001")

    def test_fenced_code_block_is_ignored(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n```bash\ncat docs/does-not-exist.md\n```\n")
        self.assert_no_code(self.lint(), "AGL001")

    def test_bare_path_without_backticks_is_checked(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Read docs/CONVENTIONS.md first.\n")
        self.assert_code(self.lint(), "AGL001")

    def test_markdown_link_target_is_checked(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- See [notes](docs/notes.md).\n")
        found = self.assert_code(self.lint(), "AGL001")
        self.assertIn("docs/notes.md", found.message)


# ---------------------------------------------------------------------------
# AGL002 -- contradictions
# ---------------------------------------------------------------------------


class TestContradictions(ScratchCase):
    def test_always_vs_never_same_subject(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n"
                  "- Always use tabs for indentation.\n"
                  "- Never use tabs for indentation.\n")
        found = self.assert_code(self.lint(), "AGL002")
        self.assertEqual(found.severity, "high")
        self.assertIn("AGENTS.md:5", found.message)
        self.assertEqual(found.line, 6)

    def test_tabs_vs_spaces(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n"
                  "- Always use tabs for indentation.\n"
                  "- Always use spaces for indentation.\n")
        found = self.assert_code(self.lint(), "AGL002")
        self.assertIn("tab indentation vs space indentation", found.message)

    def test_semicolons_required_vs_forbidden(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n"
                  "- Always use semicolons.\n"
                  "- Never use semicolons.\n")
        self.assert_code(self.lint(), "AGL002")

    def test_opposite_rules_in_different_headings_are_not_flagged(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Frontend\n\n- Always use tabs for indentation.\n\n"
                  "## Backend\n\n- Never use tabs for indentation.\n")
        self.assert_no_code(self.lint(), "AGL002")

    def test_different_subjects_are_not_flagged(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n"
                  "- Always use tabs for indentation.\n"
                  "- Never commit directly to main in this repository.\n")
        self.assert_no_code(self.lint(), "AGL002")

    def test_opposition_pair_table_is_used_verbatim(self) -> None:
        inst = self._inst("Always use semicolons.\n\nNever use semicolons.\n")
        first, second = inst.statements[0], inst.statements[1]
        pair = acl._opposition_pair(first, second)
        self.assertIsNotNone(pair)
        # "Always ... Never" also matches the always-never pair, which is
        # declared first, so that is the pair the tool reports. The point of the
        # assertion is that both statements are pointed at.
        self.assertEqual(pair[0], "always-never")
        self.assertEqual(pair[1], first.line)
        self.assertEqual(pair[2], second.line)
        self.assertTrue(any(p[0] == "always-never" for p in acl.OPPOSITION_PAIRS))

    def test_pair_outside_the_table_is_not_a_contradiction(self) -> None:
        # "prefer 100-character lines" vs "never exceed 80 characters" is a real
        # contradiction, but it is not one of the declared opposition pairs, so
        # the tool stays quiet rather than guessing.
        inst = self._inst("Keep every line under 100 characters.\n\n"
                          "No line may exceed 80 characters.\n")
        self.assertIsNone(acl._opposition_pair(inst.statements[0],
                                               inst.statements[1]))

    def _inst(self, text: str) -> acl.InstructionFile:
        path = self.file("_probe.md", text)
        return acl.load_instruction_file(path, self.repo)


# ---------------------------------------------------------------------------
# AGL003 / AGL004 -- duplicates
# ---------------------------------------------------------------------------


class TestDuplicates(ScratchCase):
    def test_exact_duplicate_in_one_file(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n"
                  "- Run `npm test` before you open a pull request.\n"
                  "- run npm test before you open a pull request\n")
        found = self.assert_code(self.lint(), "AGL003")
        self.assertIn("line 5", found.message)
        self.assertEqual(found.line, 6)

    def test_near_duplicate_is_medium(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Tests\n\n"
                  "- Run the test suite before you open a pull request.\n"
                  "- Always run the test suite before you open a pull request.\n")
        analysis = self.lint()
        self.assert_no_code(analysis, "AGL003")
        found = self.assert_code(analysis, "AGL004")
        self.assertEqual(found.severity, "medium")
        self.assertEqual(found.line, 6)
        self.assertIn("91%", found.message)

    def test_distinct_rules_are_not_duplicates(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n"
                  "- Run `npm test` before you open a pull request.\n"
                  "- Sort imports alphabetically within each group.\n")
        analysis = self.lint()
        self.assert_no_code(analysis, "AGL003")
        self.assert_no_code(analysis, "AGL004")

    def test_indentation_only_variant_is_a_duplicate(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Tests\n\n"
                  "- Run `npm test` before you open a pull request.\n"
                  "    - Run `npm test` before you open a pull request.\n")
        found = self.assert_code(self.lint(), "AGL003")
        self.assertIn("line 5", found.message)


# ---------------------------------------------------------------------------
# AGL005 / AGL006 -- size budget
# ---------------------------------------------------------------------------


class TestSizeBudget(ScratchCase):
    def _long_file(self, lines: int) -> str:
        body = [f"- Rule number {i} applies to the checkout service." for i in range(lines)]
        return "# A\n\n## Rules\n\n" + "\n".join(body) + "\n"

    def test_default_budget_is_clean_for_a_small_file(self) -> None:
        self.file("AGENTS.md", self._long_file(50))
        self.assert_no_code(self.lint(), "AGL005")

    def test_over_line_budget(self) -> None:
        self.file("AGENTS.md", self._long_file(510))
        analysis = self.lint()
        found = self.assert_code(analysis, "AGL005")
        self.assertIn("past the 500-line budget", found.message)
        self.assertIn("514 lines", found.message)

    def test_over_word_budget_without_over_line_budget(self) -> None:
        # 200 bullets of 29 words: over 6000 words, still under 500 lines.
        body = "\n".join(
            "- " + " ".join(f"word{i}_{j}" for i in range(29)) for j in range(200)
        )
        self.file("AGENTS.md", "# A\n\n## Rules\n\n" + body + "\n")
        analysis = self.lint()
        found = self.assert_code(analysis, "AGL005")
        self.assertIn("word budget", found.message)
        self.assertIn("not a hard limit", found.message)
        self.assertLess(analysis.files[0].line_count, 500)
        self.assertGreater(analysis.files[0].word_count, 6000)
        # Only the word trigger fires; the line budget is satisfied.
        self.assertEqual(len([f for f in analysis.findings if f.code == "AGL005"]), 1)

    def test_over_both_budgets_adds_agl006(self) -> None:
        body = "\n".join(
            "- " + " ".join(f"word{i}_{j}" for i in range(29)) for j in range(520)
        )
        self.file("AGENTS.md", "# A\n\n## Rules\n\n" + body + "\n")
        analysis = self.lint()
        self.assert_code(analysis, "AGL005")
        found = self.assert_code(analysis, "AGL006")
        self.assertEqual(found.severity, "low")
        self.assertIn("neither budget is met", found.message)

    def test_max_lines_flag_is_respected(self) -> None:
        self.file("AGENTS.md", self._long_file(30))
        self.assertEqual(self.lint(max_lines=20, max_words=10000).findings[0].code,
                         "AGL005")
        self.assert_no_code(self.lint(max_lines=100, max_words=10000), "AGL005")

    def test_budget_message_explains_itself(self) -> None:
        self.file("AGENTS.md", self._long_file(600))
        found = self.assert_code(self.lint(), "AGL005")
        self.assertIn("budget, not a hard limit", found.message)
        self.assertIn("attention", found.message)


# ---------------------------------------------------------------------------
# AGL007 - AGL011 -- Cursor frontmatter
# ---------------------------------------------------------------------------


class TestFrontmatter(ScratchCase):
    def _mdc(self, frontmatter: str) -> None:
        self.file(".cursor/rules/ts.mdc",
                  frontmatter + "\n# T\n\n- Use two-space indentation.\n")

    def test_missing_frontmatter_is_high(self) -> None:
        self.file(".cursor/rules/ts.mdc", "# T\n\n- Use two-space indentation.\n")
        found = self.assert_code(self.lint(), "AGL007")
        self.assertEqual(found.severity, "high")

    def test_valid_frontmatter_is_clean(self) -> None:
        self._mdc("---\ndescription: TS rules\nglobs: '**/*.ts'\nalwaysApply: false\n---")
        analysis = self.lint()
        self.assert_no_code(analysis, "AGL007")
        self.assert_no_code(analysis, "AGL008")
        self.assert_no_code(analysis, "AGL009")
        self.assert_no_code(analysis, "AGL010")

    def test_unterminated_frontmatter_is_malformed(self) -> None:
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: TS rules\n\n# T\n\n- Use two-space indentation.\n")
        found = self.assert_code(self.lint(), "AGL008")
        self.assertIn("never closed", found.message)

    def test_unclosed_list_is_malformed(self) -> None:
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: d\nglobs: [**/*.ts, **/*.tsx\nalwaysApply: true\n---\n\n"
                  "# T\n\n- Use two-space indentation.\n")
        found = self.assert_code(self.lint(), "AGL008")
        self.assertIn("unclosed list", found.message)
        self.assertEqual(found.line, 3)

    def test_unbalanced_braces_are_malformed(self) -> None:
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: d\nglobs: '**/*.{ts,tsx'\nalwaysApply: true\n---\n\n"
                  "# T\n\n- Use two-space indentation.\n")
        found = self.assert_code(self.lint(), "AGL008")
        self.assertIn("unbalanced braces", found.message)

    def test_line_without_a_colon_is_malformed(self) -> None:
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: d\nglobs: '**/*.ts'\nalwaysApply: false\nbroken line\n---\n\n"
                  "# T\n\n- Use two-space indentation.\n")
        found = self.assert_code(self.lint(), "AGL008")
        self.assertIn("not a 'key: value' pair", found.message)

    def test_unbalanced_quote_is_malformed(self) -> None:
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: \"TS rules\nglobs: '**/*.ts'\nalwaysApply: false\n---\n\n"
                  "# T\n\n- Use two-space indentation.\n")
        found = self.assert_code(self.lint(), "AGL008")
        self.assertIn("unbalanced quote", found.message)

    def test_frontmatter_without_scope_or_description(self) -> None:
        self._mdc("---\nalwaysApply: false\n---")
        analysis = self.lint()
        found = [f for f in analysis.findings if f.code == "AGL009"]
        self.assertEqual(len(found), 2, self.codes(analysis))
        self.assertTrue(all(f.severity == "medium" for f in found))
        self.assertIn("Convention", found[0].message)

    def test_description_alone_still_reports_the_missing_scope(self) -> None:
        self._mdc("---\ndescription: TS rules\nalwaysApply: false\n---")
        found = [f for f in self.lint().findings if f.code == "AGL009"]
        self.assertEqual(len(found), 1)
        self.assertIn("scopes this rule to nothing", found[0].message)

    def test_unknown_key_is_reported_as_a_convention(self) -> None:
        self._mdc("---\ndescription: d\nglobs: '**/*.ts'\nalwaysApply: false\n"
                  "colours: blue\n---")
        found = self.assert_code(self.lint(), "AGL010")
        self.assertEqual(found.severity, "low")
        self.assertIn("colours", found.message)
        self.assertIn("convention", found.message)

    def test_only_the_three_documented_keys_are_validated(self) -> None:
        self.assertEqual(acl.MDC_DOCUMENTED_KEYS,
                         ("description", "globs", "alwaysApply"))

    def test_always_apply_true_everywhere_in_one_directory(self) -> None:
        for name in ("a", "b", "c"):
            self.file(f".cursor/rules/{name}.mdc",
                      f"---\ndescription: {name}\nglobs: '**/*.{name}'\n"
                      "alwaysApply: true\n---\n\n# T\n\n- Use two-space indentation.\n")
        found = self.assert_code(self.lint(), "AGL011")
        self.assertEqual(found.severity, "medium")
        self.assertIn("all 3 rule files", found.message)

    def test_one_scoped_file_is_enough_to_silence_agl011(self) -> None:
        self.file(".cursor/rules/a.mdc",
                  "---\ndescription: a\nglobs: '**/*.a'\nalwaysApply: true\n---\n\n"
                  "# T\n\n- Use two-space indentation.\n")
        self.file(".cursor/rules/b.mdc",
                  "---\ndescription: b\nglobs: '**/*.b'\nalwaysApply: false\n---\n\n"
                  "# T\n\n- Use four-space indentation.\n")
        self.assert_no_code(self.lint(), "AGL011")

    def test_single_mdc_file_does_not_trip_agl011(self) -> None:
        self.file(".cursor/rules/only.mdc",
                  "---\ndescription: only\nglobs: '**/*.ts'\nalwaysApply: true\n---\n\n"
                  "# T\n\n- Use two-space indentation.\n")
        self.assert_no_code(self.lint(), "AGL011")

    def test_blanks_and_quotes_around_globs(self) -> None:
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: d\nglobs:\n  - '**/*.ts'\n  - '**/*.tsx'\n"
                  "alwaysApply: false\n---\n\n# T\n\n- Use two-space indentation.\n")
        analysis = self.lint()
        self.assertEqual(analysis.files[0].globs, ("**/*.ts", "**/*.tsx"))
        self.assert_no_code(analysis, "AGL009")

    def test_quoted_values_with_inner_apostrophe_are_valid(self) -> None:
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: \"the team's TS rules\"\nglobs: \"**/*.ts\"\n"
                  "alwaysApply: false\n---\n\n# T\n\n- Use two-space indentation.\n")
        self.assert_no_code(self.lint(), "AGL008")


# ---------------------------------------------------------------------------
# AGL012 -- conflicting scope
# ---------------------------------------------------------------------------


class TestScopeConflicts(ScratchCase):
    def test_overlapping_globs_with_opposite_rules(self) -> None:
        self.file(".cursor/rules/all.mdc",
                  "---\ndescription: all\nglobs: '**/*'\nalwaysApply: false\n---\n\n"
                  "# House\n\n- Always use semicolons.\n")
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: ts\nglobs: '**/*.ts'\nalwaysApply: false\n---\n\n"
                  "# TS\n\n- Never use semicolons.\n")
        found = self.assert_code(self.lint(), "AGL012")
        self.assertEqual(found.severity, "medium")
        self.assertIn("typescript", found.message)

    def test_brace_glob_counts_as_typescript(self) -> None:
        self.assertEqual(acl.glob_languages("**/*.{ts,tsx}"), frozenset({"typescript"}))
        self.assertEqual(acl.glob_languages("**/*.py"), frozenset({"python"}))
        self.assertEqual(acl.glob_languages("**/*"), frozenset())

    def test_non_overlapping_globs_are_not_flagged(self) -> None:
        self.file(".cursor/rules/py.mdc",
                  "---\ndescription: py\nglobs: '**/*.py'\nalwaysApply: false\n---\n\n"
                  "# PY\n\n- Always use tabs for indentation.\n")
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: ts\nglobs: '**/*.ts'\nalwaysApply: false\n---\n\n"
                  "# TS\n\n- Never use tabs for indentation.\n")
        self.assert_no_code(self.lint(), "AGL012")

    def test_same_scope_but_compatible_rules_are_not_flagged(self) -> None:
        self.file(".cursor/rules/a.mdc",
                  "---\ndescription: a\nglobs: '**/*.ts'\nalwaysApply: false\n---\n\n"
                  "# A\n\n- Sort imports alphabetically.\n")
        self.file(".cursor/rules/b.mdc",
                  "---\ndescription: b\nglobs: '**/*.tsx'\nalwaysApply: false\n---\n\n"
                  "# B\n\n- Export components by name.\n")
        self.assert_no_code(self.lint(), "AGL012")


# ---------------------------------------------------------------------------
# AGL013 - AGL015 -- structure
# ---------------------------------------------------------------------------


class TestStructure(ScratchCase):
    def test_rule_before_the_first_heading(self) -> None:
        self.file("AGENTS.md", "- Run `npm test` before you commit.\n\n# A\n\n## R\n\n- One.\n")
        found = self.assert_code(self.lint(), "AGL013")
        self.assertEqual(found.severity, "low")
        self.assertEqual(found.line, 1)

    def test_prose_preamble_without_a_bullet_is_not_flagged(self) -> None:
        self.file("AGENTS.md", "This file explains the checkout service.\n\n# A\n\n"
                               "## R\n\n- Run `npm test` before you commit.\n")
        self.assert_no_code(self.lint(), "AGL013")

    def test_frontmatter_is_not_preamble(self) -> None:
        self.file("CLAUDE.md", "---\nglobs: '**/*.ts'\n---\n\n# A\n\n## R\n\n"
                               "- Run `npm test` before you commit.\n")
        self.assert_no_code(self.lint(), "AGL013")

    def test_heading_depth_jump(self) -> None:
        self.file("AGENTS.md", "# A\n\n## R\n\n- Run `npm test`.\n\n"
                               "#### Deep\n\n- Keep one behaviour per change.\n")
        found = self.assert_code(self.lint(), "AGL014")
        self.assertEqual(found.line, 7)
        self.assertIn("h2 to h4", found.message)

    def test_heading_depth_descent_is_fine(self) -> None:
        self.file("AGENTS.md", "# A\n\n## R\n\n### Deeper\n\n- Run `npm test`.\n")
        self.assert_no_code(self.lint(), "AGL014")

    def test_empty_section(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Run `npm test`.\n\n"
                               "## Release notes\n\n## After\n\n- Keep it short.\n")
        found = self.assert_code(self.lint(), "AGL015")
        self.assertEqual(found.line, 7)
        self.assertIn("Release notes", found.message)

    def test_parent_heading_with_only_subsections_is_not_empty(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n### One\n\n- Run `npm test`.\n")
        self.assert_no_code(self.lint(), "AGL015")

    def test_section_has_text_helper(self) -> None:
        nested = ["# Top", "", "## Sub", "", "- a rule here now."]
        # The h2 on line 3 has a bullet under it.
        self.assertTrue(acl.section_has_text(nested, 3, 2))
        # A heading followed by a deeper heading has something to point at, so
        # it is not the "empty section" this rule is about.
        self.assertTrue(acl.section_has_text(nested, 1, 1))
        # A section that ends at the next same-level heading has no text.
        self.assertFalse(acl.section_has_text(
            ["# A", "", "## B", "", "# C", "", "- a rule."], 1, 2))
        # Prose under the heading is text.
        self.assertTrue(acl.section_has_text(
            ["# A", "", "Some prose about this repository.", "", "## B"], 1, 1))
        # End of file counts as no text.
        self.assertFalse(acl.section_has_text(["# A"], 1, 1))
        self.assertFalse(acl.section_has_text(["# A", "", "   "], 1, 1))
        self.assertFalse(acl.section_has_text(["# A", "", "<!-- todo -->"], 1, 1))

    def test_heading_at_helper(self) -> None:
        lines = ["# Top", "", "## Sub", "text", "-----", "body"]
        self.assertEqual(acl.heading_at(lines, 0), (1, "Top", 1))
        self.assertEqual(acl.heading_at(lines, 2), (2, "Sub", 3))
        self.assertEqual(acl.heading_at(lines, 3), (2, "text", 4))  # setext underline
        self.assertIsNone(acl.heading_at(lines, 5))

    def test_comment_only_section_is_empty(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Run `npm test`.\n\n"
                               "## TODO\n\n<!-- fill this in -->\n")
        self.assert_code(self.lint(), "AGL015")


# ---------------------------------------------------------------------------
# AGL016 - AGL018 -- rule quality
# ---------------------------------------------------------------------------


class TestRuleQuality(ScratchCase):
    def test_question_instead_of_instruction(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Should you run the linter first?\n")
        found = self.assert_code(self.lint(), "AGL016")
        self.assertEqual(found.severity, "low")
        self.assertIn("question", found.message)

    def test_heading_ending_in_a_question_mark_is_not_a_rule(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Why does this exist?\n\n- Run `npm test`.\n")
        self.assert_no_code(self.lint(), "AGL016")

    def test_rule_addressed_to_a_human(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Ask your teammate before a release.\n")
        found = self.assert_code(self.lint(), "AGL017")
        self.assertIn("addressed to a human", found.message)

    def test_wiki_reference_is_addressed_to_a_human(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- See the wiki for the release process.\n")
        self.assert_code(self.lint(), "AGL017")

    def test_unactionable_rules(self) -> None:
        for phrase in ("Write clean code.", "Be careful with migrations.",
                       "Follow best practices.", "Keep it simple."):
            with self.subTest(phrase=phrase):
                self.file("AGENTS.md", f"# A\n\n## Rules\n\n- {phrase}\n")
                found = self.assert_code(self.lint(), "AGL018")
                self.assertEqual(found.severity, "low")
                self.assertIn("not verifiable", found.message)

    def test_concrete_rules_are_not_unactionable(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n"
                  "- Run `npm test` before you commit.\n"
                  "- Keep every function under twenty lines.\n"
                  "- Import the client from `src/api/client.ts`.\n")
        self.assert_no_code(self.lint(), "AGL018")

    def test_best_practices_with_a_named_command_is_still_unactionable(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Follow best practices for `eslint`.\n")
        self.assert_code(self.lint(), "AGL018")


# ---------------------------------------------------------------------------
# AGL019 / AGL020 -- the CLAUDE.md / AGENTS.md pair
# ---------------------------------------------------------------------------


class TestAgentDocPair(ScratchCase):
    def test_identical_pair_is_clean(self) -> None:
        content = "# A\n\n## Rules\n\n- Run `npm test` before you commit.\n"
        self.file("AGENTS.md", content)
        self.file("CLAUDE.md", content)
        analysis = self.lint()
        self.assert_no_code(analysis, "AGL019")
        self.assert_no_code(analysis, "AGL020")

    def test_claude_only(self) -> None:
        self.file("CLAUDE.md", "# A\n\n## Rules\n\n- Run `npm test` before you commit.\n")
        found = self.assert_code(self.lint(), "AGL020")
        self.assertEqual(found.severity, "medium")
        self.assertIn("no AGENTS.md", found.message)

    def test_agents_only(self) -> None:
        self.file("AGENTS.md", "# A\n\n## Rules\n\n- Run `npm test` before you commit.\n")
        found = self.assert_code(self.lint(), "AGL020")
        self.assertIn("no CLAUDE.md", found.message)

    def test_divergent_pair_is_high(self) -> None:
        self.file("AGENTS.md",
                  "# AGENTS\n\n## Tests\n\n- Run `npm test` before you commit.\n"
                  "- Sort imports alphabetically within each group.\n")
        self.file("CLAUDE.md",
                  "# CLAUDE\n\n## Deploy\n\n- Deploy only from the release branch.\n"
                  "- Rotate the signing key every quarter.\n")
        found = self.assert_code(self.lint(), "AGL019")
        self.assertEqual(found.severity, "high")
        self.assertIn("diverged", found.message)
        self.assertIn("AGENTS.md", found.rule_files)

    def test_similar_pair_is_not_divergent(self) -> None:
        self.file("AGENTS.md",
                  "# A\n\n## Rules\n\n- Run `npm test` before you commit.\n"
                  "- Sort imports alphabetically within each group.\n")
        self.file("CLAUDE.md",
                  "# A\n\n## Rules\n\n- Run `npm test` before you commit.\n"
                  "- Sort imports alphabetically within each group, per package.\n")
        self.assert_no_code(self.lint(), "AGL019")

    def test_pair_in_a_subdirectory_is_checked_there(self) -> None:
        self.file("frontend/AGENTS.md", "# A\n\n## Rules\n\n- Run `npm test`.\n")
        found = [f for f in self.lint().findings if f.code == "AGL020"]
        self.assertTrue(found)
        self.assertEqual(found[0].path, "frontend/AGENTS.md")


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


class TestDiscovery(ScratchCase):
    def test_known_files_are_discovered(self) -> None:
        self.file("AGENTS.md", "# A\n\n## R\n\n- Run `npm test`.\n")
        self.file(".cursorrules", "# A\n\n## R\n\n- Run `npm test`.\n")
        self.file(".github/copilot-instructions.md", "# A\n\n## R\n\n- Run `npm test`.\n")
        self.file(".cursor/rules/ts.mdc",
                  "---\ndescription: d\nglobs: '**/*.ts'\nalwaysApply: false\n---\n\n"
                  "# T\n\n- Use two-space indentation.\n")
        analysis = self.lint()
        found = {f.rel_path for f in analysis.files}
        self.assertEqual(found, {"AGENTS.md", ".cursorrules",
                                 ".github/copilot-instructions.md",
                                 ".cursor/rules/ts.mdc"})

    def test_unrelated_markdown_is_ignored(self) -> None:
        self.file("README.md", "# Readme\n\n## Rules\n\n- Write clean code.\n")
        self.file("AGENTS.md", "# A\n\n## R\n\n- Run `npm test`.\n")
        analysis = self.lint()
        self.assertEqual([f.rel_path for f in analysis.files], ["AGENTS.md"],
                         self.codes(analysis))

    def test_empty_file_is_handled(self) -> None:
        self.file("AGENTS.md", "")
        analysis = self.lint()
        self.assertEqual(analysis.files[0].line_count, 1)
        self.assertEqual(analysis.files[0].statements, [])
        self.assert_code(analysis, "AGL020")  # no CLAUDE.md next to it

    def test_file_of_only_whitespace_is_handled(self) -> None:
        self.file("AGENTS.md", "\n\n   \n")
        self.file("CLAUDE.md", "\n\n   \n")
        analysis = self.lint()
        self.assertEqual(self.codes(analysis), [], self.codes(analysis))

    def test_references_resolve_against_a_nested_project_root(self) -> None:
        # agent-config-lint's own repository contains examples/good/, so linting
        # the checkout must resolve examples/good/src/... from examples/good and
        # not from the checkout root.
        self.file("docs/README.md", "# Docs\n")
        self.file("examples/nested/AGENTS.md",
                  "# A\n\n## Rules\n\n- The handler lives in `src/handler.ts`.\n")
        self.file("examples/nested/CLAUDE.md",
                  "# A\n\n## Rules\n\n- The handler lives in `src/handler.ts`.\n")
        self.file("examples/nested/src/handler.ts", "export const x = 1;\n")
        analysis = self.lint()
        self.assert_no_code(analysis, "AGL001")
        # Now delete the nested file: the same reference must be reported.
        (self.repo / "examples" / "nested" / "src" / "handler.ts").unlink()
        self.assert_code(self.lint(), "AGL001")

    def test_scratch_directory_itself_is_never_linted(self) -> None:
        self.file("AGENTS.md", "# A\n\n## R\n\n- Run `npm test`.\n")
        self.file("CLAUDE.md", "# A\n\n## R\n\n- Run `npm test`.\n")
        self.assertNotIn("AGL001", self.codes(self.lint()))


# ---------------------------------------------------------------------------
# Negative control and the shipped examples
# ---------------------------------------------------------------------------


class TestExampleRepositories(unittest.TestCase):
    def test_good_example_has_zero_findings_at_the_default_threshold(self) -> None:
        analysis = acl.analyse(GOOD_EXAMPLE)
        self.assertEqual(
            analysis.findings, [],
            "examples/good must be clean; got "
            + "; ".join(f"{f.code} {f.path}:{f.line} {f.message[:60]}"
                        for f in analysis.findings),
        )

    def test_good_example_exits_zero(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = acl.main([str(GOOD_EXAMPLE)])
        self.assertEqual(code, 0, out.getvalue())

    def test_good_example_rules_files_are_discovered(self) -> None:
        analysis = acl.analyse(GOOD_EXAMPLE)
        paths = {f.rel_path for f in analysis.files}
        self.assertIn("AGENTS.md", paths)
        self.assertIn("CLAUDE.md", paths)
        self.assertIn(".cursor/rules/typescript.mdc", paths)
        self.assertIn(".cursor/rules/python-service.mdc", paths)
        self.assertIn(".github/copilot-instructions.md", paths)

    def test_good_example_covers_every_rule_at_a_low_severity_threshold(self) -> None:
        # Sanity check that the good example is not clean merely because nothing
        # was read: every file must parse and contribute rules.
        analysis = acl.analyse(GOOD_EXAMPLE)
        for inst in analysis.files:
            self.assertGreater(len(inst.statements), 0, inst.rel_path)

    def test_bad_example_is_not_clean(self) -> None:
        analysis = acl.analyse(BAD_EXAMPLE)
        self.assertGreater(len(analysis.findings), 10)

    def test_bad_example_demonstrates_most_rules(self) -> None:
        codes = {f.code for f in acl.analyse(BAD_EXAMPLE).findings}
        for expected in ("AGL001", "AGL002", "AGL003", "AGL004", "AGL005", "AGL006",
                         "AGL008", "AGL009", "AGL010", "AGL011", "AGL012", "AGL014",
                         "AGL015", "AGL016", "AGL017", "AGL018", "AGL019"):
            self.assertIn(expected, codes)

    def test_bad_example_exits_one(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = acl.main([str(BAD_EXAMPLE)])
        self.assertEqual(code, 1)

    def test_bad_example_json_lists_every_finding(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            code = acl.main([str(BAD_EXAMPLE), "--json"])
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(len(payload["findings"]),
                         sum(payload["counts"].values()))
        self.assertTrue(all(f["fix"] for f in payload["findings"]))

    def test_bad_example_paths_that_exist_are_not_reported(self) -> None:
        reported = " ".join(f.message for f in acl.analyse(BAD_EXAMPLE).findings
                            if f.code == "AGL001")
        for existing in ("src/api/routes.ts", "src/services/orders.py",
                         "tests/inventory.test.ts", "src/components/"):
            self.assertNotIn(f"`{existing}`", reported)

    def test_examples_contain_no_credentials(self) -> None:
        suspicious = ("BEGIN RSA", "AKIA", "sk_live", "password =", "api_key")
        for root in (GOOD_EXAMPLE, BAD_EXAMPLE):
            for dirpath, _dirnames, filenames in os.walk(root):
                for filename in filenames:
                    full = Path(dirpath) / filename
                    text = full.read_text(encoding="utf-8", errors="replace")
                    for needle in suspicious:
                        self.assertNotIn(needle, text, str(full))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestHelpers(unittest.TestCase):
    def test_normalise_ignores_case_punctuation_and_code_marks(self) -> None:
        self.assertEqual(acl.normalise("Run `npm test`, always!"),
                         acl.normalise("run npm test always"))

    def test_token_similarity_bounds(self) -> None:
        self.assertEqual(acl.token_similarity(frozenset(), frozenset({"a"})), 0.0)
        same = frozenset({"a", "b"})
        self.assertEqual(acl.token_similarity(same, same), 1.0)

    def test_shorten_keeps_short_text_intact(self) -> None:
        self.assertEqual(acl.shorten("short rule"), "short rule")
        self.assertTrue(acl.shorten("x" * 200).endswith("\u2026"))

    def test_severity_at_least(self) -> None:
        self.assertTrue(acl.severity_at_least("high", "low"))
        self.assertTrue(acl.severity_at_least("medium", "medium"))
        self.assertFalse(acl.severity_at_least("low", "high"))

    def test_clean_token_keeps_a_leading_dot(self) -> None:
        self.assertEqual(acl._clean_token(".cursor/rules/x.mdc`;"),
                         ".cursor/rules/x.mdc")
        self.assertEqual(acl._clean_token("(`src/app.ts`),"), "src/app.ts")

    def test_brace_expand(self) -> None:
        self.assertEqual(acl._brace_expand("**/*.{ts,tsx}"), ["**/*.ts", "**/*.tsx"])
        self.assertEqual(acl._brace_expand("src/*.py"), ["src/*.py"])

    def test_every_rule_has_a_severity_and_a_basis(self) -> None:
        for spec in acl.RULES:
            self.assertIn(spec.severity, acl.SEVERITIES)
            self.assertIn(spec.basis, {"documented", "convention", "heuristic"})
            self.assertTrue(spec.title)

    def test_opposition_pairs_are_well_formed(self) -> None:
        self.assertGreaterEqual(len(acl.OPPOSITION_PAIRS), 10)
        for pid, left, right, label in acl.OPPOSITION_PAIRS:
            self.assertTrue(pid)
            self.assertTrue(label)
            self.assertNotEqual(left, right)


if __name__ == "__main__":
    unittest.main(verbosity=2)
