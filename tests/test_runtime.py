"""Bootstrap failure and path-alias regression checks; no network used here."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"backend"))
import runtime


class RuntimeTest(unittest.TestCase):
    def test_existing_environment_resolves_path_alias_before_restarting(self):
        with tempfile.TemporaryDirectory() as directory:
            actual = Path(directory)/"actual"
            actual.mkdir()
            alias = Path(directory)/"alias"
            alias.symlink_to(actual,target_is_directory=True)
            with patch.object(runtime,"location",return_value=alias), patch.object(sys,"prefix",str(actual)), patch.object(runtime,"run_command") as command:
                runtime.ensure_runtime(lambda *_: self.fail("Ready environment should not install again"))
                command.assert_not_called()

    def test_failed_install_never_executes_incomplete_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/"managed"
            states = []
            with patch.object(runtime,"location",return_value=target), patch.object(runtime,"run_command",side_effect=RuntimeError("offline")), patch.object(os,"execve") as execute:
                with self.assertRaises(RuntimeError):
                    runtime.ensure_runtime(lambda *args: states.append(args))
                execute.assert_not_called()
                self.assertEqual(states[0][0],"INSTALLING")


if __name__ == "__main__":
    unittest.main()
