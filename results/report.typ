#set document(
  title: "A Comparative Benchmark: Python vs Rust on Numerical Solving of the 2-D Heat Equation",
  author: "Алекса Ћетковић",
)
#set page(paper: "us-letter", margin: (x: 2.5cm, y: 2.8cm), numbering: "1")
#set text(font: "Liberation Serif", size: 11pt, lang: "en", region: "GB")
#show math.equation: set text(font: "STIX Two Math")
#show raw: set text(font: "JetBrains Mono")
#set par(justify: true, leading: 0.68em)
#set heading(numbering: "1.1.")

#show heading.where(level: 1): it => {
  v(1em); text(weight: "bold", size: 13pt, it); v(0.4em)
}
#show heading.where(level: 2): it => {
  v(0.7em); text(weight: "bold", size: 11pt, it); v(0.25em)
}
#show figure: it => {
  v(0.5em)
  align(center, it.body)
  v(0.2em)
  align(center, text(size: 9.5pt, style: "italic", it.caption))
  v(0.5em)
}

// ── Title block ─────────────────────────────────────────────
#align(center)[
  #v(0.8cm)
  #text(size: 15pt, weight: "bold")[
    A Comparative Benchmark: Python versus Rust \
    on Numerical Solving of the 2-D Heat Equation
  ]
  #v(8cm)
]

// ════════════════════════════════════════════════════════════
= Problem and Numerical Method
// ════════════════════════════════════════════════════════════

The transient 2-D heat equation on a unit-square plate is:

$
  frac(partial T, partial t)
    = alpha (frac(partial^2 T, partial x^2) + frac(partial^2 T, partial y^2)),
  quad (x, y) in [0, 1]^2, quad t in [0, t_"end"]
$

with $alpha = 1.172 times 10^(-5)$ m²/s (thermal diffusivity of structural steel).
Boundary conditions are Dirichlet ($T = 0$ on all four edges, held fixed).
The initial condition is a centred hot square occupying 20 % of the plate ($T = 100$).

The equation is solved with the explicit forward-in-time, centred-in-space
(FTCS) finite-difference scheme:

$
  T_(i,j)^(n+1) = T_(i,j)^n
    + r_x (T_(i+1,j)^n - 2 T_(i,j)^n + T_(i-1,j)^n)
    + r_y (T_(i,j+1)^n - 2 T_(i,j)^n + T_(i,j-1)^n)
$

where $r_x = alpha Delta t \/ Delta x^2$ and $r_y = alpha Delta t \/ Delta y^2$.
The Von Neumann stability analysis requires
$alpha Delta t (Delta x^(-2) + Delta y^(-2)) <= 1\/2$,
giving the maximum stable time step:

$
  Delta t_"max" = frac(Delta x^2 dot Delta y^2,
                       2 alpha (Delta x^2 + Delta y^2))
$

A CFL factor $C = 0.5$ is applied so that $Delta t = C dot Delta t_"max"$.
The number of steps is $n_t = ceil(t_"end" \/ Delta t)$, rounded up so that
the simulation covers exactly $t_"end"$.

// ════════════════════════════════════════════════════════════
= System Details
// ════════════════════════════════════════════════════════════

#let env-data = csv("assets/env.csv")

#figure(
  table(
    columns: (auto, 1fr),
    stroke: 0.4pt, 
    inset: 6pt,
    
    // 1. Grab the first row and make the column headers bold
    ..env-data.at(0).map(header => [*#header*]),
    
    // 2. Loop through all remaining rows and add them to the table
    ..env-data.slice(1).flatten()
  ),
  caption: [Hardware and software environment.]
)

// Load both lockfiles
#let uv-lock = toml("../uv.lock")
#let cargo-lock = toml("../Cargo.lock")

// Define the major third-party libraries to extract
#let py-deps = ("numpy", "h5py", "typer")
#let rs-deps = ("ndarray", "hdf5", "clap", "anyhow", "serde", "toml")

#figure(
  grid(
    columns: (1fr, 1fr), // Splitting the layout exactly 50/50 side-by-side
    gutter: 20pt,       // Spacing between the two tables
    
    // Left Table: Python Dependencies
    table(
      columns: (auto, 1fr),
      stroke: 0.4pt, inset: 6pt,
      table.header([*Package*], [*Version*]),
      
      ..py-deps.map(dep-name => {
        let match = uv-lock.package.find(p => p.name == dep-name)
        let version = if match != none { match.version } else [Not found]
        (raw(dep-name), version)
      }).flatten()
    ),
    
    // Right Table: Rust Dependencies
    table(
      columns: (auto, 1fr),
      stroke: 0.4pt, inset: 6pt,
      table.header([*Crate*], [*Version*]),
      
      ..rs-deps.map(crate-name => {
        let match = cargo-lock.package.find(c => c.name == crate-name)
        let version = if match != none { match.version } else [Not found]
        (raw(crate-name), version)
      }).flatten()
    )
  ),
  caption: [Major third-party (direct) dependencies managed via uv and cargo. Versions for other dependencies may be viewed in project uv and cargo lockfiles.]
)

// ════════════════════════════════════════════════════════════
= Parallel Fraction and Theoretical Limits
// ════════════════════════════════════════════════════════════

== Sequential and Parallel Fractions

At each time step the only inherently sequential operations are re-pinning the
four Dirichlet boundary edges and inter-worker synchronisation.
All interior stencil updates are data-parallel.
For a grid of $n_x times n_y$ points:

$
  p_"ideal"
    = frac((n_x - 2)(n_y - 2), n_x n_y)
    = frac(510 times 510, 512 times 512)
    approx 0.9922
  quad arrow.r.double quad
  s_"ideal" = 1 - p approx 0.78 %
$

The sequential fraction consists of $2 n_x + 2 n_y - 4 = 2044$ boundary
assignments per step --- less than 0.8 % of the $262\,144$ total cell updates.

== Amdahl's Law --- Strong Scaling

For a fixed problem size, Amdahl's law @amdahl gives the theoretical speedup
achievable with $n$ workers:

$
  S_"Amdahl" (n) = frac(1, s + p\/n)
$

As $n -> infinity$, speedup is bounded by $S_"max" = 1\/s$.
Using the ideal parallel fraction:

$
  S_"max"^"ideal" = frac(1, 1 - 0.9922) = frac(1, 0.0078) approx 128
$

In practice, synchronisation overhead and memory-bandwidth contention reduce
the effective $p$ below 0.9922 (see @sec-strong-py and @sec-strong-rs).

== Gustafson's Law --- Weak Scaling

Gustafson's law @gustafson addresses weak scaling, where the per-worker
problem size is held constant while the number of workers grows.
The scaled speedup is:

$
  S_"Gustafson" (n) = p dot n + (1 - p)
$

Ideal weak scaling gives $S(n) = n$ (100 % efficiency).
The sequential fraction $s = 1 - p$ limits how closely this ideal can be reached.

// ════════════════════════════════════════════════════════════
= Implementations
// ════════════════════════════════════════════════════════════

All four variants produce numerically identical results: the maximum pairwise
difference in the final temperature field across all implementations and worker
counts is $2.8 times 10^(-14)$ (floating-point rounding noise).

- *`heatpy` (serial Python)* --- NumPy vectorised stencil via `numpy.roll`;
  Dirichlet boundary re-pinned after every step.

- *`heatpy-mp` (parallel Python)* --- Interior rows partitioned into
  contiguous bands, one per worker process.
  Workers share two complete frame buffers via
  `multiprocessing.shared_memory.SharedMemory`, so halo rows are read directly
  from shared memory without message passing.
  A single `multiprocessing.Barrier` per step synchronises all workers.

- *`heatrs` (serial Rust)* --- Explicit stencil loop with a pointer-swap
  double buffer (`std::mem::swap`); compiled with full optimisations
  (`--release`), enabling auto-vectorisation to SIMD instructions.

- *`heatrs-mt` (parallel Rust)* --- Row-band decomposition using
  `std::thread::scope` and two `Arc<UnsafeCell<Vec<f64>>>` double buffers.
  Two `std::sync::Barrier` instances per step --- one after the stencil
  compute and one after snapshotting --- guarantee race-freedom without a
  mutex on the shared buffer.

// ════════════════════════════════════════════════════════════
= Scaling Experiments
// ════════════════════════════════════════════════════════════

Each configuration was repeated 10 times; reported times cover only the solver
loop (file I/O excluded). Outliers are defined as runs deviating by more than
three standard deviations from the mean.

For weak scaling the grid grows as $n_x (n) = 256 sqrt(n)$,
$n_y (n) = 256 sqrt(n)$, so that work per worker is proportional to
$256^2 = 65\,536$ cells --- constant regardless of worker count.

#figure(
  table(
    columns: (auto, auto, auto),
    stroke: 0.4pt, inset: 5pt,
    [*Workers*], [*Grid*],           [*$n_t$*],
    [1],         [$256 times 256$],  [31],
    [2],         [$362 times 362$],  [62],
    [3],         [$443 times 443$],  [93],
    [4],         [$512 times 512$],  [123],
  ),
  caption: [
    Weak-scaling grid sizes. Total cells $approx 65\,536 times n_"workers"$.
  ]
)

== Strong Scaling --- Python <sec-strong-py>

#figure(
  image("assets/strong_python.png", width: 82%),
  caption: [
    Strong scaling of `heatpy-mp` relative to the serial `heatpy` baseline. \
    Grid: $512 times 512$, $t_"end" = 5$ s, $n_t = 123$. \
    Dashed blue line: Amdahl's law with empirically fitted $p = 0.2683$.
  ]
)

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    stroke: 0.4pt, inset: 5.5pt,
    align: (left, right, right, right, right),
    [*Workers*],          [*Mean (s)*], [*Std (s)*], [*Speedup*], [*Outliers*],
    [`heatpy` (serial)],  [0.6039],    [0.0185],    [1.000],     [0],
    [1 (`heatpy-mp`)],    [0.4532],    [0.0146],    [1.332],     [0],
    [2],                  [0.4888],    [0.0203],    [1.235],     [0],
    [3],                  [0.4987],    [0.0289],    [1.211],     [0],
    [4],                  [0.4983],    [0.0149],    [1.212],     [0],
  ),
  caption: [Strong-scaling results for Python. Speedup $= T_"serial" \/ T_n$.]
)

The parallel variant peaks at 1.33× with one worker and stabilises near 1.21×
for two to four workers.
The gain at one worker arises from a structural difference between the two
implementations: `heatpy` uses `numpy.roll`, which allocates a temporary array
on every call, whereas `heatpy-mp` operates on contiguous shared-memory row
slices without intermediate allocation.
Adding further workers yields no additional gain because the stencil is
memory-bandwidth-bound: the double buffer ($2 times 2$ MiB per frame) exceeds
the 3 MiB L3 cache, so each step is limited by DDR4 throughput rather than
compute. The two logical cores on each Skylake physical core share the same L3
and memory bus, which explains the flat speedup curve from two to four workers.

Fitting Amdahl's law to the measured values gives an effective parallel
fraction $p_"eff" = 0.2683$ and a theoretical maximum of
$S_"max" = 1 \/ (1 - 0.2683) approx 1.37 times$.
The gap from the ideal $p_"ideal" = 0.9922$ reflects the bandwidth bottleneck:
when workers contend for the same DDR4 channel, the parallelisable compute
fraction shrinks relative to memory-access stalls.

== Strong Scaling --- Rust <sec-strong-rs>

#figure(
  image("assets/strong_rust.png", width: 82%),
  caption: [
    Strong scaling of `heatrs-mt` relative to the serial `heatrs` baseline. \
    Same grid as above. \
    Dashed red line: Amdahl's law with empirically fitted $p = 0.0778$.
  ]
)

#figure(
  table(
    columns: (auto, auto, auto, auto, auto),
    stroke: 0.4pt, inset: 5.5pt,
    align: (left, right, right, right, right),
    [*Threads*],          [*Mean (s)*], [*Std (s)*], [*Speedup*], [*Outliers*],
    [`heatrs` (serial)],  [0.1473],    [0.0016],    [1.000],     [0],
    [2],                  [0.1392],    [0.0016],    [1.058],     [0],
    [3],                  [0.1390],    [0.0011],    [1.059],     [0],
    [4],                  [0.1408],    [0.0015],    [1.046],     [0],
  ),
  caption: [Strong-scaling results for Rust. Speedup $= T_"serial" \/ T_n$.]
)

The multi-threaded Rust solver achieves a peak of 1.06× at two to three
threads and degrades slightly at four.
Two factors explain the modest gain.
First, the serial solver at 0.147 s is already
$0.604 \/ 0.147 approx 4.1 times$ faster than the serial NumPy implementation,
leaving little absolute time to save.
Second, at this working-set size (4 MiB double buffer exceeding the 3 MiB L3
cache) the solver is bandwidth-bound, so adding threads does not reduce the
memory-access bottleneck.
The fitted effective parallel fraction $p_"eff" = 0.0778$ gives
$S_"max" = 1 \/ (1 - 0.0778) approx 1.08 times$,
consistent with the observed saturation beyond two threads.

== Weak Scaling --- Python

#figure(
  image("assets/weak_python.png", width: 82%),
  caption: [
    Weak scaling of `heatpy-mp`. \
    Scaled speedup $S(n) = n dot eta$ where $eta = T_1 \/ T_n$ is the parallel efficiency. \
    Dashed blue line: Gustafson's law with empirically fitted $p = 0.01$.
  ]
)

#figure(
  table(
    columns: (auto, auto, auto, auto, auto, auto),
    stroke: 0.4pt, inset: 5.5pt,
    align: (left, right, right, right, right, right),
    [*Workers*], [*Grid*],          [*Mean (s)*], [*Std (s)*], [*Efficiency $eta$*], [*Outliers*],
    [1],         [$256 times 256$], [0.0766],    [0.0070],    [1.000],             [0],
    [2],         [$362 times 362$], [0.1597],    [0.0083],    [0.480],             [0],
    [3],         [$443 times 443$], [0.2905],    [0.0165],    [0.264],             [0],
    [4],         [$512 times 512$], [0.4880],    [0.0087],    [0.157],             [0],
  ),
  caption: [Weak-scaling results for Python. Efficiency $eta = T_1 \/ T_n$.]
)

Parallel efficiency falls from 100 % at one worker to 15.7 % at four.
With constant work per worker and ideal hardware, execution time should remain
fixed at $T_1$ regardless of scale.
The observed growth in $T_n$ has two causes: the `multiprocessing.Barrier`
latency increases with participant count, and as the grid expands from
$256 times 256$ to $512 times 512$ the working set grows from roughly
0.5 MiB to 2 MiB per frame buffer, moving from L3-resident to DDR4-resident.
The Gustafson fit returns $p approx 0.01$, indicating that at these grid sizes
the overhead dominates the parallelisable compute on this hardware.

== Weak Scaling --- Rust

#figure(
  image("assets/weak_rust.png", width: 82%),
  caption: [
    Weak scaling of `heatrs-mt`. \
    Scaled speedup $S(n) = n dot eta$. \
    Dashed red line: Gustafson's law with empirically fitted $p = 0.01$.
  ]
)

#figure(
  table(
    columns: (auto, auto, auto, auto, auto, auto),
    stroke: 0.4pt, inset: 5.5pt,
    align: (left, right, right, right, right, right),
    [*Threads*], [*Grid*],          [*Mean (s)*], [*Std (s)*], [*Efficiency $eta$*], [*Outliers*],
    [1],         [$256 times 256$], [0.0089],    [0.0000],    [1.000],             [0],
    [2],         [$362 times 362$], [0.0355],    [0.0007],    [0.249],             [0],
    [3],         [$443 times 443$], [0.0791],    [0.0027],    [0.112],             [0],
    [4],         [$512 times 512$], [0.1385],    [0.0011],    [0.064],             [0],
  ),
  caption: [Weak-scaling results for Rust. Efficiency $eta = T_1 \/ T_n$.]
)

Rust weak-scaling efficiency falls more steeply still, reaching 6.4 % at four
threads.
The single-thread baseline is $0.0766 \/ 0.0089 approx 8.6 times$ faster than
the Python counterpart, so the two barrier crossings per step constitute a
proportionally larger share of total elapsed time: at four threads each thread
computes its band in under 2 ms per step, while barrier co-ordination takes
hundreds of microseconds.
The Gustafson fit again yields $p approx 0.01$, confirming that the Rust
solver is in a synchronisation-dominated regime at these grid sizes on this
hardware.

// ════════════════════════════════════════════════════════════
= Summary
// ════════════════════════════════════════════════════════════

#figure(
  table(
    columns: (1fr, auto, auto, auto, auto),
    stroke: 0.4pt, inset: 6pt,
    align: (left, right, right, right, right),
    [*Metric*],                    [*py serial*], [*py-mp (4)*], [*rs serial*], [*rs-mt (4)*],
    [Mean time (s)],               [0.6039],      [0.4983],      [0.1473],      [0.1408],
    [Speedup vs own serial],       [---],         [1.21×],       [---],         [1.05×],
    [Rust vs Python speedup],      [4.10×],       [2.36×],       [---],         [---],
    [Amdahl $p_"eff"$],            [---],         [0.2683],      [---],         [0.0778],
    [Amdahl $S_"max"$ (fitted)],   [---],         [1.37×],       [---],         [1.08×],
    [Amdahl $S_"max"$ (ideal)],    [---],         [128×],        [---],         [128×],
  ),
  caption: [
    Summary at the strong-scaling grid ($512 times 512$, $n_t = 123$).
  ]
)

The ideal parallel fraction of the FTCS stencil is
$p_"ideal" = 99.22$ %, giving a theoretical Amdahl limit of $128 times$ on
an infinite-core machine.
On this two-core / four-thread laptop the achieved speedup is $1.21 times$ (Python)
and $1.05 times$ (Rust), because the double-buffer working set exceeds the L3 cache
and the workload becomes bandwidth-bound rather than compute-bound.
Effective parallel fractions fitted from measurements
($p_"eff" = 0.27$ for Python, $0.08$ for Rust) reflect this bottleneck and
correctly predict the observed saturation beyond two workers.

The serial Rust solver is $4.1 times$ faster than serial NumPy on the same
problem, owing to auto-vectorised SIMD stencil code and zero-copy double-buffer
management.
Both languages parallelise the FTCS scheme correctly and produce results that
agree to floating-point precision.

#bibliography("report.bib", full: true)
