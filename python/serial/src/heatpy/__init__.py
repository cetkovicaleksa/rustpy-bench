import typer
from typing import Optional

from .solver import solve
from rustpy_bench.core.config import get_config
from rustpy_bench.core.io import open_run_group, write_run
from rustpy_bench.core.solver import EquationParams



def _main(
    nx: int = typer.Option(..., help="Grid points in x"),
    ny: int = typer.Option(..., help="Grid points in y"),
    t: float = typer.Option(..., help="Total simulated time [s]"),
    out: Optional[str] = typer.Option(
        "heatpy.h5", help="HDF5 target: path/to/file.h5#/group/path (group default: '/')"
    ),
    cfl: Optional[float] = typer.Option(
        None, help="CFL number (default: experiment.toml [equation].cfl)"
    ),
    snapshot_every: Optional[int] = typer.Option(
        None,
        help="Save a snapshot every N iterations (default: experiment.toml "
        "[experiment].snapshot_every; 0 = initial+final only)",
    ),
    run_id: Optional[str] = typer.Option(
        None, help="Run identifier / HDF5 subgroup name (default: timestamp-based)"
    ),
) -> None:
    cfg = get_config()
    params = EquationParams(nx=nx, ny=ny, t=t, cfl=cfl if cfl is not None else cfg.cfl)
    snap_every = snapshot_every if snapshot_every is not None else cfg.snapshot_every

    snapshots, snapshot_iters, elapsed = solve(params, snap_every)

    with open_run_group(out) as group:
        write_run(
            group,
            params=params,
            variant="serial",
            n_workers=1,
            elapsed_seconds=elapsed,
            snapshots=snapshots,
            snapshot_iters=snapshot_iters,
            run_id=run_id,
        )

    typer.echo(
        f"heatpy: nx={nx} ny={ny} nt={params.nt} dt={params.dt:.3e}s "
        f"elapsed={elapsed:.4f}s -> {out}"
    )


def main() -> None:
    typer.run(_main)
