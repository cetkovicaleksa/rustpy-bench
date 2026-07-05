import time, socket, h5py, numpy as np

from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Iterator

from .solver import EquationParams


def parse_h5_target(spec: str) -> tuple[Path, str]:
    """Split a `path/to/file.h5#/group/path` spec into (file_path, group_path).

    This is what lets a whole experiment (e.g. weak scaling: every
    param combination x every repetition) live in a single HDF5 file --
    each run just gets its own group path within it. If no '#' is present,
    the group defaults to the file root '/'.
    """
    if "#" in spec:
        file_part, _, group_part = spec.partition("#")
    else:
        file_part, group_part = spec, "/"
    if not group_part.startswith("/"):
        group_part = "/" + group_part
    return Path(file_part), group_part


@contextmanager
def open_run_group(spec: str, mode: str = "a") -> Iterator[h5py.Group]:
    """Open (creating parent groups/dirs as needed) the group addressed by `spec`."""
    file_path, group_path = parse_h5_target(spec)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(file_path, mode) as f:
        group = f.require_group(group_path) if group_path != "/" else f["/"]
        yield group


def write_run(
    group: h5py.Group,
    *,
    params: EquationParams,
    variant: str,
    n_workers: int,
    elapsed_seconds: float,
    snapshots: np.ndarray,
    snapshot_iters: np.ndarray,
    run_id: int | str | None = None,
) -> h5py.Group:
    """Write one completed run into a fresh subgroup of `group`.

    `elapsed_seconds` must cover only the solve loop -- never file I/O -- so
    benchmark numbers aren't polluted by HDF5 write cost.

    `snapshots` has shape (n_snapshots, ny, nx); `snapshot_iters` holds the
    iteration index each snapshot was taken at (length n_snapshots, with the
    final entry == params.nt).
    """
    run_name = str(run_id) if run_id is not None else f"run_{int(time.time() * 1e6)}"
    run_group = group.create_group(run_name)

    for key, value in asdict(params).items():
        run_group.attrs[key] = value
    run_group.attrs["variant"] = variant
    run_group.attrs["n_workers"] = n_workers
    run_group.attrs["elapsed_seconds"] = elapsed_seconds
    run_group.attrs["hostname"] = socket.gethostname()
    run_group.attrs["timestamp"] = time.time()

    run_group.create_dataset(
        "snapshots", data=snapshots, compression="gzip", compression_opts=4
    )
    run_group.create_dataset("snapshot_iters", data=snapshot_iters)

    return run_group
