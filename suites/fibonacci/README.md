# Fibonacci

CPU-bound benchmark for function-call overhead, integer loops and `range` iteration.

| Case | Workload | `input.txt` | Expected output |
|---|---|---|---|
| `recursive_35` | naive recursive fib(n) | `35` | `9227465` |
| `recursive_40` | naive recursive fib(n) | `40` | `102334155` |
| `iterative_1m` | sum of fib(30 + k % 10) for k in 0..n | `1000000` | `16423387200000` |

`recursive_*` measures call overhead. `iterative_1m` runs about 34.5 million loop iterations of
integer addition. It has two Arx variants:

- `arx-while`: `while` loops only.
- `arx-range`: `for ... in range(...)`. `range` currently allocates a list on every call.

## Implementations

| Label | Source | Build and run | Optimization | Integer overflow |
|---|---|---|---|---|
| `arx`, `arx-while`, `arx-range` | `arx/*.x` | `arx <file> --output-file <bin>` | no IR passes (see below) | checked, raises |
| `c-O0`, `c-O2` | `c/fib.c` | `clang -O0` / `-O2` | as named | undefined behaviour (signed) |
| `c-O0-checked`, `c-O2-checked` | `c/fib.c` | `clang -DCHECKED` | as named | checked, exits 1 |
| `rust-O0`, `rust-O2` | `rust/fib.rs` | `rustc -C opt-level=0/2 -C overflow-checks=off` | as named | wraps (defined) |
| `rust-O0-checked`, `rust-O2-checked` | `rust/fib.rs` | `rustc ... -C overflow-checks=on` | as named | panics, exit 101 |
| `go` | `go/fib.go` | `go build` | always optimized, no level flag | wraps (defined) |
| `lua` | `lua/fib.lua` | `lua` (PUC-Rio 5.5, not LuaJIT) | interpreter | wraps (defined) |
| `java` | `java/Fib.java` | `javac`, then `java` | JIT, default flags | wraps (defined) |
| `java-checked` | `java/Fib.java` | `java -Dchecked=true` | JIT, default flags | `Math.addExact`/`subtractExact` |
| `julia` | `julia/fib.jl` | `julia --startup-file=no -O2` | JIT | wraps (defined) |
| `julia-checked` | `julia/fib.jl` | same, with `--checked` | JIT | `Base.Checked` |
| `numba` | `numba/fib.py` | `@njit` with explicit signature, `cache=False` | JIT | wraps |
| `python` | `python/fib.py` | CPython | interpreter | unbounded integers |

Checked variants cover the operations Arx checks: every `+`, `-` and loop increment.
Toolchain versions are recorded in `environment.json` for each run.

## Input

Every implementation reads `n` from a file named `input.txt` in its working directory. The harness
writes that file for each case and runs every implementation in that directory. No compiler can
therefore treat the workload size as a compile-time constant, and no implementation receives
information the others lack. `recursive_35` and `recursive_40` share one Arx source.

## Reproduce

Requirements: Python >= 3.11, Arx sources require Arx >= 1.28.0 `hyperfine`, `clang` and `arx` on `PATH`, plus the toolchains of the
languages being run. See the [top-level README](../../README.md#requirements). From the repository root:

```bash
python3 harness/bench.py list
python3 harness/bench.py check fibonacci
python3 harness/bench.py run fibonacci
python3 harness/bench.py report
python3 harness/bench.py report results/<run-dir>
```

Close other applications first and, on a laptop, use mains power with low-power mode off. If a
`stddev` is above about 5% of its median, rerun. Use `run fibonacci --quick` only as a smoke
test; its output goes to `build/quick-results/` and must not be published.

Each run writes to a new `results/<UTC timestamp>_<os>-<arch>_arx-<version>/` directory, so earlier
runs are never overwritten. A run is written to a hidden `.<name>.partial` directory and renamed
only after every case has succeeded, together with a `complete.json` marker. A failed or interrupted
run therefore leaves no result. To contribute results from another machine, run the commands above
and open a PR adding the new directory.

## Method

- Every implementation runs once before timing and must print the expected output. A mismatch
  aborts the run. This first run also absorbs the macOS first-launch check on freshly built binaries.
- Compiled executables are timed with hyperfine (`-N`, no shell) after warm-up runs; the number
  of runs is set per case in `benchmark.toml`. Compile time is excluded.
- Cases with short run times (`recursive_35`, `iterative_1m`) use 30 timed runs and 5 warm-up runs;
  `recursive_40` uses 5 runs. Medians are reported because single outlier runs inflate the standard
  deviation on cases under 100 ms.
- Each run also times an empty program per language (the start-up baseline). Reports show the
  baseline as `startup` and the median minus the baseline as `net`.
- `report` reads only complete runs and picks the latest one by the timestamp recorded in the run,
  not by directory name. `report <dir>` refuses a run without a completion marker.
- The tables show median, min and standard deviation of wall-clock time, peak memory as reported by
  hyperfine, and a ratio to the fastest implementation in that case.

## Fairness notes

**Implementation parity.** Every language implements the same algorithm with the same structure:
naive double recursion, and an iterative function with an explicit loop and accumulator that is
called once per iteration of an outer explicit counting loop accumulating a checksum. No
implementation uses library reductions (`sum`, generator expressions), vectorized APIs or
precomputed tables. Each language uses its idiomatic counted loop.

**Optimization.** Arx 1.28.0 (`fbd98b77`) runs no LLVM IR optimization passes on generated
code. `_build_from_ir` (`packages/irx/src/irx/builder/backend.py`, line 193) parses the IR
text and passes it directly to `emit_object`. The target machine is created without an `opt`
argument (`packages/irx/src/irx/builder/core.py`, lines 555-562), so llvmlite's default
code-generation level (`opt=2`, llvmlite 0.48.0) applies to instruction selection and register
allocation only. No pass-manager invocation exists in `packages/irx/src` or `packages/arx/src`. The
module emitted for `arx/recursive.x` contains 194 `alloca` and no `phi` instructions.
The `c-O0` and `c-O2` columns are reference points for unoptimized and optimized C, not bounds on
Arx's performance. Arx also pays for overflow checks and a status-code calling convention, which the
C references do not.

**Overflow and calling convention.** Arx checks every integer operation and raises on overflow
(`llvm.*.with.overflow` plus a branch to an exception path). Arx functions return a status code and
pass results through a pointer. Checked variants exist for C, Rust, Java and Julia. Go, Lua and Numba
have no built-in checked arithmetic and are compared unchecked. CPython integers cannot overflow.

| Implementation | Integer overflow |
|---|---|
| Arx | checked, raises |
| C (`-O0`, `-O2`) | signed overflow is undefined behaviour; the optimizer may assume it does not occur |
| Rust (`overflow-checks=off`), Go, Lua, Java, Julia | wraps (defined two's-complement behaviour) |
| Numba | wraps |
| `*-checked` variants | raise, panic or exit as listed in the Implementations table |
| Python | unbounded integers, nothing to overflow |

Because C signed overflow is undefined behaviour, optimized unchecked and checked C builds can
compile to different code, so their timings are not a pure measure of the cost of checking.

**JIT languages.** Java, Julia and Numba compile or warm up inside the timed process. The `startup`
column measures only an empty program, so `net` still contains JIT compilation. Numba also includes
its import time. Treat their `net` values as end-to-end process cost, not steady-state speed.

**Other.** Timings include process start-up. Results come from one machine, so compare ratios, not
absolute times, across machines.

## Results

<!-- results:start -->
<!-- results:end -->