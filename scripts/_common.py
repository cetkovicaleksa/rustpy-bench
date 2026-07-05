"""Shared helpers for the strong/weak scaling benchmark drivers."""
import os, sys, shutil, subprocess, time
from pathlib import Path

# ---------------------------------------------------------------------------
# Locate solver binaries / scripts
# ---------------------------------------------------------------------------

def _find(name: str, env_var: str | None = None) -> str:
    """Return the absolute path to a solver, or raise a clear error."""
    if env_var:
        override = os.environ.get(env_var)
        if override:
            return override

    found = shutil.which(name)
    if found:
        return found

    # Also check the repo's cargo release target dir, relative to this file.
    repo_root = Path(__file__).parent.parent
    candidate = repo_root / "target" / "release" / name
    if candidate.exists():
        return str(candidate)

    raise FileNotFoundError(
        f"Could not find '{name}'.  "
        f"Run 'uv sync --dev' (Python) or 'cargo build --release' (Rust) first.  "
        f"Or set {env_var or 'PATH'} to override."
    )


def solvers() -> dict[str, str]:
    return {
        "heatpy":    _find("heatpy"),
        "heatpy-mp": _find("heatpy-mp"),
        "heatrs":    _find("heatrs",    "HEATRS_BIN"),
        "heatrs-mt": _find("heatrs-mt", "HEATRS_MT_BIN"),
    }


# ---------------------------------------------------------------------------
# Run one subprocess timed invocation
# ---------------------------------------------------------------------------

def run_solver(cmd: list[str], *, timeout_s: float = 3600) -> float:
    """Launch `cmd`, stream its stderr to our stderr, and return wall-clock seconds.

    Note: we measure wall time of the subprocess, not the compute-only time
    that the solver writes into the HDF5 file.  The benchmark scripts use the
    HDF5 `elapsed_seconds` attribute for the actual timing numbers; this return
    value is only used for a human-readable progress line.
    """
    t0 = time.perf_counter()
    result = subprocess.run(
        cmd,
        stderr=subprocess.PIPE,
        timeout=timeout_s,
        check=False,
    )
    wall = time.perf_counter() - t0

    # Always echo solver stderr so the user can see per-run progress.
    if result.stderr:
        sys.stderr.buffer.write(result.stderr)
        sys.stderr.flush()

    if result.returncode != 0:
        raise RuntimeError(
            f"Solver exited with code {result.returncode}:\n  {' '.join(cmd)}"
        )
    return wall
