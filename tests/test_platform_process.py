import subprocess
import unittest
from datetime import datetime
from unittest import mock

from core.platform import ProcessInfo
from core.platform import linux, macos


class LinuxProcessPrimitiveTests(unittest.TestCase):
    def test_parse_process_snapshot_preserves_args(self):
        out = (
            " 123 1 pts/3 bash bash -lc claude --resume abc\n"
            " bad 1 pts/4 zsh zsh\n"
            " 124 123 ? python python worker.py --flag value\n"
            " 125 123 pts/5\n"
        )
        table = linux._parse_ps_processes(out)
        self.assertEqual(table[123], ProcessInfo(
            pid=123,
            ppid=1,
            tty="pts/3",
            comm="bash",
            args="bash -lc claude --resume abc",
        ))
        self.assertEqual(table[124].args, "python worker.py --flag value")
        self.assertNotIn(125, table)

    def test_list_processes_returns_empty_on_missing_ps(self):
        with mock.patch("core.platform.linux.subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(linux.list_processes(), {})

    def test_list_processes_uses_replacement_decoding(self):
        proc = subprocess.CompletedProcess(["ps"], 0, stdout=" 7 1 pts/1 zsh zsh\n", stderr="")
        with mock.patch("core.platform.linux.subprocess.run", return_value=proc) as run:
            self.assertIn(7, linux.list_processes())
        run.assert_called_once_with(
            ["ps", "-eo", "pid=,ppid=,tty=,comm=,args="],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=5,
        )

    def test_list_processes_returns_empty_on_nonzero_exit(self):
        proc = subprocess.CompletedProcess(["ps"], 1, stdout="", stderr="error")
        with mock.patch("core.platform.linux.subprocess.run", return_value=proc):
            self.assertEqual(linux.list_processes(), {})

    def test_process_cwd_returns_none_on_error(self):
        with mock.patch("core.platform.linux.os.readlink", side_effect=PermissionError):
            self.assertIsNone(linux.process_cwd(123))

    def test_process_start_ms_returns_zero_on_error(self):
        with mock.patch("core.platform.linux.os.stat", side_effect=FileNotFoundError):
            self.assertEqual(linux.process_start_ms(123), 0)


class MacOSProcessPrimitiveTests(unittest.TestCase):
    def test_parse_process_snapshot_preserves_command(self):
        out = (
            " 321 1 ttys001 node /n/bin/claude --resume abc\n"
            " nope 1 ttys002 zsh zsh\n"
            " 322 321 ?? ps -axo pid=,ppid=,tty=,command=\n"
        )
        table = macos._parse_ps_processes(out)
        self.assertEqual(table[321], ProcessInfo(
            pid=321,
            ppid=1,
            tty="ttys001",
            args="node /n/bin/claude --resume abc",
            comm="",
        ))
        self.assertEqual(table[322].tty, "??")

    def test_list_processes_uses_safe_argv_and_degrades_on_failure(self):
        proc = subprocess.CompletedProcess(["ps"], 0, stdout=" 7 1 ttys001 codex\n", stderr="")
        with mock.patch("core.platform.macos.subprocess.run", return_value=proc) as run:
            self.assertIn(7, macos.list_processes())
        run.assert_called_once_with(
            ["/bin/ps", "-axww", "-o", "pid=,ppid=,tty=,command="],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=5,
        )

        with mock.patch("core.platform.macos.subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(macos.list_processes(), {})

        nonzero = subprocess.CompletedProcess(["ps"], 1, stdout=" 7 1 ttys001 codex\n", stderr="error")
        with mock.patch("core.platform.macos.subprocess.run", return_value=nonzero):
            self.assertEqual(macos.list_processes(), {})

    def test_lsof_cwd_parser_returns_first_absolute_name(self):
        output = "\n".join(["p123", "fcwd", "nrelative", "n/tmp/example-project", "n/private/tmp"])
        self.assertEqual(macos._parse_lsof_cwd(output), "/tmp/example-project")

    def test_process_cwd_returns_none_for_lsof_failures(self):
        with mock.patch("core.platform.macos.subprocess.run", side_effect=FileNotFoundError):
            self.assertIsNone(macos.process_cwd(123))

        nonzero = subprocess.CompletedProcess(["lsof"], 1, stdout="n/private\n", stderr="denied")
        with mock.patch("core.platform.macos.subprocess.run", return_value=nonzero):
            self.assertIsNone(macos.process_cwd(123))

        empty = subprocess.CompletedProcess(["lsof"], 0, stdout="", stderr="")
        with mock.patch("core.platform.macos.subprocess.run", return_value=empty):
            self.assertIsNone(macos.process_cwd(123))

        malformed = subprocess.CompletedProcess(["lsof"], 0, stdout="p123\nnrelative\n", stderr="")
        with mock.patch("core.platform.macos.subprocess.run", return_value=malformed):
            self.assertIsNone(macos.process_cwd(123))

    def test_process_cwd_converts_pid_before_subprocess(self):
        proc = subprocess.CompletedProcess(["lsof"], 0, stdout="n/tmp/project\n", stderr="")
        with mock.patch("core.platform.macos.subprocess.run", return_value=proc) as run:
            self.assertEqual(macos.process_cwd("123"), "/tmp/project")
        run.assert_called_once_with(
            ["/usr/sbin/lsof", "-a", "-p", "123", "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=5,
        )

    def test_lstart_parser_returns_epoch_ms(self):
        expected = int(datetime(2026, 7, 2, 10, 10, 22).timestamp() * 1000)
        self.assertEqual(macos._parse_lstart_ms("Thu Jul  2 10:10:22 2026\n"), expected)

    def test_process_start_ms_returns_zero_for_ps_failures(self):
        with mock.patch("core.platform.macos.subprocess.run", side_effect=FileNotFoundError):
            self.assertEqual(macos.process_start_ms(123), 0)

        nonzero = subprocess.CompletedProcess(["ps"], 1, stdout="Thu Jul 2 10:10:22 2026\n", stderr="")
        with mock.patch("core.platform.macos.subprocess.run", return_value=nonzero):
            self.assertEqual(macos.process_start_ms(123), 0)

        malformed = subprocess.CompletedProcess(["ps"], 0, stdout="not a date\n", stderr="")
        with mock.patch("core.platform.macos.subprocess.run", return_value=malformed):
            self.assertEqual(macos.process_start_ms(123), 0)

        empty = subprocess.CompletedProcess(["ps"], 0, stdout="", stderr="")
        with mock.patch("core.platform.macos.subprocess.run", return_value=empty):
            self.assertEqual(macos.process_start_ms(123), 0)

    def test_process_start_ms_converts_pid_before_subprocess(self):
        proc = subprocess.CompletedProcess(["ps"], 0, stdout="Thu Jul  2 10:10:22 2026\n", stderr="")
        with mock.patch("core.platform.macos.subprocess.run", return_value=proc) as run:
            self.assertGreater(macos.process_start_ms("456"), 0)
        run.assert_called_once_with(
            ["/bin/ps", "-o", "lstart=", "-p", "456"],
            capture_output=True,
            env=mock.ANY,
            text=True,
            timeout=5,
        )
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["LC_ALL"], "C")
        self.assertEqual(env["LANG"], "C")


if __name__ == "__main__":
    unittest.main()
