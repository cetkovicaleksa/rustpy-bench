use crate::config::get_config;

#[derive(Debug, Clone, Copy)]
pub struct EquationParams {
    pub nx: usize,
    pub ny: usize,
    pub t: f64,
    pub cfl: f64,

    pub dx: f64,
    pub dy: f64,
    pub dt: f64,
    pub nt: u64,

    pub alpha: f64,
    pub lx: f64,
    pub ly: f64,
}

impl EquationParams {
    /// `cfl` defaults to experiment.toml's [equation].cfl when `None`.
    pub fn new(nx: usize, ny: usize, t: f64, cfl: Option<f64>) -> Self {
        let cfg = get_config();
        let cfl = cfl.unwrap_or(cfg.cfl);
        let (alpha, lx, ly) = (cfg.alpha, cfg.lx, cfg.ly);

        let dx = lx / nx as f64;
        let dy = ly / ny as f64;

        // 2D explicit FTCS stability requires:
        //   alpha * dt * (1/dx^2 + 1/dy^2) <= 1/2
        // i.e. dt <= dx^2 * dy^2 / (2 * alpha * (dx^2 + dy^2))
        let dt_max = cfl * (dx.powi(2) * dy.powi(2)) / (2.0 * alpha * (dx.powi(2) + dy.powi(2)));

        // Round nt up so the simulation reaches exactly `t`, and shrink dt to
        // fit evenly into nt steps (dt <= dt_max is preserved by rounding up).
        let nt = ((t / dt_max).ceil() as u64).max(1);
        let dt = t / nt as f64;

        EquationParams { nx, ny, t, cfl, dx, dy, dt, nt, alpha, lx, ly }
    }
}
