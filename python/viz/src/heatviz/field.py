"""heatviz-field: render temperature-field snapshots as a GIF or static PNG.

The HDF5 target uses the same path#group syntax as the solvers:

  heatviz-field --h5 results/strong.h5#/strong/heatrs/nx512_ny512/cores1 --gif out.gif
  heatviz-field --h5 results/strong.h5#/strong/heatpy/nx512_ny512/cores1 --frame -1 --png last.png

By default the first run (run0 / lowest-numbered subgroup) in the addressed
group is used.  Override with --run <name>.

The GIF is created from the snapshot array stored in the HDF5 run group;
frame rate is proportional to simulation time so the animation is physically
meaningful regardless of how many snapshots were saved.
"""
import argparse, matplotlib, h5py, numpy as np

from pathlib import Path

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation, PillowWriter


def _resolve_run(group: h5py.Group, run_name: str | None) -> h5py.Group:
    keys = sorted(group.keys(), key=lambda k: int(k) if k.isdigit() else 0)
    if not keys:
        raise KeyError(f"No run subgroups found under {group.name!r}")
    name = run_name if run_name else keys[0]
    if name not in group:
        raise KeyError(f"Run '{name}' not found in {group.name!r}; available: {keys}")
    return group[name]  # type: ignore[return-value]


def _load(h5_spec: str, run_name: str | None) -> tuple[np.ndarray, np.ndarray, dict]:
    """Return (snapshots [n,ny,nx], snapshot_iters [n], attrs dict)."""
    if "#" in h5_spec:
        file_part, _, group_part = h5_spec.partition("#")
    else:
        file_part, group_part = h5_spec, "/"
    if not group_part.startswith("/"):
        group_part = "/" + group_part

    with h5py.File(file_part, "r") as f:
        g = f[group_part]
        run = _resolve_run(g, run_name)
        snaps = run["snapshots"][:]
        iters = run["snapshot_iters"][:]
        attrs = dict(run.attrs)
    return snaps, iters.astype(np.int64), attrs


def _colormap_kwargs(snaps: np.ndarray) -> dict:
    vmin, vmax = float(snaps.min()), float(snaps.max())
    return dict(cmap="hot", vmin=vmin, vmax=vmax, origin="lower", aspect="equal")


def render_gif(snaps: np.ndarray, iters: np.ndarray, attrs: dict, out_path: Path, fps: int = 15) -> None:
    dt   = float(attrs.get("dt", 1.0))
    nt   = int(attrs.get("nt", iters[-1]))
    lx   = float(attrs.get("lx", 1.0))
    ly   = float(attrs.get("ly", 1.0))
    nx   = int(attrs.get("nx", snaps.shape[2]))
    ny   = int(attrs.get("ny", snaps.shape[1]))
    var  = str(attrs.get("variant", ""))

    kw = _colormap_kwargs(snaps)
    fig, ax = plt.subplots(figsize=(5, 4), dpi=110)
    extent = [0, lx, 0, ly]
    im = ax.imshow(snaps[0], extent=extent, **kw)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Temperature")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    title = ax.set_title("")
    fig.tight_layout()

    def update(frame_idx: int):
        im.set_data(snaps[frame_idx])
        sim_t = iters[frame_idx] * dt
        title.set_text(
            f"{var} — nx={nx} ny={ny}  t={sim_t:.2f}s / {nt * dt:.2f}s  "
            f"(iter {iters[frame_idx]}/{nt})"
        )
        return im, title

    anim = FuncAnimation(fig, update, frames=len(snaps), interval=1000 // fps, blit=False)
    anim.save(str(out_path), writer=PillowWriter(fps=fps))
    plt.close(fig)
    print(f"  wrote {out_path}  ({len(snaps)} frames @ {fps} fps)")


def render_png(snaps: np.ndarray, iters: np.ndarray, attrs: dict, out_path: Path, frame: int) -> None:
    frame = frame % len(snaps)
    dt   = float(attrs.get("dt", 1.0))
    nt   = int(attrs.get("nt", iters[-1]))
    lx   = float(attrs.get("lx", 1.0))
    ly   = float(attrs.get("ly", 1.0))
    nx   = int(attrs.get("nx", snaps.shape[2]))
    ny   = int(attrs.get("ny", snaps.shape[1]))
    var  = str(attrs.get("variant", ""))

    kw = _colormap_kwargs(snaps)
    fig, ax = plt.subplots(figsize=(5, 4), dpi=150)
    extent = [0, lx, 0, ly]
    im = ax.imshow(snaps[frame], extent=extent, **kw)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Temperature")
    ax.set_xlabel("x [m]")
    ax.set_ylabel("y [m]")
    sim_t = iters[frame] * dt
    ax.set_title(
        f"{var} — nx={nx} ny={ny}\nt={sim_t:.2f}s / {nt * dt:.2f}s  "
        f"(iter {iters[frame]}/{nt})"
    )
    fig.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {out_path}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--h5",    required=True, help="path/to/file.h5#/group — addresses a run-collection group")
    p.add_argument("--run",   default=None,  help="Run subgroup name (default: first / run0)")
    p.add_argument("--gif",   default=None,  help="Output GIF path")
    p.add_argument("--png",   default=None,  help="Output PNG path (single frame)")
    p.add_argument("--frame", type=int, default=-1, help="Frame index for --png (-1 = last)")
    p.add_argument("--fps",   type=int, default=15, help="GIF frames per second")
    args = p.parse_args()

    if args.gif is None and args.png is None:
        p.error("Specify at least one of --gif or --png")

    snaps, iters, attrs = _load(args.h5, args.run)

    if args.gif:
        render_gif(snaps, iters, attrs, Path(args.gif), fps=args.fps)
    if args.png:
        render_png(snaps, iters, attrs, Path(args.png), frame=args.frame)
