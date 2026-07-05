#!/usr/bin/env python3
"""Strong-scaling benchmark driver.

Fixed problem size (nx, ny, t from experiment.toml [scaling.strong]).
Runs heatpy and heatrs as serial baselines (once each per repetition),
then sweeps heatpy-mp and heatrs-mt across all core counts.
Each (variant, cores, repetition) lands in its own HDF5 group:

  <out>.h5#/strong/heatpy/nx{nx}_ny{ny}/cores1/run0 ... run{N-1}
  <out>.h5#/strong/heatpy-mp/nx{nx}_ny{ny}/cores{c}/run{r}
  <out>.h5#/strong/heatrs/nx{nx}_ny{ny}/cores1/run{r}
  <out>.h5#/strong/heatrs-mt/nx{nx}_ny{ny}/cores{c}/run{r}

Usage
-----
  python scripts/strong_scaling.py --out results/strong.h5
  python scripts/strong_scaling.py --out results/strong.h5 --reps 5 --snapshot-every 0
"""
import sys, argparse
from pathlib import Path

# Make sure scripts/_common.py is importable from any cwd.
sys.path.insert(0, str(Path(__file__).parent))
from _common import run_solver, solvers

from rustpy_bench.core.config import get_config


def build_cmd(
    solver_path: str,
    name: str,
    nx: int,
    ny: int,
    t: float,
    workers: int,
    out_spec: str,
    run_id: int,
    snapshot_every: int,
) -> list[str]:
    cmd = [
        solver_path,
        "--nx", str(nx),
        "--ny", str(ny),
        "--t",  str(t),
        "--out", out_spec,
        "--snapshot-every", str(snapshot_every),
        "--run-id", str(run_id),
    ]
    if name in ("heatpy-mp",):
        cmd += ["--workers", str(workers)]
    if name in ("heatrs-mt",):
        cmd += ["--threads", str(workers)]
    return cmd


def main() -> None:
    cfg = get_config()
    s = cfg.strong

    p = argparse.ArgumentParser()
    p.add_argument("--out",           required=True,          help="Output HDF5 file path (no # group)")
    p.add_argument("--reps",          type=int,  default=cfg.repetitions, help="Repetitions per config")
    p.add_argument("--snapshot-every",type=int,  default=0,  help="Snapshot stride (0 = initial+final only)")
    p.add_argument("--cores",         type=int, nargs="+",   help="Override core list")
    p.add_argument("--variants",      nargs="+",              help="Subset of variants to run")
    args = p.parse_args()

    cores_list = args.cores or list(s.cores)
    all_variants = ["heatpy", "heatpy-mp", "heatrs", "heatrs-mt"]
    variants = args.variants or all_variants
    sv = solvers()

    print(f"[strong] nx={s.nx} ny={s.ny} t={s.t}s  reps={args.reps}  "
          f"cores={cores_list}  variants={variants}")
    print(f"[strong] output -> {args.out}")

    for variant in variants:
        if variant not in sv:
            print(f"  skip unknown variant '{variant}'", file=sys.stderr)
            continue
        solver_path = sv[variant]

        # Serial solvers: run at cores=1 regardless of the sweep list.
        core_sweep = [1] if variant in ("heatpy", "heatrs") else cores_list

        for cores in core_sweep:
            group = f"/strong/{variant}/nx{s.nx}_ny{s.ny}/cores{cores}"
            print(f"\n  [{variant}] cores={cores}  ({args.reps} reps)")
            for rep in range(args.reps):
                cmd = build_cmd(
                    solver_path, variant,
                    s.nx, s.ny, s.t, cores,
                    out_spec=f"{args.out}#{group}",
                    run_id=rep,
                    snapshot_every=args.snapshot_every,
                )
                wall = run_solver(cmd)
                print(f"    rep {rep:>3}: wall={wall:.3f}s")


if __name__ == "__main__":
    main()
