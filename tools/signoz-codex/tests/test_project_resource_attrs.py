from __future__ import annotations

import importlib.util
import subprocess
import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "project_resource_attrs.py"
SPEC = importlib.util.spec_from_file_location("project_resource_attrs", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class ProjectResourceAttrsTests(unittest.TestCase):
    def test_parse_and_serialize_round_trip_with_escaping(self) -> None:
        raw = r"env=dev,project.name=old\,name,project.path=/tmp/with\=equals,other=two\\three"
        parsed = MODULE.parse_resource_attributes(raw)
        self.assertEqual(parsed["env"], "dev")
        self.assertEqual(parsed["project.name"], "old,name")
        self.assertEqual(parsed["project.path"], "/tmp/with=equals")
        self.assertEqual(parsed["other"], r"two\three")
        self.assertEqual(MODULE.parse_resource_attributes(MODULE.serialize_resource_attributes(parsed)), parsed)

    def test_merge_resource_attributes_replaces_managed_keys_only(self) -> None:
        merged = MODULE.merge_resource_attributes(
            "env=dev,project.name=old,project.path=/tmp/old,vcs.repository.name=oldrepo",
            OrderedDict(
                (
                    ("project.name", "new"),
                    ("project.path", "/tmp/new"),
                )
            ),
        )
        self.assertEqual(merged, "env=dev,project.name=new,project.path=/tmp/new")

    def test_build_managed_attributes_prefers_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            nested = repo_root / "nested"
            nested.mkdir(parents=True)
            subprocess.run(["git", "init", str(repo_root)], check=True, capture_output=True, text=True)
            managed = MODULE.build_managed_attributes(nested, Path(temp_dir) / "missing.toml")
            self.assertEqual(
                managed,
                OrderedDict(
                    (
                        ("project.name", "repo"),
                        ("project.path", str(repo_root.resolve())),
                        ("vcs.repository.name", "repo"),
                    )
                ),
            )

    def test_build_managed_attributes_falls_back_to_nearest_codex_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            workspace = root / "workspace"
            project = workspace / "project"
            nested = project / "nested" / "child"
            nested.mkdir(parents=True)

            config_path = root / "config.toml"
            config_path.write_text(
                (
                    f'[projects."{workspace}"]\ntrust_level = "trusted"\n\n'
                    f'[projects."{project}"]\ntrust_level = "trusted"\n'
                ),
                encoding="utf-8",
            )

            managed = MODULE.build_managed_attributes(nested, config_path)
            self.assertEqual(
                managed,
                OrderedDict(
                    (
                        ("project.name", "project"),
                        ("project.path", str(project)),
                    )
                ),
            )

    def test_merge_resource_attributes_removes_stale_managed_keys_when_no_project(self) -> None:
        merged = MODULE.merge_resource_attributes(
            "env=dev,project.name=old,project.path=/tmp/old,vcs.repository.name=oldrepo",
            OrderedDict(),
        )
        self.assertEqual(merged, "env=dev")


if __name__ == "__main__":
    unittest.main()
