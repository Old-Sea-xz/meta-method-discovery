"""Validate skill packaging and test assets; does not evaluate agent behavior."""
import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def read_frontmatter(text, folder_name):
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    if not match:
        raise ValueError("Missing YAML frontmatter")
    data = yaml.safe_load(match[1])
    if not isinstance(data, dict):
        raise ValueError("Frontmatter must be a mapping")
    allowed = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    if set(data) - allowed:
        raise ValueError("Unknown frontmatter fields")
    name = data.get("name")
    if (not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
            or len(name) > 64 or name != folder_name):
        raise ValueError("Invalid name or directory mismatch")
    description = data.get("description")
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
        raise ValueError("Invalid description")
    return data


def load_cases(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids, prompts = set(), set()
    for row in rows:
        for field in ("id", "prompt"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError(f"Missing {field}")
        if row["id"] in ids or row["prompt"] in prompts:
            raise ValueError("Duplicate ID or prompt")
        ids.add(row["id"])
        prompts.add(row["prompt"])
    return rows


class PackageTests(unittest.TestCase):
    def test_actual_frontmatter(self):
        read_frontmatter((ROOT / "SKILL.md").read_text(encoding="utf-8"), ROOT.name)

    def test_invalid_frontmatter(self):
        examples = [
            "name: ''\ndescription: ok", "name: Bad\ndescription: ok",
            "name: a--b\ndescription: ok", "name: other\ndescription: ok",
            "name: meta-method-discovery\ndescription: ''",
            "name: meta-method-discovery\ndescription: [not, text]",
            "name: meta-method-discovery\ndescription: ok\nunknown: value",
        ]
        for example in examples:
            with self.subTest(example=example), self.assertRaises(ValueError):
                read_frontmatter(f"---\n{example}\n---\nBody\n", ROOT.name)

    def test_resource_links_resolve_inside_package(self):
        for path in [ROOT / "SKILL.md", *(ROOT / "references").glob("*.md")]:
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                resolved = (ROOT / target.split("#")[0]).resolve()
                self.assertTrue(resolved.is_relative_to(ROOT.resolve()), target)
                self.assertTrue(resolved.is_file(), target)

    def test_trigger_coverage(self):
        rows = load_cases(ROOT / "tests/trigger_cases.jsonl")
        self.assertTrue(all(type(r.get("expected_activate")) is bool for r in rows))
        self.assertGreaterEqual(sum(r["expected_activate"] for r in rows), 10)
        self.assertGreaterEqual(sum(not r["expected_activate"] for r in rows), 10)
        self.assertTrue(all(r.get("rationale") for r in rows))

    def test_discovery_coverage(self):
        rows = load_cases(ROOT / "tests/discovery_cases.jsonl")
        self.assertGreaterEqual(len({r["domain"] for r in rows}), 6)
        for row in rows:
            for field in ("acceptance", "critical_errors"):
                self.assertIsInstance(row.get(field), list)
                self.assertTrue(row[field])
                self.assertTrue(all(isinstance(x, str) and x.strip() for x in row[field]))

    def test_runtime_boundary(self):
        # Catch accidental links to evaluation assets, not semantic leakage.
        for path in [ROOT / "SKILL.md", *(ROOT / "references").glob("*.md")]:
            targets = re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
            self.assertFalse(any("tests/" in t or "evaluation/" in t or "labels_private" in t for t in targets))
        self.assertFalse(list(ROOT.rglob("labels_private*")))
        self.assertFalse(list(ROOT.rglob("MetaMethodBench*.zip")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
