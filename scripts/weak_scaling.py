#!/usr/bin/env python3
"""Weak-scaling benchmark driver.

Per-core grid size is held constant at nx0×ny0 (from experiment.toml
[scaling.weak]).  For n cores, the total grid grows to nx0√n × ny0√n so
work-per-core stays ~constant.  Serial baselines run at the n=1 grid only.

Group layout in the output HDF5 file:

  <out>.h5#/weak/heatpy/nx{nx}_ny{ny}/cores1/run{r}         (n=1 baseline only)
  <out>.h5#/weak/heatpy-mp/nx{nx}_ny{ny}/cores{c}/run{r}    (all core counts)
  <out>.h5#/weak/heatrs/nx{nx}_ny{ny}/cores1/run{r}
  <out>.h5#/weak/heatrs-mt/nx{nx}_ny{ny}/cores{c}/run{r}

Usage
-----
  python scripts/weak_scaling.py --out results/weak.h5
  python scripts/weak_scaling.py --out results/weak.h5 --reps 5 --snapshot-every 0
"""
import sys, argparse
from pathlib import Path

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
    w = cfg.weak

    p = argparse.ArgumentParser()
    p.add_argument("--out",           required=True,          help="Output HDF5 file path (no # group)")
    p.add_argument("--reps",          type=int,  default=cfg.repetitions, help="Repetitions per config")
    p.add_argument("--snapshot-every",type=int,  default=0,  help="Snapshot stride (0 = initial+final only)")
    p.add_argument("--cores",         type=int, nargs="+",   help="Override core list")
    p.add_argument("--variants",      nargs="+",              help="Subset of variants to run")
    args = p.parse_args()

    cores_list = args.cores or list(w.cores)
    all_variants = ["heatpy", "heatpy-mp", "heatrs", "heatrs-mt"]
    variants = args.variants or all_variants
    sv = solvers()

    print(f"[weak] nx0={w.nx0} ny0={w.ny0} t={w.t}s  reps={args.reps}  "
          f"cores={cores_list}  variants={variants}")
    print(f"[weak] output -> {args.out}")
    print("[weak] grid sizes:")
    for c in cores_list:
        nx, ny = w.grid_for(c)
        print(f"  cores={c}: nx={nx} ny={ny} (total {nx*ny} cells)")

    for variant in variants:
        if variant not in sv:
            print(f"  skip unknown variant '{variant}'", file=sys.stderr)
            continue
        solver_path = sv[variant]

        is_serial = variant in ("heatpy", "heatrs")
        # Serial: only the n=1 grid (keeping 1 core of work consistent).
        core_sweep = [1] if is_serial else cores_list

        for cores in core_sweep:
            nx, ny = w.grid_for(cores)
            group = f"/weak/{variant}/nx{nx}_ny{ny}/cores{cores}"
            print(f"\n  [{variant}] cores={cores} nx={nx} ny={ny}  ({args.reps} reps)")
            for rep in range(args.reps):
                cmd = build_cmd(
                    solver_path, variant,
                    nx, ny, w.t, cores,
                    out_spec=f"{args.out}#{group}",
                    run_id=rep,
                    snapshot_every=args.snapshot_every,
                )
                wall = run_solver(cmd)
                print(f"    rep {rep:>3}: wall={wall:.3f}s")


if __name__ == "__main__":
    main()
