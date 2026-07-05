use std::path::PathBuf;
use std::str::FromStr;
use std::time::{SystemTime, UNIX_EPOCH};

use anyhow::Result;
use hdf5::types::VarLenUnicode;
use hdf5::{File as H5File, Group};
use ndarray::{Array1, Array3};

use crate::solver::EquationParams;

/// Split a `path/to/file.h5#/group/path` spec into (file_path, group_path).
/// Mirrors `rustpy_bench.core.io.parse_h5_target`.
pub fn parse_h5_target(spec: &str) -> (PathBuf, String) {
    match spec.split_once('#') {
        Some((file_part, group_part)) => {
            let group_part = if group_part.starts_with('/') {
                group_part.to_string()
            } else {
                format!("/{group_part}")
            };
            (PathBuf::from(file_part), group_part)
        }
        None => (PathBuf::from(spec), "/".to_string()),
    }
}

/// Open (creating parent dirs/groups as needed) the group addressed by `spec`.
/// Returns the open File too -- it must stay alive as long as `Group` is used.
pub fn open_run_group(spec: &str) -> Result<(H5File, Group)> {
    let (file_path, group_path) = parse_h5_target(spec);
    if let Some(parent) = file_path.parent() {
        if !parent.as_os_str().is_empty() {
            std::fs::create_dir_all(parent)?;
        }
    }
    let file = if file_path.exists() {
        H5File::append(&file_path)?
    } else {
        H5File::create(&file_path)?
    };
    let group = if group_path == "/" {
        file.group("/")?
    } else {
        match file.group(&group_path) {
            Ok(g) => g,
            Err(_) => file.create_group(&group_path)?,
        }
    };
    Ok((file, group))
}

pub struct RunData<'a> {
    pub variant: &'a str,
    pub n_workers: u32,
    pub elapsed_seconds: f64,
    /// shape (n_snapshots, ny, nx)
    pub snapshots: Array3<f64>,
    pub snapshot_iters: Array1<u64>,
}

/// Write one completed run into a fresh subgroup of `group`. Mirrors the
/// Python `write_run` schema exactly so both languages' output is readable
/// by the same visualization code.
pub fn write_run(
    group: &Group,
    params: &EquationParams,
    run: &RunData,
    run_id: Option<&str>,
) -> Result<Group> {
    let run_name = match run_id {
        Some(s) => s.to_string(),
        None => format!(
            "run_{}",
            SystemTime::now().duration_since(UNIX_EPOCH)?.as_micros()
        ),
    };
    let run_group = group.create_group(&run_name)?;

    run_group.new_attr::<i64>().create("nx")?.write_scalar(&(params.nx as i64))?;
    run_group.new_attr::<i64>().create("ny")?.write_scalar(&(params.ny as i64))?;
    run_group.new_attr::<f64>().create("t")?.write_scalar(&params.t)?;
    run_group.new_attr::<f64>().create("cfl")?.write_scalar(&params.cfl)?;
    run_group.new_attr::<f64>().create("dx")?.write_scalar(&params.dx)?;
    run_group.new_attr::<f64>().create("dy")?.write_scalar(&params.dy)?;
    run_group.new_attr::<f64>().create("dt")?.write_scalar(&params.dt)?;
    run_group.new_attr::<i64>().create("nt")?.write_scalar(&(params.nt as i64))?;
    run_group.new_attr::<f64>().create("alpha")?.write_scalar(&params.alpha)?;
    run_group.new_attr::<f64>().create("lx")?.write_scalar(&params.lx)?;
    run_group.new_attr::<f64>().create("ly")?.write_scalar(&params.ly)?;

    let variant: VarLenUnicode = VarLenUnicode::from_str(run.variant)?;
    run_group.new_attr::<VarLenUnicode>().create("variant")?.write_scalar(&variant)?;
    run_group.new_attr::<i64>().create("n_workers")?.write_scalar(&(run.n_workers as i64))?;
    run_group
        .new_attr::<f64>()
        .create("elapsed_seconds")?
        .write_scalar(&run.elapsed_seconds)?;

    let hostname: VarLenUnicode = VarLenUnicode::from_str(
        &hostname::get()
            .map(|h| h.to_string_lossy().to_string())
            .unwrap_or_else(|_| "unknown".to_string()),
    )?;
    run_group.new_attr::<VarLenUnicode>().create("hostname")?.write_scalar(&hostname)?;

    let timestamp = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs_f64();
    run_group.new_attr::<f64>().create("timestamp")?.write_scalar(&timestamp)?;

    run_group
        .new_dataset::<f64>()
        .deflate(4)
        .shape(run.snapshots.dim())
        .create("snapshots")?
        .write(&run.snapshots)?;

    let snapshot_iters_i64 = run.snapshot_iters.mapv(|v| v as i64);
    run_group
        .new_dataset::<i64>()
        .shape(snapshot_iters_i64.len())
        .create("snapshot_iters")?
        .write(&snapshot_iters_i64)?;

    Ok(run_group)
}
