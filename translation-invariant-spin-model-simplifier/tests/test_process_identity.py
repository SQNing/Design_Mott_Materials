"""Phase A: process identity must work on macOS (ps) and Linux (/proc)."""
import socket
import unittest
from unittest import mock

from research import state


class PsIdentityTests(unittest.TestCase):
    def _completed(self, stdout, returncode=0):
        return mock.Mock(returncode=returncode, stdout=stdout)

    def test_parses_ps_output(self):
        stdout = "  4242 Ss   Wed Nov 18 19:00:01 2026\n"
        with mock.patch("research.state.subprocess.run",
                        return_value=self._completed(stdout)) as run:
            identity = state._ps_identity(4242)
        run.assert_called_once()
        self.assertEqual(identity["pid"], 4242)
        self.assertEqual(identity["host"], socket.gethostname())
        self.assertEqual(identity["start"], "Wed Nov 18 19:00:01 2026")

    def test_zombie_returns_none(self):
        stdout = "  4242 Z    Wed Nov 18 19:00:01 2026\n"
        with mock.patch("research.state.subprocess.run",
                        return_value=self._completed(stdout)):
            self.assertIsNone(state._ps_identity(4242))

    def test_missing_process_returns_none(self):
        with mock.patch("research.state.subprocess.run",
                        return_value=self._completed("", returncode=1)):
            self.assertIsNone(state._ps_identity(42))

    def test_ps_failure_returns_none(self):
        with mock.patch("research.state.subprocess.run", side_effect=OSError("no ps")):
            self.assertIsNone(state._ps_identity(42))

    def test_pid_mismatch_returns_none(self):
        stdout = "  9999 Ss   Wed Nov 18 19:00:01 2026\n"
        with mock.patch("research.state.subprocess.run",
                        return_value=self._completed(stdout)):
            self.assertIsNone(state._ps_identity(4242))


class PsutilIdentityTests(unittest.TestCase):
    def test_psutil_identity_or_unavailable(self):
        identity = state._psutil_identity(1)
        if identity == "unavailable":
            self.skipTest("psutil not installed")
        if identity is not None:  # pid 1 may be hidden by the sandbox
            self.assertEqual(identity["pid"], 1)
            self.assertIn("start", identity)

    def test_nonexistent_pid_returns_none_or_unavailable(self):
        identity = state._psutil_identity(2 ** 22)
        self.assertIn(identity, (None, "unavailable"))


class PlatformDispatchTests(unittest.TestCase):
    def test_proc_platform_uses_proc_reader(self):
        with mock.patch("research.state._PROC_AVAILABLE", True), \
             mock.patch("research.state._proc_identity", return_value={"pid": 1}) as proc, \
             mock.patch("research.state._psutil_identity") as psutil_reader, \
             mock.patch("research.state._ps_identity") as ps:
            self.assertEqual(state.process_identity(1), {"pid": 1})
        proc.assert_called_once_with(1)
        psutil_reader.assert_not_called()
        ps.assert_not_called()

    def test_macos_platform_prefers_psutil_reader(self):
        with mock.patch("research.state._PROC_AVAILABLE", False), \
             mock.patch("research.state._psutil_identity", return_value={"pid": 2}) as psutil_reader, \
             mock.patch("research.state._ps_identity") as ps, \
             mock.patch("research.state._proc_identity") as proc:
            self.assertEqual(state.process_identity(2), {"pid": 2})
        psutil_reader.assert_called_once_with(2)
        ps.assert_not_called()
        proc.assert_not_called()

    def test_macos_platform_falls_back_to_ps_without_psutil(self):
        with mock.patch("research.state._PROC_AVAILABLE", False), \
             mock.patch("research.state._psutil_identity", return_value="unavailable"), \
             mock.patch("research.state._ps_identity", return_value={"pid": 3}) as ps:
            self.assertEqual(state.process_identity(3), {"pid": 3})
        ps.assert_called_once_with(3)

    def test_current_platform_identity_roundtrip(self):
        identity = state.process_identity(1)  # launchd/pid 1 always exists
        if identity is not None:  # sandbox may hide it; then skip value checks
            self.assertEqual(identity["pid"], 1)
            self.assertEqual(identity["host"], socket.gethostname())


class ProcessStateTests(unittest.TestCase):
    def test_foreign_host_is_unknown(self):
        identity = {"host": "other-host", "pid": 1, "start": "x"}
        self.assertEqual(state.process_state(identity), "unknown")

    def test_missing_process_is_missing(self):
        identity = {"host": socket.gethostname(), "pid": 1, "start": "x"}
        with mock.patch("research.state.process_identity", return_value=None):
            self.assertEqual(state.process_state(identity), "missing")

    def test_same_identity_is_running(self):
        identity = {"host": socket.gethostname(), "pid": 1, "start": "x"}
        with mock.patch("research.state.process_identity", return_value=identity):
            self.assertEqual(state.process_state(identity), "running")

    def test_recycled_pid_is_missing(self):
        identity = {"host": socket.gethostname(), "pid": 1, "start": "x"}
        other = {"host": socket.gethostname(), "pid": 1, "start": "y"}
        with mock.patch("research.state.process_identity", return_value=other):
            self.assertEqual(state.process_state(identity), "missing")


if __name__ == "__main__":
    unittest.main()
