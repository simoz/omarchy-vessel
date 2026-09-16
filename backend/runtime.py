"""Install the single live dependency into a private, reusable virtualenv."""

import fcntl
import hashlib
import os
import shutil
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "requirements.txt"
WEBSOCKETS_VERSION = "17.1"


def location():
    # A new interpreter or dependency pin gets a separate environment. Nothing
    # is written into the Git checkout or the system Python installation.
    identity = f"{sys.version}|{sys.base_prefix}|".encode() + REQUIREMENTS.read_bytes()
    tag = hashlib.sha256(identity).hexdigest()[:16]
    base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "omarchy-vessel" / "python" / tag


def run_command(args, timeout):
    env = dict(os.environ)
    for name in ("AISSTREAM_API_KEY", "PYTHONPATH", "PYTHONHOME"):
        env.pop(name, None)
    # Suppress installer output, which isn't part of the QML JSON protocol.
    # Kill the process group on cancellation so setup can't outlive the widget.
    child = subprocess.Popen(
        args,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        if child.wait(timeout=timeout):
            raise RuntimeError("Dependency setup failed")
    finally:
        if child.poll() is None:
            # The child can exit between poll() and killpg().
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)
            child.wait()


def ensure_runtime(output):
    target = location()
    if Path(sys.prefix).resolve() == target.resolve():
        import websockets

        if websockets.__version__ != WEBSOCKETS_VERSION:
            raise RuntimeError("Wrong runtime version")
        return
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    python = target / "bin" / "python"
    output("INSTALLING", "Preparing the live receiver. This runs only when needed.")
    with (target.parent / (target.name + ".lock")).open("w") as lock:
        # One installer across monitors or simultaneous shell restarts.
        fcntl.flock(lock, fcntl.LOCK_EX)
        ready = False
        if python.exists():
            try:
                run_command(
                    [
                        str(python),
                        "-I",
                        "-c",
                        f"import websockets; assert websockets.__version__ == {WEBSOCKETS_VERSION!r}",
                    ],
                    10,
                )
                ready = True
            except (RuntimeError, OSError, subprocess.TimeoutExpired):
                pass
        if not ready:
            if target.exists():
                shutil.rmtree(target)
            run_command([sys.executable, "-I", "-m", "venv", str(target)], 120)
            run_command(
                [
                    str(python),
                    "-I",
                    "-m",
                    "pip",
                    "--isolated",
                    "install",
                    "--disable-pip-version-check",
                    "--no-input",
                    "--no-deps",
                    "--only-binary=:all:",
                    "--require-hashes",
                    "--retries",
                    "2",
                    "--timeout",
                    "20",
                    "-r",
                    str(REQUIREMENTS),
                ],
                180,
            )
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    # Replace this process, retaining the same PID for Quickshell lifecycle control.
    os.execve(
        str(python),
        [str(python), "-B", str(ROOT / "backend" / "vessel.py"), *sys.argv[1:]],
        env,
    )
