import numpy as np

from .config import get_config
from .solver import EquationParams


def initial_field(params: EquationParams) -> np.ndarray:
    """Build the initial temperature field per experiment.toml's [initial_condition].

    Shared by every Python solver variant so they all start from bit-identical
    initial conditions -- required for cross-variant correctness comparisons.
    """
    cfg = get_config().initial_condition
    field = np.full((params.ny, params.nx), cfg.cold_value, dtype=np.float64)

    if cfg.kind == "hot_square":
        hx = max(1, int(params.nx * cfg.fraction))
        hy = max(1, int(params.ny * cfg.fraction))
        x0, y0 = (params.nx - hx) // 2, (params.ny - hy) // 2
        field[y0 : y0 + hy, x0 : x0 + hx] = cfg.hot_value
    elif cfg.kind == "gaussian":
        x = np.linspace(0, params.lx, params.nx)
        y = np.linspace(0, params.ly, params.ny)
        xx, yy = np.meshgrid(x, y)
        cx, cy = params.lx / 2, params.ly / 2
        sigma = cfg.fraction * min(params.lx, params.ly)
        field += (cfg.hot_value - cfg.cold_value) * np.exp(
            -((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma**2)
        )
    elif cfg.kind == "uniform":
        field[:] = cfg.hot_value
    else:
        raise ValueError(f"Unknown initial_condition.kind: {cfg.kind!r}")

    # Dirichlet boundary: held fixed at cold_value for the whole simulation.
    field[0, :] = field[-1, :] = field[:, 0] = field[:, -1] = cfg.cold_value
    return field


def snapshot_iterations(nt: int, snapshot_every: int) -> list[int]:
    """Iteration indices that get snapshotted: 0 (initial), every `snapshot_every`
    steps if > 0, and always the final step `nt` -- regardless of stride.
    """
    iters = [0]
    if snapshot_every > 0:
        iters.extend(it for it in range(snapshot_every, nt, snapshot_every))
    if iters[-1] != nt:
        iters.append(nt)
    return iters
