import os, math, tomllib

from dataclasses import dataclass
from pathlib import Path
from typing import Final

_CONFIG_ENV_VAR: Final[str] = "RUSTPY_BENCH_EXPERIMENT_TOML"
_CONFIG_FILENAME: Final[str] = "experiment.toml"


def find_config_path(start: Path | None = None) -> Path:
    """Locate experiment.toml, the single source of truth for shared params.

    Honors the RUSTPY_BENCH_EXPERIMENT_TOML environment variable as an
    explicit override; otherwise walks up from `start` (default: this file's
    location) looking for experiment.toml. Walking up means this works no
    matter what cwd a benchmark driver subprocess launches scripts from.
    """
    override = os.environ.get(_CONFIG_ENV_VAR)
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"{_CONFIG_ENV_VAR} points to a missing file: {path}")
        return path

    here = (start or Path(__file__)).resolve()
    for directory in (here, *here.parents):
        candidate = directory / _CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Could not locate {_CONFIG_FILENAME} above {here}; "
        f"set {_CONFIG_ENV_VAR} to override."
    )


@dataclass(frozen=True)
class InitialCondition:
    kind: str
    hot_value: float
    cold_value: float
    fraction: float


@dataclass(frozen=True)
class ScalingStrong:
    nx: int
    ny: int
    t: float
    cores: tuple[int, ...]


@dataclass(frozen=True)
class ScalingWeak:
    nx0: int
    ny0: int
    t: float
    cores: tuple[int, ...]

    def grid_for(self, n_cores: int) -> tuple[int, int]:
        """Grid size for `n_cores` keeping work-per-core ~constant.

        nx = ny = nx0 * sqrt(n_cores), rounded to the nearest int (>= 1).
        """
        scale = math.sqrt(n_cores)
        nx = max(1, round(self.nx0 * scale))
        ny = max(1, round(self.ny0 * scale))
        return nx, ny


@dataclass(frozen=True)
class Config:
    alpha: float
    lx: float
    ly: float
    cfl: float
    initial_condition: InitialCondition
    repetitions: int
    snapshot_every: int
    strong: ScalingStrong
    weak: ScalingWeak

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        cfg_path = path or find_config_path()
        with cfg_path.open("rb") as f:
            data = tomllib.load(f)

        eq = data["equation"]
        ic = data["initial_condition"]
        exp = data["experiment"]
        strong = data["scaling"]["strong"]
        weak = data["scaling"]["weak"]

        return cls(
            alpha=eq["alpha"],
            lx=eq["lx"],
            ly=eq["ly"],
            cfl=eq["cfl"],
            initial_condition=InitialCondition(**ic),
            repetitions=exp["repetitions"],
            snapshot_every=exp["snapshot_every"],
            strong=ScalingStrong(
                nx=strong["nx"], ny=strong["ny"], t=strong["t"],
                cores=tuple(strong["cores"]),
            ),
            weak=ScalingWeak(
                nx0=weak["nx0"], ny0=weak["ny0"], t=weak["t"],
                cores=tuple(weak["cores"]),
            ),
        )


_cached: Config | None = None


def get_config() -> Config:
    """Return the process-wide Config, loaded once from experiment.toml and cached."""
    global _cached
    if _cached is None:
        _cached = Config.load()
    return _cached
