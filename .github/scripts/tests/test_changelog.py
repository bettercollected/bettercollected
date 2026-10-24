"""Tests for .github/scripts/changelog.py (standard library only).

Run: python3 -m unittest discover -s .github/scripts/tests
 or: uv run --no-project --with pytest pytest .github/scripts/tests
"""

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "changelog", Path(__file__).resolve().parents[1] / "changelog.py"
)
changelog = importlib.util.module_from_spec(_SPEC)
sys.modules["changelog"] = changelog  # dataclasses look the module up
_SPEC.loader.exec_module(changelog)

CHANGELOG = """\
# Changelog

Intro text.

## [Unreleased]

### Fixed

- An existing fix that is already
  wrapped over two lines.

### Added

- An existing feature.

## [1.2.0] - 2026-01-02

### Added

- Old feature.

[1.2.0]: https://github.com/example/repo/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/example/repo/releases/tag/v1.1.0
"""


class Repo(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "changelog.d").mkdir()
        (self.root / "changelog.d" / "README.md").write_text("# Fragments\n")
        (self.root / "CHANGELOG.md").write_text(CHANGELOG)

    def tearDown(self):
        self._tmp.cleanup()

    def fragment(self, name, text):
        (self.root / "changelog.d" / name).write_text(text)

    def changelog_text(self):
        return (self.root / "CHANGELOG.md").read_text()

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = changelog.main(["--root", str(self.root), *argv])
        return code, out.getvalue(), err.getvalue()


class AssembleTest(Repo):
    def test_assemble_keeps_existing_entries_orders_categories_and_sorts_fragments(self):
        self.fragment("fix-z-branch.fixed.md", "- Fix from a branch slug.\n")
        self.fragment("120.fixed.md", "- Fix from PR 120.\n")
        self.fragment("99.fixed.md", "- Fix from PR 99.\n")
        self.fragment("a-branch.fixed.md", "- Fix from another branch.\n")
        self.fragment("100.security.md", "- A security fix.\n")
        self.fragment("100.changed.md", "- A change.\n")
        code, out, err = self.run_main("assemble", "1.3.0", "--date", "2026-02-03")
        self.assertEqual(code, 0, err)
        expected_section = """\
## [Unreleased]

## [1.3.0] - 2026-02-03

### Added

- An existing feature.

### Changed

- A change.

### Fixed

- An existing fix that is already
  wrapped over two lines.
- Fix from PR 99.
- Fix from PR 120.
- Fix from another branch.
- Fix from a branch slug.

### Security

- A security fix.

## [1.2.0] - 2026-01-02
"""
        self.assertIn(expected_section, self.changelog_text())
        self.assertTrue(self.changelog_text().startswith("# Changelog\n\nIntro text.\n\n"))
        remaining = sorted(p.name for p in (self.root / "changelog.d").iterdir())
        self.assertEqual(remaining, ["README.md"])

    def test_wrapping_and_nested_bullets_preserved(self):
        text = "- First line of a long entry\n  that wraps here.\n  - A nested point\n    wrapped too.\n- A second bullet.\n"
        self.fragment("my-branch.added.md", text)
        code, _, err = self.run_main("assemble", "1.3.0", "--date", "2026-02-03")
        self.assertEqual(code, 0, err)
        self.assertIn("- An existing feature.\n" + text + "\n### Fixed", self.changelog_text())

    def test_compare_link_added(self):
        self.fragment("1.added.md", "- X.\n")
        self.run_main("assemble", "1.3.0", "--date", "2026-02-03")
        self.assertIn(
            "[1.3.0]: https://github.com/example/repo/compare/v1.2.0...v1.3.0\n"
            "[1.2.0]: https://github.com/example/repo/compare/v1.1.0...v1.2.0\n",
            self.changelog_text(),
        )

    def test_previous_override(self):
        self.run_main("assemble", "1.3.0", "--date", "2026-02-03", "--previous", "1.2.5")
        self.assertIn("compare/v1.2.5...v1.3.0", self.changelog_text())

    def test_unreleased_only_entries_are_released(self):
        code, _, err = self.run_main("assemble", "1.3.0", "--date", "2026-02-03")
        self.assertEqual(code, 0, err)
        self.assertIn("## [Unreleased]\n\n## [1.3.0] - 2026-02-03\n\n### Added\n", self.changelog_text())

    def test_nothing_to_release(self):
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## [Unreleased]\n\n## [1.2.0] - 2026-01-02\n\n- x\n"
        )
        code, _, err = self.run_main("assemble", "1.3.0")
        self.assertEqual(code, 1)
        self.assertIn("nothing to release", err)

    def test_existing_version_rejected(self):
        code, _, err = self.run_main("assemble", "1.2.0")
        self.assertEqual(code, 1)
        self.assertIn("already has", err)

    def test_bad_version_and_date_rejected(self):
        self.assertEqual(self.run_main("assemble", "v1.3")[0], 1)
        self.assertEqual(self.run_main("assemble", "1.3.0", "--date", "03/02/2026")[0], 1)
        self.assertEqual(self.changelog_text(), CHANGELOG)

    def test_draft_changes_nothing(self):
        self.fragment("7.removed.md", "- Gone.\n")
        code, out, err = self.run_main("assemble", "--draft")
        self.assertEqual(code, 0, err)
        self.assertTrue(out.startswith("## [Unreleased]\n\n### Added\n\n- An existing feature.\n"))
        self.assertIn("### Removed\n\n- Gone.\n\n### Fixed", out)
        self.assertEqual(self.changelog_text(), CHANGELOG)
        self.assertTrue((self.root / "changelog.d" / "7.removed.md").exists())


class FragmentValidationTest(Repo):
    def assert_rejected(self, name, text, message):
        self.fragment(name, text)
        code, _, err = self.run_main("assemble", "1.3.0")
        self.assertEqual(code, 1)
        self.assertIn(message, err)
        self.assertEqual(self.changelog_text(), CHANGELOG)
        self.assertTrue((self.root / "changelog.d" / name).exists())

    def test_empty_fragment_rejected(self):
        self.assert_rejected("1.added.md", "  \n\n", "empty")

    def test_unknown_category_rejected(self):
        self.assert_rejected("1.improved.md", "- X.\n", "unknown category 'improved'")

    def test_bad_name_rejected(self):
        self.assert_rejected("notes.txt", "- X.\n", "name it")

    def test_not_a_bullet_rejected(self):
        self.assert_rejected("1.added.md", "Just text.\n", "bullet")

    def test_heading_rejected(self):
        self.assert_rejected("1.added.md", "### Added\n- X.\n", "bullet")
        self.fragment("1.added.md", "- X.\n# heading\n")
        self.assertEqual(self.run_main("assemble", "1.3.0")[0], 1)

    def test_blank_line_inside_rejected(self):
        self.assert_rejected("1.added.md", "- X.\n\n- Y.\n", "blank line")

    def test_unindented_continuation_rejected(self):
        self.assert_rejected("1.added.md", "- X\nnot indented.\n", "continues one")

    def test_trailing_whitespace_and_crlf_normalised(self):
        self.fragment("1.added.md", "\n- X  \r\n  wrapped.\r\n\n")
        self.assertEqual(self.run_main("assemble", "1.3.0", "--date", "2026-02-03")[0], 0)
        self.assertIn("- An existing feature.\n- X\n  wrapped.\n\n", self.changelog_text())

    def test_dotted_slug_allowed(self):
        self.fragment("deps.4.0.added.md", "- X.\n")
        self.assertEqual(self.run_main("assemble", "--draft")[0], 0)


class CheckTest(Repo):
    def check(self, changed, head="feat/x", labels=(), author="someone"):
        out = io.StringIO()
        with redirect_stdout(out):
            return changelog.check(self.root, changed, head, set(labels), author)

    def test_code_without_fragment_fails(self):
        problems = self.check(["backend/backend/app/main.py"])
        self.assertEqual(len(problems), 1)
        self.assertIn("No changelog fragment", problems[0])

    def test_code_with_fragment_passes(self):
        self.fragment("feat-x.added.md", "- X.\n")
        self.assertEqual(self.check(["backend/backend/app/main.py", "changelog.d/feat-x.added.md"]), [])

    def test_label_and_bot_waive_fragment(self):
        self.assertEqual(self.check(["webapp/package.json"], labels=["no-changelog"]), [])
        self.assertEqual(self.check(["webapp/yarn.lock"], author="dependabot[bot]"), [])

    def test_docs_and_tests_need_no_fragment(self):
        changed = [
            "docs/ci.md",
            "README.md",
            "backend/tests/app/test_x.py",
            "webapp/src/components/x.test.tsx",
            "webapp/src/__tests__/y.ts",
            "auth/tests/conftest.py",
            ".github/ISSUE_TEMPLATE/bug_report.yml",
        ]
        self.assertEqual(self.check(changed), [])

    def test_ci_config_needs_fragment(self):
        self.assertTrue(self.check([".github/workflows/ci.yml"]))
        self.assertTrue(changelog.needs_entry("webapp/jest.config.js"))
        self.assertTrue(changelog.needs_entry("backend/backend/admin/tasks/impl/selftest_slow.py"))

    def test_direct_changelog_edit_fails_even_with_label(self):
        problems = self.check(["CHANGELOG.md"], labels=["no-changelog"])
        self.assertEqual(len(problems), 1)
        self.assertIn("edited directly", problems[0])

    def test_release_assembly_branch_may_edit_changelog(self):
        self.assertEqual(self.check(["CHANGELOG.md", "changelog.d/12.added.md"], head="docs/changelog-1.3.0"), [])

    def test_branch_sync_skipped(self):
        self.assertEqual(self.check(["CHANGELOG.md", "backend/x.py"], head="release/4.0"), [])

    def test_merge_forward_is_a_branch_sync(self):
        changed = ["CHANGELOG.md", "backend/x.py"]
        self.assertEqual(self.check(changed, head="merge/release-4.0-into-develop"), [])
        # only a merge of a release branch: other merge/ heads are checked as usual
        self.assertTrue(self.check(changed, head="merge/feature-into-develop"))

    def test_invalid_fragment_fails_check(self):
        self.fragment("feat-x.improved.md", "- X.\n")
        problems = self.check(["backend/x.py", "changelog.d/feat-x.improved.md"])
        self.assertTrue(any("unknown category" in p for p in problems))

    def test_deleted_fragment_does_not_count(self):
        self.assertTrue(self.check(["backend/x.py", "changelog.d/gone.added.md"]))

    def test_parse_labels(self):
        self.assertEqual(changelog.parse_labels('["a", "no-changelog"]'), {"a", "no-changelog"})
        self.assertEqual(changelog.parse_labels("a, b"), {"a", "b"})
        self.assertEqual(changelog.parse_labels(""), set())


if __name__ == "__main__":
    unittest.main()
