use ndarray::Array2;

use crate::config::InitialCondition;
use crate::solver::EquationParams;

/// Build the initial temperature field per experiment.toml's [initial_condition].
/// Mirrors `rustpy_bench.core.ic.initial_field` bit-for-bit so Python and Rust
/// solvers start from the same state.
pub fn initial_field(params: &EquationParams, ic: &InitialCondition) -> Array2<f64> {
    let (ny, nx) = (params.ny, params.nx);
    let mut field = Array2::<f64>::from_elem((ny, nx), ic.cold_value);

    match ic.kind.as_str() {
        "hot_square" => {
            let hx = (((nx as f64) * ic.fraction) as usize).max(1);
            let hy = (((ny as f64) * ic.fraction) as usize).max(1);
            let x0 = (nx - hx) / 2;
            let y0 = (ny - hy) / 2;
            for y in y0..y0 + hy {
                for x in x0..x0 + hx {
                    field[[y, x]] = ic.hot_value;
                }
            }
        }
        "gaussian" => {
            let cx = params.lx / 2.0;
            let cy = params.ly / 2.0;
            let sigma = ic.fraction * params.lx.min(params.ly);
            let xdenom = ((nx.max(2) - 1) as f64).max(1.0);
            let ydenom = ((ny.max(2) - 1) as f64).max(1.0);
            for y in 0..ny {
                let yy = params.ly * (y as f64) / ydenom;
                for x in 0..nx {
                    let xx = params.lx * (x as f64) / xdenom;
                    let d2 = (xx - cx).powi(2) + (yy - cy).powi(2);
                    field[[y, x]] =
                        ic.cold_value + (ic.hot_value - ic.cold_value) * (-d2 / (2.0 * sigma.powi(2))).exp();
                }
            }
        }
        "uniform" => field.fill(ic.hot_value),
        other => panic!("Unknown initial_condition.kind: {other:?}"),
    }

    // Dirichlet boundary: held fixed at cold_value for the whole simulation.
    for x in 0..nx {
        field[[0, x]] = ic.cold_value;
        field[[ny - 1, x]] = ic.cold_value;
    }
    for y in 0..ny {
        field[[y, 0]] = ic.cold_value;
        field[[y, nx - 1]] = ic.cold_value;
    }

    field
}

/// Iteration indices to snapshot: 0 (initial), every `snapshot_every` steps
/// if > 0, and always the final step `nt` regardless of stride.
pub fn snapshot_iterations(nt: u64, snapshot_every: i64) -> Vec<u64> {
    let mut iters = vec![0u64];
    if snapshot_every > 0 {
        let stride = snapshot_every as u64;
        let mut it = stride;
        while it < nt {
            iters.push(it);
            it += stride;
        }
    }
    if *iters.last().unwrap() != nt {
        iters.push(nt);
    }
    iters
}
