import time, numpy as np

from multiprocessing import Barrier, Process
from multiprocessing.shared_memory import SharedMemory

from rustpy_bench.core.config import get_config
from rustpy_bench.core.ic import initial_field, snapshot_iterations
from rustpy_bench.core.solver import EquationParams



def _partition_rows(n_interior: int, n_workers: int) -> list[tuple[int, int]]:
    """Split global interior rows [1, ny-2] as evenly as possible among workers.

    Returns (start, end) pairs in global row coordinates, end exclusive.
    """
    n_workers = min(n_workers, max(1, n_interior))
    base, rem = divmod(n_interior, n_workers)
    ranges = []
    row = 1
    for w in range(n_workers):
        size = base + (1 if w < rem else 0)
        if size > 0:
            ranges.append((row, row + size))
            row += size
    return ranges


def _worker(
    worker_id: int,
    row_range: tuple[int, int],
    shm_a_name: str,
    shm_b_name: str,
    shm_snap_name: str,
    shape: tuple[int, int],
    snapshot_iters: list[int],
    nt: int,
    rx: float,
    ry: float,
    cold: float,
    barrier,
) -> None:
    ny, nx = shape
    shm_a = SharedMemory(name=shm_a_name)
    shm_b = SharedMemory(name=shm_b_name)
    shm_snap = SharedMemory(name=shm_snap_name)
    try:
        buf_a = np.ndarray(shape, dtype=np.float64, buffer=shm_a.buf)
        buf_b = np.ndarray(shape, dtype=np.float64, buffer=shm_b.buf)
        snaps = np.ndarray(
            (len(snapshot_iters), ny, nx), dtype=np.float64, buffer=shm_snap.buf
        )

        y0, y1 = row_range
        wanted = set(snapshot_iters)
        # snapshot index 0 (the initial field) is written by the parent before
        # any worker is spawned, so the first index a worker may write is 1.
        snap_idx = 1

        for it in range(1, nt + 1):
            src, dst = (buf_a, buf_b) if it % 2 == 1 else (buf_b, buf_a)

            interior = src[y0:y1, :]
            lap_x = rx * (
                np.roll(interior, -1, axis=1) - 2 * interior + np.roll(interior, 1, axis=1)
            )
            lap_y = ry * (src[y0 - 1 : y1 - 1, :] - 2 * interior + src[y0 + 1 : y1 + 1, :])
            dst[y0:y1, :] = interior + lap_x + lap_y
            # np.roll wraps in x, so re-pin the left/right edges of our rows.
            dst[y0:y1, 0] = cold
            dst[y0:y1, -1] = cold

            barrier.wait()

            # Safe without extra sync: `dst` (this iteration's result) is only
            # ever written again two iterations from now, by which point this
            # copy (sequential in worker 0's own code, strictly before it
            # computes that future write) has long completed -- see the
            # race-freedom note in this module's docstring-level comments.
            if worker_id == 0 and it in wanted:
                snaps[snap_idx, :, :] = dst
                snap_idx += 1
    finally:
        shm_a.close()
        shm_b.close()
        shm_snap.close()


def solve(
    params: EquationParams, snapshot_every: int, n_workers: int
) -> tuple[np.ndarray, np.ndarray, float]:
    """Run the FTCS solve loop in parallel across `n_workers` processes.

    Domain decomposition: the grid's interior rows are split into contiguous
    row-blocks, one per worker process. All workers share two full (ny, nx)
    double-buffers via shared memory and ping-pong between them each
    iteration, synchronized by a single Barrier -- so halo rows are read
    directly out of shared memory rather than message-passed. Worker 0 also
    copies out periodic snapshots; see `_worker` for why that's race-free
    with only one barrier per iteration.

    Returns (snapshots, snapshot_iters, elapsed_seconds). Timing covers only
    process spawn + the compute loop + join -- not shared-memory allocation
    or initial-condition setup -- to stay comparable to the serial timing.
    """
    cold = get_config().initial_condition.cold_value
    ny, nx = params.ny, params.nx
    shape = (ny, nx)
    nbytes = ny * nx * 8

    wanted_iters = snapshot_iterations(params.nt, snapshot_every)

    shm_a = SharedMemory(create=True, size=nbytes)
    shm_b = SharedMemory(create=True, size=nbytes)
    shm_snap = SharedMemory(create=True, size=len(wanted_iters) * nbytes)
    try:
        buf_a = np.ndarray(shape, dtype=np.float64, buffer=shm_a.buf)
        buf_b = np.ndarray(shape, dtype=np.float64, buffer=shm_b.buf)
        snaps = np.ndarray((len(wanted_iters), ny, nx), dtype=np.float64, buffer=shm_snap.buf)

        T0 = initial_field(params)
        buf_a[:, :] = T0
        buf_b[:, :] = T0  # boundary rows/cols never get overwritten by workers
        snaps[0, :, :] = T0

        rx = params.alpha * params.dt / params.dx**2
        ry = params.alpha * params.dt / params.dy**2

        row_ranges = _partition_rows(ny - 2, n_workers)
        barrier = Barrier(len(row_ranges))

        start = time.perf_counter()
        procs = [
            Process(
                target=_worker,
                args=(
                    wid,
                    row_range,
                    shm_a.name,
                    shm_b.name,
                    shm_snap.name,
                    shape,
                    wanted_iters,
                    params.nt,
                    rx,
                    ry,
                    cold,
                    barrier,
                ),
            )
            for wid, row_range in enumerate(row_ranges)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join()
        elapsed = time.perf_counter() - start

        snapshots = np.array(snaps)  # copy out before shared memory is unlinked
    finally:
        shm_a.close()
        shm_b.close()
        shm_snap.close()
        shm_a.unlink()
        shm_b.unlink()
        shm_snap.unlink()

    return snapshots, np.array(wanted_iters, dtype=np.int64), elapsed
