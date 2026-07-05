import time, numpy as np

from rustpy_bench.core.config import get_config
from rustpy_bench.core.ic import initial_field, snapshot_iterations
from rustpy_bench.core.solver import EquationParams


def solve(
    params: EquationParams, snapshot_every: int
) -> tuple[np.ndarray, np.ndarray, float]:
    """Run the FTCS solve loop.

    Returns (snapshots, snapshot_iters, elapsed_seconds). `elapsed_seconds`
    covers only this loop -- no array allocation outside it, no file I/O --
    so it's a fair number to compare against the parallel/Rust variants.
    """
    cold = get_config().initial_condition.cold_value
    T = initial_field(params)

    rx = params.alpha * params.dt / params.dx**2
    ry = params.alpha * params.dt / params.dy**2

    wanted_iters = snapshot_iterations(params.nt, snapshot_every)
    wanted_set = set(wanted_iters)
    snapshots = [T.copy()]  # iteration 0, always recorded

    start = time.perf_counter()
    for it in range(1, params.nt + 1):
        lap = rx * (np.roll(T, -1, axis=1) - 2 * T + np.roll(T, 1, axis=1)) + ry * (
            np.roll(T, -1, axis=0) - 2 * T + np.roll(T, 1, axis=0)
        )
        T = T + lap
        # np.roll wraps around, so re-pin the boundary every step.
        T[0, :] = T[-1, :] = T[:, 0] = T[:, -1] = cold

        if it in wanted_set:
            snapshots.append(T.copy())
    elapsed = time.perf_counter() - start

    return np.stack(snapshots), np.array(wanted_iters, dtype=np.int64), elapsed
