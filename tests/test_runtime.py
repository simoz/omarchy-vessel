"""Bootstrap failure and path-alias regression checks; no network used here."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import runtime


class RuntimeTest(unittest.TestCase):
    def test_existing_environment_resolves_path_alias_before_restarting(self):
        with tempfile.TemporaryDirectory() as directory:
            actual = Path(directory) / "actual"
            actual.mkdir()
            alias = Path(directory) / "alias"
            alias.symlink_to(actual, target_is_directory=True)
            with (
                patch.object(runtime, "location", return_value=alias),
                patch.object(sys, "prefix", str(actual)),
                patch.object(runtime, "run_command") as command,
            ):
                runtime.ensure_runtime(
                    lambda *_: self.fail("Ready environment should not install again")
                )
                command.assert_not_called()

    def test_failed_install_never_executes_incomplete_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "managed"
            states = []
            with (
                patch.object(runtime, "location", return_value=target),
                patch.object(
                    runtime, "run_command", side_effect=RuntimeError("offline")
                ),
                patch.object(os, "execve") as execute,
            ):
                with self.assertRaises(RuntimeError):
                    runtime.ensure_runtime(lambda *args: states.append(args))
                execute.assert_not_called()
                self.assertEqual(states[0][0], "INSTALLING")


class InstallerBoundaryTest(unittest.TestCase):
    def test_timeout_cleanup_tolerates_already_exited_child_and_removes_key(self):
        import subprocess
        from unittest.mock import Mock

        child = Mock()
        child.wait.side_effect = [subprocess.TimeoutExpired(["installer"], 1), 0]
        child.poll.return_value = None
        with (
            patch.dict(
                os.environ,
                {"AISSTREAM_API_KEY": "private-key", "PYTHONPATH": "/untrusted"},
            ),
            patch.object(runtime.subprocess, "Popen", return_value=child) as launch,
            patch.object(runtime.os, "killpg", side_effect=ProcessLookupError),
        ):
            with self.assertRaises(subprocess.TimeoutExpired):
                runtime.run_command(["installer"], 1)
        self.assertNotIn("AISSTREAM_API_KEY", launch.call_args.kwargs["env"])
        self.assertNotIn("PYTHONPATH", launch.call_args.kwargs["env"])
        self.assertTrue(launch.call_args.kwargs["start_new_session"])
        self.assertEqual(child.wait.call_count, 2)


if __name__ == "__main__":
    unittest.main()
