import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("sync_readme_structure.py")
SPEC = importlib.util.spec_from_file_location("sync_readme_structure", SCRIPT_PATH)
sync_readme_structure = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sync_readme_structure)


class SyncReadmeStructureTests(unittest.TestCase):
    def test_pre_commit_ignores_untracked_local_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            self._init_repo(repo)
            (repo / "tracked").mkdir()
            (repo / "tracked" / "file.txt").write_text("tracked\n")
            (repo / "local-backup").mkdir()
            (repo / "local-backup" / "scratch.txt").write_text("local\n")

            readme = repo / "README.md"
            original = (
                "# Fixture\n\n"
                "```\n"
                "fixture/\n"
                "└── tracked/    # tracked directory\n"
                "```\n"
            )
            readme.write_text(original)
            subprocess.run(
                ["git", "-C", str(repo), "add", "README.md", "tracked/file.txt"],
                check=True,
            )

            indexed_paths = sync_readme_structure._git_index_paths(repo)

            result = sync_readme_structure.check_directory(
                repo, fix=True, repo_root=repo, indexed_paths=indexed_paths
            )

            self.assertEqual(result, 0)
            self.assertEqual(readme.read_text(), original)

    def test_pre_commit_includes_staged_new_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            self._init_repo(repo)
            (repo / "tracked").mkdir()
            (repo / "tracked" / "file.txt").write_text("tracked\n")
            (repo / "staged").mkdir()
            (repo / "staged" / "file.txt").write_text("staged\n")

            readme = repo / "README.md"
            readme.write_text(
                "# Fixture\n\n"
                "```\n"
                "fixture/\n"
                "└── tracked/    # tracked directory\n"
                "```\n"
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo),
                    "add",
                    "README.md",
                    "tracked/file.txt",
                    "staged/file.txt",
                ],
                check=True,
            )

            indexed_paths = sync_readme_structure._git_index_paths(repo)

            result = sync_readme_structure.check_directory(
                repo, fix=True, repo_root=repo, indexed_paths=indexed_paths
            )

            self.assertEqual(result, 0)
            self.assertIn("staged/", readme.read_text())

    def _init_repo(self, repo: Path) -> None:
        subprocess.run(["git", "-C", str(repo), "init"], check=True)


if __name__ == "__main__":
    unittest.main()
