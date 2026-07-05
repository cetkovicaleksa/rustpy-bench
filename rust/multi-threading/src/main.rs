//! 2D Heat Equation — parallel Rust solver using native threads.
//!
//! # Strategy: row-band decomposition + double-buffering + Barrier
//!
//! The grid's interior rows are split into contiguous bands, one per thread.
//! Each thread owns a slice of rows and works on a shared pair of `Arc<Mutex<…>>`
//! buffers — except we don't hold the mutex during computation; instead we use a
//! **double-buffer + barrier** scheme so each iteration is:
//!
//!   1. Every thread computes its row band into the "next" buffer from the
//!      "current" buffer.  Reads of halo rows (y-1, y+1) on boundaries are safe
//!      because only the owning thread writes those rows in the *next* buffer, and
//!      everyone reads only from the *current* buffer during this phase.
//!   2. Barrier.wait() — all threads have finished writing `next`.
//!   3. Thread 0 takes a snapshot if needed.
//!   4. Another Barrier.wait() — snapshot is done, `next` is now safe to be the
//!      new `current` (pointers are swapped via an atomic index).
//!   5. Repeat.
//!
//! The two frame buffers are stored as contiguous `Vec<f64>` (row-major, length
//! ny*nx) behind `Arc<UnsafeCell<…>>`.  Using `UnsafeCell` is sound here because:
//!   - Each thread writes only its own rows in the "next" buffer.
//!   - All reads are from the "current" buffer, which no thread writes during step 1.
//!   - The two barriers strictly order accesses.

use std::cell::UnsafeCell;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Barrier};
use std::thread;
use std::time::Instant;

use anyhow::Result;
use clap::Parser;
use ndarray::{Array2, Array3, s};
use rustpy_bench_core::{
    config::get_config,
    ic::{initial_field, snapshot_iterations},
    io::{open_run_group, write_run, RunData},
    solver::EquationParams,
};

// Safety wrapper so we can share raw slice pointers across threads.
struct SyncCell<T>(UnsafeCell<T>);
unsafe impl<T: Send> Sync for SyncCell<T> {}

#[derive(Parser)]
#[command(name = "heatrs-mt", about = "Multi-threaded Rust FTCS solver for the 2D heat equation")]
struct Cli {
    #[arg(long)] nx: usize,
    #[arg(long)] ny: usize,
    #[arg(long)] t: f64,
    #[arg(long, help = "HDF5 target: path/to/file.h5#/group/path")] out: String,
    #[arg(long)] threads: usize,
    #[arg(long)] cfl: Option<f64>,
    #[arg(long)] snapshot_every: Option<i64>,
    #[arg(long)] run_id: Option<String>,
}

fn partition_rows(n_interior: usize, n_threads: usize) -> Vec<(usize, usize)> {
    let n_threads = n_threads.min(n_interior.max(1));
    let base = n_interior / n_threads;
    let rem = n_interior % n_threads;
    let mut ranges = Vec::with_capacity(n_threads);
    let mut row = 1usize; // first interior row (global index)
    for w in 0..n_threads {
        let size = base + if w < rem { 1 } else { 0 };
        if size > 0 {
            ranges.push((row, row + size));
            row += size;
        }
    }
    ranges
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let cfg = get_config();

    let params = EquationParams::new(cli.nx, cli.ny, cli.t, cli.cfl);
    let snap_every = cli.snapshot_every.unwrap_or(cfg.snapshot_every);
    let wanted_iters = snapshot_iterations(params.nt, snap_every);
    let cold = cfg.initial_condition.cold_value;
    let (ny, nx) = (params.ny, params.nx);
    let rx = params.alpha * params.dt / params.dx.powi(2);
    let ry = params.alpha * params.dt / params.dy.powi(2);

    // Allocate both buffers and initialise them to the IC.
    let t0: Array2<f64> = initial_field(&params, &cfg.initial_condition);
    let flat0: Vec<f64> = t0.as_slice().unwrap().to_vec();
    let buf_a = Arc::new(SyncCell(UnsafeCell::new(flat0.clone())));
    let buf_b = Arc::new(SyncCell(UnsafeCell::new(flat0)));

    // `cur_idx` 0 → buf_a is current, 1 → buf_b is current.
    let cur_idx = Arc::new(AtomicUsize::new(0));

    let n_snaps = wanted_iters.len();
    let snapshots_out = Arc::new(SyncCell(UnsafeCell::new(
        Array3::<f64>::zeros((n_snaps, ny, nx)),
    )));
    // Write iteration 0 (initial field).
    {
        let out = unsafe { &mut *snapshots_out.0.get() };
        out.slice_mut(s![0, .., ..]).assign(&t0);
    }

    let wanted_set: Arc<std::collections::HashSet<u64>> =
        Arc::new(wanted_iters.iter().copied().collect());
    let wanted_iters_arc = Arc::new(wanted_iters.clone());

    let row_ranges = partition_rows(ny - 2, cli.threads);
    let n_workers = row_ranges.len();

    // Two barriers: one after compute, one after snapshot.
    let bar_compute = Arc::new(Barrier::new(n_workers));
    let bar_snapshot = Arc::new(Barrier::new(n_workers));

    let start = Instant::now();
    thread::scope(|scope| {
        for (wid, (y0, y1)) in row_ranges.iter().enumerate() {
            let (y0, y1) = (*y0, *y1);
            let buf_a = Arc::clone(&buf_a);
            let buf_b = Arc::clone(&buf_b);
            let cur_idx = Arc::clone(&cur_idx);
            let bar_compute = Arc::clone(&bar_compute);
            let bar_snapshot = Arc::clone(&bar_snapshot);
            let wanted_set = Arc::clone(&wanted_set);
            let wanted_iters_arc = Arc::clone(&wanted_iters_arc);
            let snapshots_out = Arc::clone(&snapshots_out);

            scope.spawn(move || {
                let mut snap_idx = 1usize;

                for it in 1..=params.nt {
                    // Determine which buffer is current and which is next.
                    let ci = cur_idx.load(Ordering::Acquire);
                    let (cur_raw, nxt_raw) = if ci == 0 {
                        (buf_a.0.get(), buf_b.0.get())
                    } else {
                        (buf_b.0.get(), buf_a.0.get())
                    };

                    // SAFETY: Each thread writes only rows y0..y1 in `nxt_raw`.
                    // All threads read from `cur_raw` which no one writes this
                    // iteration. Barriers below order all accesses.
                    unsafe {
                        let cur = &*cur_raw;
                        let nxt = &mut *nxt_raw;
                        for y in y0..y1 {
                            for x in 1..nx - 1 {
                                let i   = y * nx + x;
                                let lap_x = cur[i + 1] - 2.0 * cur[i] + cur[i - 1];
                                let lap_y = cur[i + nx] - 2.0 * cur[i] + cur[i - nx];
                                nxt[i] = cur[i] + rx * lap_x + ry * lap_y;
                            }
                            // Re-pin left/right Dirichlet columns.
                            nxt[y * nx]          = cold;
                            nxt[y * nx + nx - 1] = cold;
                        }
                    }

                    bar_compute.wait(); // All threads done writing `nxt_raw`.

                    if wid == 0 {
                        // Swap: next becomes current.
                        cur_idx.store(ci ^ 1, Ordering::Release);

                        // Snapshot from the (now-current) buffer.
                        if wanted_set.contains(&it) {
                            let new_ci = ci ^ 1;
                            let cur_raw = if new_ci == 0 { buf_a.0.get() } else { buf_b.0.get() };
                            unsafe {
                                let cur = &*cur_raw;
                                let out = &mut *snapshots_out.0.get();
                                // Flatten into the snapshots array.
                                let mut row_out = out.slice_mut(s![snap_idx, .., ..]);
                                for y in 0..ny {
                                    for x in 0..nx {
                                        row_out[[y, x]] = cur[y * nx + x];
                                    }
                                }
                            }
                            snap_idx += 1;
                        }
                    }

                    bar_snapshot.wait(); // Snapshot done; next iteration may begin.
                    let _ = &wanted_iters_arc; // keep arc alive
                }
            });
        }
    });
    let elapsed = start.elapsed().as_secs_f64();

    // Extract snapshots from the Arc (only reference left).
    let snapshots = Arc::try_unwrap(snapshots_out)
        .ok().expect("arc not unique")
        .0
        .into_inner();

    let (_file, group) = open_run_group(&cli.out)?;
    write_run(
        &group,
        &params,
        &RunData {
            variant: "multi-threading",
            n_workers: n_workers as u32,
            elapsed_seconds: elapsed,
            snapshots,
            snapshot_iters: ndarray::Array1::from(wanted_iters),
        },
        cli.run_id.as_deref(),
    )?;

    eprintln!(
        "heatrs-mt: nx={} ny={} nt={} threads={} elapsed={:.4}s -> {}",
        cli.nx, cli.ny, params.nt, n_workers, elapsed, cli.out
    );
    Ok(())
}
