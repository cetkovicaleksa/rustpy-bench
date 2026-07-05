"""heatviz-scaling: render the 4 required scaling plots + supporting tables.

Usage
-----
  heatviz-scaling --strong results/strong.h5 --weak results/weak.h5 --out-dir results/

Produces (in --out-dir):
  strong_python.png/pdf   — Python strong scaling (Amdahl)
  strong_rust.png/pdf     — Rust strong scaling (Amdahl)
  weak_python.png/pdf     — Python weak scaling (Gustafson)
  weak_rust.png/pdf       — Rust weak scaling (Gustafson)
  scaling_tables.txt      — Plain-text tables for the report
"""
import sys, math, argparse, matplotlib, numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from pathlib import Path

from .reader import RunStats, load, speedup_table

# Parallel fraction used for the theoretical Amdahl/Gustafson lines.
# We derive this from the data automatically (see _estimate_parallel_fraction).
_FALLBACK_P = 0.95


# ---------------------------------------------------------------------------
# Theory lines
# ---------------------------------------------------------------------------

def amdahl_speedup(p: float, cores: np.ndarray) -> np.ndarray:
    """S(n) = 1 / ((1-p) + p/n)"""
    return 1.0 / ((1.0 - p) + p / cores)


def gustafson_speedup(p: float, cores: np.ndarray) -> np.ndarray:
    """S(n) = n - (1-p)*(n-1)  (scaled problem)"""
    return cores - (1.0 - p) * (cores - 1.0)


def _estimate_parallel_fraction(table: dict[int, tuple[float, float, float]]) -> float:
    """Fit p from measured speedup at the largest core count via Amdahl's law."""
    if not table:
        return _FALLBACK_P
    n_max = max(table)
    if n_max <= 1:
        return _FALLBACK_P
    S = table[n_max][0]
    # S = 1/((1-p) + p/n)  →  p = (1/S - 1) / (1/n - 1)
    try:
        p = (1.0 / S - 1.0) / (1.0 / n_max - 1.0)
        return float(np.clip(p, 0.5, 1.0))
    except ZeroDivisionError:
        return _FALLBACK_P


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------

STYLE = {
    "figure.dpi": 150,
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.35,
    "axes.labelsize": 11,
    "legend.fontsize": 9,
}


def _plot_scaling(
    ax: plt.Axes,
    table: dict[int, tuple[float, float, float]],
    label: str,
    theory_fn,
    color: str,
    kind: str,
) -> None:
    cores_arr = np.array(sorted(table))
    speedups = np.array([table[c][0] for c in cores_arr])
    lo       = np.array([table[c][1] for c in cores_arr])
    hi       = np.array([table[c][2] for c in cores_arr])

    p = _estimate_parallel_fraction(table)
    cores_theory = np.linspace(1, cores_arr.max() * 1.05, 300)
    theory = theory_fn(p, cores_theory)
    ideal  = cores_theory if kind == "strong" else gustafson_speedup(1.0, cores_theory)

    ax.plot(cores_theory, ideal,   "k--", lw=1.2, label="Ideal (p=1)", zorder=1)
    ax.plot(cores_theory, theory,  "--",  lw=1.2, color=color, alpha=0.65,
            label=f"Amdahl p={p:.3f}" if kind == "strong" else f"Gustafson p={p:.3f}", zorder=2)
    ax.fill_between(cores_arr, lo, hi, color=color, alpha=0.15, zorder=3)
    ax.plot(cores_arr, speedups, "o-", color=color, lw=2, ms=6, label=label, zorder=4)


def _finish_ax(ax: plt.Axes, title: str, kind: str, max_cores: int) -> None:
    ax.set_title(title, fontsize=12, pad=8)
    ax.set_xlabel("CPU cores / threads")
    ax.set_ylabel("Speedup S(n)")
    ax.set_xlim(0.5, max_cores * 1.1)
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.legend(loc="upper left")


def _save(fig: plt.Figure, stem: str, out_dir: Path) -> None:
    for ext in ["svg"]:
        p = out_dir / f"{stem}.{ext}"
        fig.savefig(p, bbox_inches="tight")
        print(f"  wrote {p}")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def _table_lines(
    stats: list[RunStats],
    kind: str,
    baseline_v: str,
    parallel_v: str,
    label: str,
) -> list[str]:
    lines = [f"\n{label} ({kind} scaling)"]
    lines.append("-" * 72)
    try:
        table = speedup_table(stats, baseline_v, parallel_v)
    except ValueError as e:
        lines.append(f"  No data: {e}")
        return lines

    lines.append(f"  {'cores':>6}  {'mean_t (s)':>12}  {'std (s)':>10}  "
                 f"{'speedup':>9}  {'outliers':>8}")
    for s in sorted((x for x in stats if x.variant == parallel_v), key=lambda x: x.cores):
        sp_info = table.get(s.cores, (float("nan"), 0, 0))
        sp = sp_info[0]
        # Outliers: runs > mean + 3*std or < mean - 3*std
        if len(s.times) > 1:
            z = np.abs(s.times - s.mean) / (s.std + 1e-12)
            n_out = int((z > 3).sum())
        else:
            n_out = 0
        lines.append(
            f"  {s.cores:>6}  {s.mean:>12.4f}  {s.std:>10.4f}  {sp:>9.4f}  {n_out:>8}"
        )
    return lines


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PAIRS = {
    "python": {
        "serial":   "heatpy",
        "parallel": "heatpy-mp",
        "color":    "#2196F3",
    },
    "rust": {
        "serial":   "heatrs",
        "parallel": "heatrs-mt",
        "color":    "#F44336",
    },
}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--strong",  required=True, help="HDF5 file from strong_scaling.py")
    p.add_argument("--weak",    required=True, help="HDF5 file from weak_scaling.py")
    p.add_argument("--out-dir", default=".",   help="Directory to write plots + tables into")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    strong_stats = load(args.strong, "strong")
    weak_stats   = load(args.weak,   "weak")

    table_lines: list[str] = ["=" * 72, "Scaling Results Summary", "=" * 72]

    with plt.style.context(STYLE):
        for lang, cfg in PAIRS.items():
            serial_v   = cfg["serial"]
            parallel_v = cfg["parallel"]
            color      = cfg["color"]

            # ---- Strong scaling ----
            try:
                s_table = speedup_table(strong_stats, serial_v, parallel_v)
            except ValueError as e:
                print(f"  [skip strong {lang}]: {e}", file=sys.stderr)
                s_table = {}
            if s_table:
                max_cores = max(s_table)
                fig, ax = plt.subplots(figsize=(6, 4))
                _plot_scaling(ax, s_table, parallel_v, amdahl_speedup, color, "strong")
                _finish_ax(ax, f"Strong Scaling — {lang.capitalize()} ({parallel_v})", "strong", max_cores)
                _save(fig, f"strong_{lang}", out_dir)

            table_lines += _table_lines(strong_stats, "strong", serial_v, parallel_v,
                                        f"{lang.capitalize()} parallel ({parallel_v})")

            # ---- Weak scaling ----
            try:
                w_table = speedup_table(weak_stats, serial_v, parallel_v)
            except ValueError as e:
                print(f"  [skip weak {lang}]: {e}", file=sys.stderr)
                w_table = {}
            if w_table:
                max_cores = max(w_table)
                fig, ax = plt.subplots(figsize=(6, 4))
                _plot_scaling(ax, w_table, parallel_v, gustafson_speedup, color, "weak")
                _finish_ax(ax, f"Weak Scaling — {lang.capitalize()} ({parallel_v})", "weak", max_cores)
                _save(fig, f"weak_{lang}", out_dir)

            table_lines += _table_lines(weak_stats, "weak", serial_v, parallel_v,
                                        f"{lang.capitalize()} parallel ({parallel_v})")

    table_path = out_dir / "scaling_tables.txt"
    table_path.write_text("\n".join(table_lines) + "\n")
    print(f"  wrote {table_path}")
