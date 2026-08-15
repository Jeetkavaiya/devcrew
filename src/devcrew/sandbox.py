from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 15


@dataclass
class SandboxResult:
    """Outcome of a single sandboxed execution.

    `passed` is only meaningful for the pytest-runner helper (exit code 0).
    For arbitrary script execution, check `returncode` / `timed_out` /
    `errored` yourself — "passed" has no universal meaning outside a test
    context.
    """

    passed: bool
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    errored: bool = False
    error_message: str = ""
    duration_seconds: float = 0.0
    files_written: list[str] = field(default_factory=list)


def _make_restricted_tempdir() -> Path:
    """Create a fresh, isolated temp directory for one sandbox run.

    Each call gets its own directory under the system temp root so
    concurrent/sequential runs never see each other's files, and cleanup
    is a single `shutil.rmtree` regardless of what the executed code wrote.
    """
    return Path(tempfile.mkdtemp(prefix="devcrew_sandbox_"))


def run_pytest_on_files(
    code: str,
    test_code: str,
    *,
    code_filename: str = "solution.py",
    test_filename: str = "test_solution.py",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> SandboxResult:
    """Write `code` and `test_code` into an isolated temp dir and run pytest.

    This is the primary entry point the Tester node uses: `code` is the
    Coder's implementation, `test_code` is the independently-written test
    suite (from the spec, not from `code`). Both land in the same temp dir
    so the test file's `from solution import ...`-style local import works,
    then pytest runs against just that directory — nothing else on disk is
    visible or affected.

    Isolation notes (subprocess-level, not container-level):
    - Runs in its own temp dir via `cwd=`, so relative-path side effects
      are contained there.
    - `timeout_seconds` kills a hung process via `subprocess.run(timeout=)`,
      which raises `TimeoutExpired`; we catch that and report `timed_out`.
    - Uses `sys.executable -m pytest` (not a bare `pytest` on PATH) so it
      runs in the same interpreter/venv as the calling process.
    - The temp dir is always removed in a `finally` block, even on timeout
      or crash, so failed runs don't accumulate on disk.
    """
    tmpdir = _make_restricted_tempdir()
    try:
        code_path = tmpdir / code_filename
        test_path = tmpdir / test_filename
        code_path.write_text(code, encoding="utf-8")
        test_path.write_text(test_code, encoding="utf-8")

        import time

        start = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", test_filename, "-v"],
                cwd=str(tmpdir),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            return SandboxResult(
                passed=False,
                returncode=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                timed_out=True,
                errored=True,
                error_message=(
                    f"Execution exceeded {timeout_seconds}s timeout and was killed."
                ),
                duration_seconds=duration,
                files_written=[code_filename, test_filename],
            )
        except OSError as exc:
            duration = time.monotonic() - start
            return SandboxResult(
                passed=False,
                returncode=None,
                stdout="",
                stderr=str(exc),
                errored=True,
                error_message=f"Failed to launch sandbox subprocess: {exc}",
                duration_seconds=duration,
                files_written=[code_filename, test_filename],
            )

        duration = time.monotonic() - start
        return SandboxResult(
            passed=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=duration,
            files_written=[code_filename, test_filename],
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def run_python_file(
    code: str,
    *,
    filename: str = "script.py",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    args: list[str] | None = None,
) -> SandboxResult:
    """Run a standalone Python file in an isolated temp dir.

    Not currently called by the Tester node (which uses
    `run_pytest_on_files` instead), but kept as a general-purpose primitive
    since earlier sandbox designs / future nodes may want to just execute
    a script without pytest involved. Same isolation/timeout/cleanup
    guarantees as `run_pytest_on_files`.
    """
    tmpdir = _make_restricted_tempdir()
    try:
        script_path = tmpdir / filename
        script_path.write_text(code, encoding="utf-8")

        import time

        start = time.monotonic()
        cmd = [sys.executable, filename, *(args or [])]
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(tmpdir),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            duration = time.monotonic() - start
            return SandboxResult(
                passed=False,
                returncode=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                timed_out=True,
                errored=True,
                error_message=(
                    f"Execution exceeded {timeout_seconds}s timeout and was killed."
                ),
                duration_seconds=duration,
                files_written=[filename],
            )
        except OSError as exc:
            duration = time.monotonic() - start
            return SandboxResult(
                passed=False,
                returncode=None,
                stdout="",
                stderr=str(exc),
                errored=True,
                error_message=f"Failed to launch sandbox subprocess: {exc}",
                duration_seconds=duration,
                files_written=[filename],
            )

        duration = time.monotonic() - start
        return SandboxResult(
            passed=proc.returncode == 0,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            duration_seconds=duration,
            files_written=[filename],
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)