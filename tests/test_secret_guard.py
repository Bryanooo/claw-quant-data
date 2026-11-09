"""Exercise real Git hooks in disposable repositories, with synthetic credentials."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("gitleaks"), "Gitleaks is required for hook integration tests")
class SecretGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Secret scan fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        for relative in (".gitleaks.toml", ".githooks/pre-commit", ".githooks/pre-push",
                         "scripts/check_secrets.py", "scripts/install_git_hooks.py"):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SOURCE / relative, target)
        self.git("add", ".")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-m", "clean fixture")
        subprocess.run([sys.executable, "scripts/install_git_hooks.py"],
                       cwd=self.repo, check=True, capture_output=True)
        self.synthetic = hashlib.sha224(b"synthetic credential for isolated hook tests").hexdigest()

    def git(self, *args, check=True):
        result = subprocess.run(["git", *args], cwd=self.repo, text=True, capture_output=True)
        if check:
            self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def test_staged_secret_is_blocked_after_worktree_is_cleaned(self):
        path = self.repo / "sample.py"
        path.write_text('TOKEN = "' + self.synthetic + '"\n')
        self.git("add", "sample.py")
        path.write_text("TOKEN = None\n")
        before = self.git("rev-parse", "HEAD").stdout
        result = self.git("commit", "-m", "must be blocked", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, before)
        self.assertNotIn(self.synthetic, result.stdout + result.stderr)

    def test_unstaged_secret_does_not_replace_the_index_scan(self):
        path = self.repo / "sample.py"
        path.write_text("TOKEN = None\n")
        self.git("add", "sample.py")
        path.write_text('TOKEN = "' + self.synthetic + '"\n')
        self.git("commit", "-m", "clean staged snapshot")
        self.assertNotIn(self.synthetic, self.git("show", "HEAD:sample.py").stdout)

    def test_inline_allow_comment_cannot_disable_the_check(self):
        path = self.repo / "sample.py"
        path.write_text('TOKEN = "' + self.synthetic + '"  # gitleaks:allow\n')
        self.git("add", "sample.py")
        result = self.git("commit", "-m", "must be blocked", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(self.synthetic, result.stdout + result.stderr)

    def test_pre_push_blocks_an_unreferenced_tainted_commit(self):
        remote = self.root / "remote.git"
        subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
        self.git("remote", "add", "origin", str(remote))
        path = self.repo / "sample.py"
        path.write_text('TOKEN = "' + self.synthetic + '"\n')
        self.git("add", "sample.py")
        self.git("-c", "core.hooksPath=/dev/null", "commit", "-m", "isolated tainted fixture")
        bad = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("reset", "--hard", "HEAD^")
        result = self.git("push", "origin", bad + ":refs/heads/leak-test", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(self.synthetic, result.stdout + result.stderr)
        exists = subprocess.run(["git", "--git-dir", str(remote), "rev-parse",
                                 "--verify", "refs/heads/leak-test"], capture_output=True)
        self.assertNotEqual(exists.returncode, 0)

    def test_missing_scanner_fails_closed(self):
        result = subprocess.run(
            [sys.executable, "scripts/check_secrets.py", "--staged"], cwd=self.repo,
            env={**os.environ, "PATH": ""}, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("requires Gitleaks", result.stderr)

    def test_branch_deletion_skips_nonexistent_target(self):
        zeros = "0" * 40
        line = "delete " + zeros + " refs/heads/old " + zeros + "\n"
        result = subprocess.run(
            [sys.executable, "scripts/check_secrets.py", "--pre-push"],
            cwd=self.repo, input=line, text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
