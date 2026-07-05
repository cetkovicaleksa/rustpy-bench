"""Load and aggregate benchmark results from an experiment HDF5 file.

HDF5 layout expected (as written by the scaling benchmark drivers):

  /strong/{variant}/nx{NX}_ny{NY}/cores{C}/run{R}  (attrs: elapsed_seconds, n_workers, …)
  /weak/{variant}/nx{NX}_ny{NY}/cores{C}/run{R}
"""
import numpy as np, h5py

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


ScalingKind = Literal["strong", "weak"]


@dataclass
class RunStats:
    variant: str
    cores: int
    nx: int
    ny: int
    times: np.ndarray   # shape (n_reps,), seconds
    mean: float
    std: float


def _collect_times(parent: h5py.Group) -> np.ndarray:
    """Collect elapsed_seconds from every run_* subgroup of `parent`."""
    times = []
    for key in sorted(parent.keys(), key=lambda k: int(k) if k.isdigit() else 0):
        run = parent[key]
        if "elapsed_seconds" in run.attrs:
            times.append(float(run.attrs["elapsed_seconds"]))
    return np.array(times, dtype=np.float64)


def load(h5_path: str | Path, kind: ScalingKind) -> list[RunStats]:
    """Return a list of RunStats, one per (variant, core-count) combination."""
    results: list[RunStats] = []
    with h5py.File(h5_path, "r") as f:
        if kind not in f:
            raise KeyError(f"Group '/{kind}' not found in {h5_path}")
        root = f[kind]
        for variant in sorted(root.keys()):
            var_group = root[variant]
            for grid_key in sorted(var_group.keys()):
                grid_group = var_group[grid_key]
                for cores_key in sorted(grid_group.keys()):
                    cores = int(cores_key.replace("cores", ""))
                    times = _collect_times(grid_group[cores_key])
                    if len(times) == 0:
                        continue
                    nx = ny = 0
                    for rkey in grid_group[cores_key].keys():
                        run0 = grid_group[cores_key][rkey]
                        nx = int(run0.attrs.get("nx", 0))
                        ny = int(run0.attrs.get("ny", 0))
                        break
                    results.append(
                        RunStats(
                            variant=variant,
                            cores=cores,
                            nx=nx,
                            ny=ny,
                            times=times,
                            mean=float(np.mean(times)),
                            std=float(np.std(times, ddof=1) if len(times) > 1 else 0.0),
                        )
                    )
    return results


def speedup_table(
    stats: list[RunStats],
    baseline_variant: str,
    parallel_variant: str,
) -> dict[int, tuple[float, float, float]]:
    """Return {cores: (speedup, std_lo, std_hi)} for a variant pair.

    Speedup = T_baseline_serial / T_parallel_cores.
    Error bars are propagated from the standard deviations.
    """
    baseline = next(
        (s for s in stats if s.variant == baseline_variant and s.cores == 1), None
    )
    if baseline is None:
        raise ValueError(
            f"No baseline found for variant='{baseline_variant}', cores=1"
        )

    T_b = baseline.mean
    sigma_b = baseline.std

    table: dict[int, tuple[float, float, float]] = {}
    for s in sorted(
        (x for x in stats if x.variant == parallel_variant),
        key=lambda x: x.cores,
    ):
        sp = T_b / s.mean
        # Error propagation: d(T_b/T_p) ≈ sp * sqrt((σ_b/T_b)^2 + (σ_p/T_p)^2)
        rel_err = np.sqrt((sigma_b / T_b) ** 2 + (s.std / s.mean) ** 2)
        sigma_sp = sp * rel_err
        table[s.cores] = (sp, max(0.0, sp - sigma_sp), sp + sigma_sp)
    return table
