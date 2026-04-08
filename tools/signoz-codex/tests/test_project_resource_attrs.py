from __future__ import annotations

import tempfile
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest import mock

from test_support import load_script_module

MODULE = load_script_module("project_resource_attrs", "project_resource_attrs.py")


class ProjectResourceAttrsTests(unittest.TestCase):
    def test_parse_and_serialize_round_trip_with_escaping(self) -> None:
        sample_path = Path("sample") / "with=equals"
        raw = rf"env=dev,project.name=old\,name,project.path={sample_path},other=two\\three"
        parsed = MODULE.parse_resource_attributes(raw)
        self.assertEqual(parsed["env"], "dev")
        self.assertEqual(parsed["project.name"], "old,name")
        self.assertEqual(parsed["project.path"], str(sample_path))
        self.assertEqual(parsed["other"], r"two\three")
        self.assertEqual(MODULE.parse_resource_attributes(MODULE.serialize_resource_attributes(parsed)), parsed)

    def test_merge_resource_attributes_replaces_managed_keys_only(self) -> None:
        merged = MODULE.merge_resource_attributes(
            "env=dev,project.name=old,project.path=old-path,vcs.repository.name=oldrepo",
            OrderedDict(
                (
                    ("project.name", "new"),
                    ("project.path", "new-path"),
                )
            ),
        )
        self.assertEqual(merged, "env=dev,project.name=new,project.path=new-path")

    def test_build_managed_attributes_prefers_git_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            nested = repo_root / "nested"
            nested.mkdir(parents=True)
            with mock.patch.object(MODULE, "git_repo_root", return_value=repo_root.resolve()):
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

    def test_git_repo_root_returns_none_when_git_discovery_times_out(self) -> None:
        with mock.patch.object(
            MODULE.subprocess,
            "run",
            side_effect=MODULE.subprocess.TimeoutExpired(cmd=["git"], timeout=MODULE.GIT_DISCOVERY_TIMEOUT_SECONDS),
        ):
            self.assertIsNone(MODULE.git_repo_root(Path.cwd()))

    def test_merge_resource_attributes_removes_stale_managed_keys_when_no_project(self) -> None:
        merged = MODULE.merge_resource_attributes(
            "env=dev,project.name=old,project.path=old-path,vcs.repository.name=oldrepo",
            OrderedDict(),
        )
        self.assertEqual(merged, "env=dev")


if __name__ == "__main__":
    unittest.main()
