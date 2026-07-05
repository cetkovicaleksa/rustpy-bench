use std::time::Instant;

use anyhow::Result;
use clap::Parser;
use ndarray::{Array3, s};
use rustpy_bench_core::{
    config::get_config,
    ic::{initial_field, snapshot_iterations},
    io::{open_run_group, write_run, RunData},
    solver::EquationParams,
};

#[derive(Parser)]
#[command(name = "heatrs", about = "Serial Rust FTCS solver for the 2D heat equation")]
struct Cli {
    #[arg(long)] nx: usize,
    #[arg(long)] ny: usize,
    #[arg(long)] t: f64,
    #[arg(long, help = "HDF5 target: path/to/file.h5#/group/path")] out: String,
    #[arg(long)] cfl: Option<f64>,
    #[arg(long)] snapshot_every: Option<i64>,
    #[arg(long)] run_id: Option<String>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let cfg = get_config();

    let params = EquationParams::new(cli.nx, cli.ny, cli.t, cli.cfl);
    let snap_every = cli.snapshot_every.unwrap_or(cfg.snapshot_every);
    let wanted_iters = snapshot_iterations(params.nt, snap_every);
    let cold = cfg.initial_condition.cold_value;

    let rx = params.alpha * params.dt / params.dx.powi(2);
    let ry = params.alpha * params.dt / params.dy.powi(2);

    let t0 = initial_field(&params, &cfg.initial_condition);
    let (ny, nx) = (params.ny, params.nx);
    let n_snaps = wanted_iters.len();
    let mut snapshots = Array3::<f64>::zeros((n_snaps, ny, nx));
    snapshots.slice_mut(s![0, .., ..]).assign(&t0);

    let mut t_cur = t0;
    let mut t_next = ndarray::Array2::<f64>::zeros((ny, nx));
    let wanted_set: std::collections::HashSet<u64> = wanted_iters.iter().copied().collect();
    let mut snap_idx = 1usize;

    let start = Instant::now();
    for it in 1..=params.nt {
        // Interior update: explicit FTCS stencil (no wrap, Dirichlet boundary frozen)
        for y in 1..ny - 1 {
            for x in 1..nx - 1 {
                let lap_x = t_cur[[y, x + 1]] - 2.0 * t_cur[[y, x]] + t_cur[[y, x - 1]];
                let lap_y = t_cur[[y + 1, x]] - 2.0 * t_cur[[y, x]] + t_cur[[y - 1, x]];
                t_next[[y, x]] = t_cur[[y, x]] + rx * lap_x + ry * lap_y;
            }
        }
        // Copy boundary rows/cols from initial (they never change under Dirichlet).
        for x in 0..nx { t_next[[0, x]] = cold; t_next[[ny-1, x]] = cold; }
        for y in 0..ny { t_next[[y, 0]] = cold; t_next[[y, nx-1]] = cold; }

        std::mem::swap(&mut t_cur, &mut t_next);

        if wanted_set.contains(&it) {
            snapshots.slice_mut(s![snap_idx, .., ..]).assign(&t_cur);
            snap_idx += 1;
        }
    }
    let elapsed = start.elapsed().as_secs_f64();

    let snapshot_iters_u64 = ndarray::Array1::from(wanted_iters);

    let (_file, group) = open_run_group(&cli.out)?;
    write_run(
        &group,
        &params,
        &RunData {
            variant: "serial",
            n_workers: 1,
            elapsed_seconds: elapsed,
            snapshots,
            snapshot_iters: snapshot_iters_u64,
        },
        cli.run_id.as_deref(),
    )?;

    eprintln!(
        "heatrs: nx={} ny={} nt={} dt={:.3e}s elapsed={:.4}s -> {}",
        cli.nx, cli.ny, params.nt, params.dt, elapsed, cli.out
    );
    Ok(())
}
