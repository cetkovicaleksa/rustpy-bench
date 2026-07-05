use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use anyhow::{Context, Result};
use serde::Deserialize;

const CONFIG_ENV_VAR: &str = "RUSTPY_BENCH_EXPERIMENT_TOML";
const CONFIG_FILENAME: &str = "experiment.toml";

#[derive(Debug, Deserialize, Clone)]
pub struct InitialCondition {
    pub kind: String,
    pub hot_value: f64,
    pub cold_value: f64,
    pub fraction: f64,
}

#[derive(Debug, Deserialize, Clone)]
pub struct ScalingStrong {
    pub nx: usize,
    pub ny: usize,
    pub t: f64,
    pub cores: Vec<usize>,
}

#[derive(Debug, Deserialize, Clone)]
pub struct ScalingWeak {
    pub nx0: usize,
    pub ny0: usize,
    pub t: f64,
    pub cores: Vec<usize>,
}

impl ScalingWeak {
    /// Grid size for `n_cores` that keeps work-per-core ~constant:
    /// nx = ny = nx0 * sqrt(n_cores), rounded (mirrors the Python `grid_for`).
    pub fn grid_for(&self, n_cores: usize) -> (usize, usize) {
        let scale = (n_cores as f64).sqrt();
        let nx = ((self.nx0 as f64) * scale).round().max(1.0) as usize;
        let ny = ((self.ny0 as f64) * scale).round().max(1.0) as usize;
        (nx, ny)
    }
}

#[derive(Debug, Deserialize)]
struct RawEquation {
    alpha: f64,
    lx: f64,
    ly: f64,
    cfl: f64,
}

#[derive(Debug, Deserialize)]
struct RawExperiment {
    repetitions: u32,
    snapshot_every: i64,
}

#[derive(Debug, Deserialize)]
struct RawScaling {
    strong: ScalingStrong,
    weak: ScalingWeak,
}

#[derive(Debug, Deserialize)]
struct RawConfig {
    equation: RawEquation,
    initial_condition: InitialCondition,
    experiment: RawExperiment,
    scaling: RawScaling,
}

#[derive(Debug, Clone)]
pub struct Config {
    pub alpha: f64,
    pub lx: f64,
    pub ly: f64,
    pub cfl: f64,
    pub initial_condition: InitialCondition,
    pub repetitions: u32,
    pub snapshot_every: i64,
    pub strong: ScalingStrong,
    pub weak: ScalingWeak,
}

/// Locate experiment.toml: honors RUSTPY_BENCH_EXPERIMENT_TOML as an
/// override, otherwise walks up from the running executable's directory
/// (falling back to cwd) -- the same two strategies the Python loader uses,
/// so a benchmark driver can launch either implementation from any cwd.
pub fn find_config_path() -> Result<PathBuf> {
    if let Ok(over) = std::env::var(CONFIG_ENV_VAR) {
        let path = PathBuf::from(over);
        if path.is_file() {
            return Ok(path);
        }
        anyhow::bail!("{CONFIG_ENV_VAR} points to a missing file: {}", path.display());
    }

    let starts: Vec<PathBuf> = [std::env::current_exe().ok(), std::env::current_dir().ok()]
        .into_iter()
        .flatten()
        .collect();

    for start in &starts {
        if let Some(found) = walk_up(start) {
            return Ok(found);
        }
    }

    anyhow::bail!(
        "Could not locate {CONFIG_FILENAME} above {:?}; set {CONFIG_ENV_VAR} to override.",
        starts
    )
}

fn walk_up(start: &Path) -> Option<PathBuf> {
    let mut dir = if start.is_file() { start.parent()? } else { start };
    loop {
        let candidate = dir.join(CONFIG_FILENAME);
        if candidate.is_file() {
            return Some(candidate);
        }
        dir = dir.parent()?;
    }
}

impl Config {
    pub fn load() -> Result<Config> {
        let path = find_config_path()?;
        let text = std::fs::read_to_string(&path)
            .with_context(|| format!("reading {}", path.display()))?;
        let raw: RawConfig =
            toml::from_str(&text).with_context(|| format!("parsing {}", path.display()))?;

        Ok(Config {
            alpha: raw.equation.alpha,
            lx: raw.equation.lx,
            ly: raw.equation.ly,
            cfl: raw.equation.cfl,
            initial_condition: raw.initial_condition,
            repetitions: raw.experiment.repetitions,
            snapshot_every: raw.experiment.snapshot_every,
            strong: raw.scaling.strong,
            weak: raw.scaling.weak,
        })
    }
}

static CACHED: OnceLock<Config> = OnceLock::new();

/// Process-wide Config, loaded once from experiment.toml and cached.
/// Panics if experiment.toml cannot be found/parsed (mirrors a hard
/// startup-time failure, same as the Python side raising on import).
pub fn get_config() -> &'static Config {
    CACHED.get_or_init(|| Config::load().expect("failed to load experiment.toml"))
}
