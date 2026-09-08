#!/usr/bin/env python3
"""The task runner. One implementation, two front doors.

``make <task>`` on macOS, Linux and CI; ``python scripts/tasks.py <task>``
everywhere, including Windows, where ``make`` is usually absent. The Makefile
delegates here rather than duplicating the commands, so the two cannot drift
apart - which is the usual fate of a Makefile plus a batch file.

Deliberately dependency-free: it runs on the system Python before anything has
been installed, because ``setup`` is one of the tasks.
"""

# A task runner talks to a person at a terminal; printing is the interface.
# ruff: noqa: T201

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

IS_WINDOWS = platform.system() == "Windows"
VENV_PYTHON = BACKEND / ".venv" / ("Scripts" if IS_WINDOWS else "bin") / (
    "python.exe" if IS_WINDOWS else "python"
)
NPM = "npm.cmd" if IS_WINDOWS else "npm"
NPX = "npx.cmd" if IS_WINDOWS else "npx"
UV = "uv.exe" if IS_WINDOWS else "uv"


class TaskFailedError(RuntimeError):
    pass


def run(command: Sequence[str], *, cwd: Path = ROOT, check: bool = True) -> int:
    printable = " ".join(str(part) for part in command)
    print(f"\n$ {printable}", flush=True)
    result = subprocess.run([str(part) for part in command], cwd=cwd)
    if check and result.returncode != 0:
        raise TaskFailedError(f"failed: {printable}")
    return result.returncode


def python() -> str:
    """The backend interpreter, or the current one before setup has run."""
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def require(tool: str) -> None:
    if shutil.which(tool) is None:
        raise TaskFailedError(
            f"'{tool}' is not on PATH. See README.md, Getting started, for what to install."
        )


# ================================================================= setup


def setup_backend() -> None:
    """Install backend dependencies from the committed lockfile."""
    require(UV)
    run([UV, "sync", "--frozen", "--group", "dev"], cwd=BACKEND)


def setup_frontend() -> None:
    """Install frontend dependencies from the committed lockfile."""
    require(NPM)
    run([NPM, "ci"], cwd=FRONTEND)


def data() -> None:
    """Regenerate the knowledge corpus and the opportunity datasets."""
    run([python(), "-m", "scripts.build_knowledge"], cwd=BACKEND)
    run([python(), "-m", "scripts.build_opportunity_data"], cwd=BACKEND)


def migrate() -> None:
    """Apply database migrations."""
    run([python(), "-m", "alembic", "upgrade", "head"], cwd=BACKEND)


def seed() -> None:
    """Load legal facts, ingest the corpus, register sources. Idempotent."""
    run([python(), "-m", "scripts.seed"], cwd=BACKEND)


def setup() -> None:
    """Everything a fresh clone needs."""
    setup_backend()
    setup_frontend()
    data()
    migrate()
    seed()
    print(
        "\n  Ready. Start it with:  python scripts/tasks.py dev   (or: make dev)\n"
        "  No API keys are needed. See .env.example for what they add.\n"
    )


# =================================================================== run


def dev_api() -> None:
    """Run the API on :8000 with reload."""
    run(
        [python(), "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
        cwd=BACKEND,
    )


def dev_web() -> None:
    """Run the web app on :3000."""
    run([NPM, "run", "dev"], cwd=FRONTEND)


def dev() -> None:
    """Run both, and stop both when one exits."""
    print("  API  -> http://localhost:8000/docs")
    print("  Web  -> http://localhost:3000\n")
    api = subprocess.Popen(
        [python(), "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
        cwd=BACKEND,
    )
    web = subprocess.Popen([NPM, "run", "dev"], cwd=FRONTEND)
    try:
        while True:
            for process in (api, web):
                if process.poll() is not None:
                    return
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in (web, api):
            if process.poll() is None:
                process.terminate()


# ================================================================= tests


def test_backend() -> None:
    """Backend tests. No network, no paid model calls."""
    run([python(), "-m", "pytest", "-q"], cwd=BACKEND)


def test_frontend() -> None:
    """Frontend unit tests."""
    run([NPX, "vitest", "run"], cwd=FRONTEND)


def test() -> None:
    """Backend and frontend unit tests."""
    test_backend()
    test_frontend()


def e2e() -> None:
    """End-to-end tests. Needs the API running on :8000."""
    run([NPX, "playwright", "test"], cwd=FRONTEND)


def evaluate() -> None:
    """AI evaluation suite. Scripted provider, so it costs nothing."""
    run([python(), "-m", "scripts.run_evals"], cwd=BACKEND)


# ================================================================ checks

_LINT_TARGETS = ["app", "scripts", "evals", "tests"]


def lint() -> None:
    """Lint the backend."""
    run([python(), "-m", "ruff", "check", *_LINT_TARGETS], cwd=BACKEND)


def format_code() -> None:
    """Auto-fix what can be auto-fixed."""
    run([python(), "-m", "ruff", "check", *_LINT_TARGETS, "--fix"], cwd=BACKEND)
    run([python(), "-m", "ruff", "format", *_LINT_TARGETS], cwd=BACKEND)


def typecheck() -> None:
    """Type-check both halves."""
    run([python(), "-m", "mypy", "app"], cwd=BACKEND)
    run([NPX, "tsc", "--noEmit"], cwd=FRONTEND)


def validate_data() -> None:
    """Gate the curated dataset: no unquoted figure on a real opportunity."""
    run([python(), "-m", "scripts.validate_curated"], cwd=BACKEND)


def check() -> None:
    """Everything CI runs, in the order that fails fastest."""
    lint()
    # Cheap, and it guards the product's central promise, so it runs early:
    # a fabricated compensation figure should fail the build before a slow
    # test suite gets the chance to pass.
    validate_data()
    typecheck()
    test()
    evaluate()
    print("\n  All checks passed.\n")


# ================================================================= build


def build() -> None:
    """Production build of the web app."""
    env = dict(os.environ, NEXT_TELEMETRY_DISABLED="1")
    print("\n$ npm run build", flush=True)
    result = subprocess.run([NPM, "run", "build"], cwd=FRONTEND, env=env)
    if result.returncode != 0:
        raise TaskFailedError("frontend build failed")


def docker_build() -> None:
    """Build both container images."""
    require("docker")
    run(["docker", "build", "-t", "mym-backend:local", "."], cwd=BACKEND)
    run(
        [
            "docker",
            "build",
            "-t",
            "mym-frontend:local",
            "--build-arg",
            "NEXT_PUBLIC_API_BASE_URL=http://localhost:8000",
            ".",
        ],
        cwd=FRONTEND,
    )


# ================================================================= clean


def clean() -> None:
    """Remove build artefacts and caches. Leaves the database alone."""
    for path in (
        FRONTEND / ".next",
        FRONTEND / "test-results",
        FRONTEND / "playwright-report",
        BACKEND / ".pytest_cache",
        BACKEND / ".mypy_cache",
        BACKEND / ".ruff_cache",
    ):
        shutil.rmtree(path, ignore_errors=True)
    for cache in BACKEND.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    print("  Cleaned.")


def reset() -> None:
    """Delete the local database and rebuild it. Destroys local accounts."""
    for pattern in ("app.db", "app.db-shm", "app.db-wal"):
        (BACKEND / "data" / pattern).unlink(missing_ok=True)
    shutil.rmtree(BACKEND / "data" / "uploads", ignore_errors=True)
    migrate()
    seed()


TASKS: dict[str, Callable[[], None]] = {
    "setup": setup,
    "setup-backend": setup_backend,
    "setup-frontend": setup_frontend,
    "data": data,
    "migrate": migrate,
    "seed": seed,
    "validate-data": validate_data,
    "dev": dev,
    "dev-api": dev_api,
    "dev-web": dev_web,
    "test": test,
    "test-backend": test_backend,
    "test-frontend": test_frontend,
    "e2e": e2e,
    "eval": evaluate,
    "lint": lint,
    "format": format_code,
    "typecheck": typecheck,
    "check": check,
    "build": build,
    "docker-build": docker_build,
    "clean": clean,
    "reset": reset,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Money You're Missing task runner.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Tasks:\n"
        + "\n".join(
            f"  {name:<16} {(fn.__doc__ or '').strip().splitlines()[0] if fn.__doc__ else ''}"
            for name, fn in TASKS.items()
        ),
    )
    parser.add_argument("task", choices=list(TASKS), metavar="TASK")
    args = parser.parse_args()

    try:
        TASKS[args.task]()
    except TaskFailedError as error:
        print(f"\n  {error}\n", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
