# Arx benchmarks

Reproducible benchmarks for the [Arx](https://github.com/arxlang/arx) compiler. Each suite
implements the same workload in Arx, C (clang `-O0` and `-O2`), Rust, Go, Lua, Java, Julia, Numba
and CPython, verifies that all implementations print the same output, and times the compiled
executables with [hyperfine](https://github.com/sharkdp/hyperfine).

## Suites

| Suite | Measures | Results |
|---|---|---|
| [`fibonacci`](suites/fibonacci/README.md) | function calls, integer loops, `range` iteration | [`results/`](results/) |

## Quick start

```bash
python3 harness/bench.py list
python3 harness/bench.py check fibonacci     # build and verify outputs
python3 harness/bench.py run fibonacci       # verify, then time
python3 harness/bench.py report              # markdown tables from the latest complete run
```

## Requirements

- Python >= 3.11 (the harness uses `tomllib`)
- [hyperfine](https://github.com/sharkdp/hyperfine) (tested with 2.0.0)
- `clang` and `arx` on `PATH`. Arx >= 1.28.0 is required: the `.x` sources use the declaration
  syntax introduced in that release (`name: T = value`), and earlier releases do not parse it.
- Per-language toolchains: `rustc`, `go`, `lua`, `javac` and `java`, `julia`, and a Python with
  Numba (set `NUMBA_PYTHON` to its interpreter; default `~/.venvs/numba/bin/python`). Languages whose
  tools are missing are skipped; `--lang a,b` selects languages explicitly.
- Optional: `ARX_REPO=/path/to/arx` records the Arx git commit in the results

On macOS, put Apple's `/usr/bin/clang` first on `PATH`. In testing, a conda-provided clang failed
to link Arx output (`ld: -lto_library library filename must be 'libLTO.dylib'`). The harness warns
if it finds one. Tested on macOS arm64 only.

## Layout

| Path | Purpose |
|---|---|
| `suites/<name>/benchmark.toml` | Manifest: cases, inputs, expected output, run counts |
| `suites/<name>/<language>/` | One implementation per language |
| `suites/<name>/README.md` | What the suite measures, fairness notes, results |
| `harness/bench.py` | Generic runner with no benchmark-specific code |
| `harness/baselines/` | Empty programs used to measure per-language start-up |
| `results/<UTC timestamp>_<os>-<arch>_arx-<version>/` | Raw hyperfine JSON, `environment.json` and the `complete.json` marker |
| `build/` | Compiled binaries and quick runs (git-ignored) |

## Method

1. **Build.** Every implementation is built before any timing. Compile time is not measured.
2. **Verify.** Each implementation runs once and must print the case's `expected` output with
   exit code 0. Any mismatch aborts the run.
3. **Time.** hyperfine runs each executable directly (`-N`, no shell) after warm-up runs. An empty
   program per language is timed as the start-up baseline.
4. **Record.** Raw JSON and `environment.json` are written to a hidden `.<name>.partial` directory.
   Only if every case succeeded is `complete.json` added and the directory renamed to its final
   name. A failed or interrupted run leaves no result, and `report` ignores incomplete runs. The
   latest run is chosen by its recorded timestamp, not by directory name.

### Why these baselines

- **C with clang `-O0` / `-O2`:** Arx lowers to LLVM IR and links with clang, so C built by the same
  toolchain is the closest native reference. `-O0` and `-O2` are reference points for unoptimized
  and optimized code, not bounds on Arx's performance.
- **CPython:** Arx has Python-like syntax, so CPython is the natural interpreter reference.
- **Rust, Go, Lua, Java, Julia, Numba:** compiled, interpreted and JIT-compiled languages of
  different overheads, with overflow-checked variants where the language offers them. Build flags,
  optimization levels and overflow behaviour are listed in each suite's README.

## Results and reproducibility

- **Outputs** are deterministic and checked on every run.
- **Timings** depend on CPU, thermals, OS and background load, and are not reproducible across
  machines. Compare ratios, not absolute times, and compare runs only when their
  `environment.json` files are comparable.
- Every run directory contains `environment.json` (tool versions, CPU, OS, harness commit and
  whether the working tree was dirty) and `complete.json`. The tables in the suite READMEs are
  generated from the JSON next to them.

## Limitations

hyperfine measures whole-process wall-clock time. As a result:

- Process start-up is included, and individual phases cannot be timed inside a program.
- JIT compilation (Java, Julia, Numba) cannot be separated from steady-state execution.
- There are no hardware counters (instructions, cache or branch misses).
- There is no CPU pinning or frequency control.
- Statistics are descriptive (median, min, stddev); there is no regression detection across versions.

## Adding a benchmark

Create `suites/<name>/` with a manifest and one folder per language. The harness discovers it
automatically.

```toml
name = "mybench"
description = "What it measures"

[references]                    # optional; one source per language, run with the case's `args`
c = "c/mybench.c"               # keys: c, python, rust, go, lua, java, julia, numba
python = "python/mybench.py"

[[case]]
id = "small"
args = ["recursive"]            # passed to the references (Arx programs take none)
input = "100"                   # written to input.txt in the working directory of every implementation
expected = "42"                 # exact stdout, trimmed
runs = 10
warmup = 2
[case.arx]                      # label = source
arx = "arx/small.x"
```

Every implementation should read its size from `input.txt`, use the same algorithm and loop
structure, and avoid library shortcuts.

## Tests

Run the harness smoke tests from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

The suite uses only the Python standard library and a temporary directory; no language toolchains
are required. End-to-end `run` tests execute when `hyperfine` is on `PATH` and are skipped
otherwise. Set `REQUIRE_HYPERFINE=1` (as in CI) to fail instead of skipping when `hyperfine` is
missing.

## License

BSD-3-Clause, see [LICENSE](LICENSE).