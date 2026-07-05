import math
from dataclasses import dataclass, field

from .config import get_config


@dataclass(frozen=True)
class EquationParams:

#region Numerical parameters (varied for scaling experiments)

    nx: int
    """
    Number of grid points in the x-direction (length).
    """

    ny: int
    """
    Number of grid points in the y-direction (width).
    """

    t: float
    """
    Total simulation time [s].
    """

    cfl: float = field(default_factory=lambda: get_config().cfl)
    """
    CFL number (<= 1.0 for stability of the 2D explicit FTCS scheme).
    """

#endregion
#region Derived parameters

    dx: float = field(init=False)
    """
    Spatial step in the x-direction [lx/nx, m].
    """

    dy: float = field(init=False)
    """
    Spatial step in the y-direction [ly/ny, m].
    """

    dt: float = field(init=False)
    """
    Time step size [s]. Chosen so that `nt * dt == t` exactly, while staying
    at or under the stability-limited dt implied by `cfl`.
    """

    nt: int = field(init=False)
    """
    Number of time steps.
    """

#endregion
#region Physical parameters (shared across the whole experiment; see experiment.toml)

    alpha: float = field(default_factory=lambda: get_config().alpha)
    """
    Thermal diffusivity [m^2/s].
    """

    lx: float = field(default_factory=lambda: get_config().lx)
    """
    Physical length of the plate [m].
    """

    ly: float = field(default_factory=lambda: get_config().ly)
    """
    Physical width of the plate [m].
    """

#endregion

    def __post_init__(self):
        dx = self.lx / self.nx
        dy = self.ly / self.ny

        # 2D explicit FTCS stability requires:
        #   alpha * dt * (1/dx^2 + 1/dy^2) <= 1/2
        # i.e. dt <= dx^2 * dy^2 / (2 * alpha * (dx^2 + dy^2))
        dt_max = self.cfl * (dx**2 * dy**2) / (2 * self.alpha * (dx**2 + dy**2))

        # Round nt up so the simulation reaches exactly `t`, and shrink dt to
        # fit evenly into nt steps (dt <= dt_max is preserved by rounding up).
        nt = max(1, math.ceil(self.t / dt_max))
        dt = self.t / nt

        object.__setattr__(self, "dx", dx)
        object.__setattr__(self, "dy", dy)
        object.__setattr__(self, "dt", dt)
        object.__setattr__(self, "nt", nt)


@dataclass
class SolverParams:
    equation: EquationParams
    out: str
