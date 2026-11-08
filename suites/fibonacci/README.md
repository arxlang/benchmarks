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
| `c-O0`, `c-O2` | `c/fib.c` | `clang -O0` / `-O2` | as named | wraps (UB) |
| `c-O0-checked`, `c-O2-checked` | `c/fib.c` | `clang -DCHECKED` | as named | checked, exits 1 |
| `rust-O0`, `rust-O2` | `rust/fib.rs` | `rustc -C opt-level=0/2 -C overflow-checks=off` | as named | wraps |
| `rust-O0-checked`, `rust-O2-checked` | `rust/fib.rs` | `rustc ... -C overflow-checks=on` | as named | panics, exit 101 |
| `go` | `go/fib.go` | `go build` | always optimized, no level flag | wraps |
| `lua` | `lua/fib.lua` | `lua` (PUC-Rio 5.5, not LuaJIT) | interpreter | wraps |
| `java` | `java/Fib.java` | `javac`, then `java` | JIT, default flags | wraps |
| `java-checked` | `java/Fib.java` | `java -Dchecked=true` | JIT, default flags | `Math.addExact`/`subtractExact` |
| `julia` | `julia/fib.jl` | `julia --startup-file=no -O2` | JIT | wraps |
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

Requirements: Python >= 3.11, `hyperfine`, `clang` and `arx` on `PATH`. See the
[top-level README](../../README.md#requirements). From the repository root:

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
runs are never overwritten. To contribute results from another machine, run the commands above and
open a PR adding the new directory.

## Method

- Every implementation runs once before timing and must print the expected output. A mismatch
  aborts the run. This first run also absorbs the macOS first-launch check on freshly built binaries.
- Compiled executables are timed with hyperfine (`-N`, no shell) after warm-up runs; the number
  of runs is set per case in `benchmark.toml`. Compile time is excluded.
- Each run also times an empty program per language (the start-up baseline). Reports show the
  baseline as `startup` and the median minus the baseline as `net`.
- The tables show median, min and standard deviation of wall-clock time, peak memory as reported by
  hyperfine, and a ratio to the fastest implementation in that case.

## Fairness notes

**Optimization.** Arx 1.27.1 (`df5fa613`) runs no LLVM IR optimization passes on generated code.
`_build_from_ir` (`packages/irx/src/irx/builder/backend.py`, line 193) parses the IR text and passes
it directly to `emit_object`. The target machine is created without an `opt` argument
(`packages/irx/src/irx/builder/core.py`, lines 554-559), so llvmlite's default code-generation
level (`opt=2`, llvmlite 0.48.0) applies to instruction selection and register allocation only. No
pass-manager invocation exists in `packages/irx/src` or `packages/arx/src`. The module emitted for
`arx/recursive.x` contains 194 `alloca` and no `phi` instructions. The `c-O0` and `c-O2` columns
bracket Arx's current behaviour.

**Overflow and calling convention.** Arx checks every integer operation and raises on overflow
(`llvm.*.with.overflow` plus a branch to an exception path). Arx functions return a status code and
pass results through a pointer. Checked variants exist for C, Rust, Java and Julia. Go, Lua and Numba
have no built-in checked arithmetic and are compared unchecked. CPython integers cannot overflow.

**JIT languages.** Java, Julia and Numba compile or warm up inside the timed process. The `startup`
column measures only an empty program, so `net` still contains JIT compilation. Numba also includes
its import time. Treat their `net` values as end-to-end process cost, not steady-state speed.

**Other.** Timings include process start-up. Results come from one machine, so compare ratios, not
absolute times, across machines.

## Results

Reference run: `results/2026-11-05_darwin-arm64_arx-1.27.0/`

> Apple M1 | macOS 27.0.1 (arm64) | Arx 1.27.0 (`5ff7e9db`) | Apple clang 21.0.0 | hyperfine 2.0.0 | Python 3.14.10

Workload note: in this run the Arx programs contained `n` as a compile-time constant, while C and
Python read it from the command line. Runs made with the current harness read `n` from `input.txt`
in every language and are stored as later directories under [`results/`](../../results/).
Tables are generated with `python3 harness/bench.py report` from the raw JSON stored next to each
run's `environment.json`.

**iterative_1m**

| implementation | median (s) | min (s) | stddev (s) | memory (MiB) | vs fastest |
|---|---|---|---|---|---|
| arx-while | 0.1223 | 0.1209 | 0.0015 | 1.6 | 5.2x |
| arx-range | 1.3164 | 1.3073 | 0.0433 | 1.7 | 56.0x |
| c-O0 | 0.0861 | 0.0858 | 0.0007 | 1.5 | 3.7x |
| c-O2 | 0.0235 | 0.0229 | 0.0004 | 1.5 | 1.0x |
| python | 0.9460 | 0.9450 | 0.0146 | 9.6 | 40.2x |

**recursive_35**

| implementation | median (s) | min (s) | stddev (s) | memory (MiB) | vs fastest |
|---|---|---|---|---|---|
| arx | 0.0937 | 0.0930 | 0.0006 | 1.6 | 1.8x |
| c-O0 | 0.0853 | 0.0847 | 0.0018 | 1.5 | 1.7x |
| c-O2 | 0.0507 | 0.0497 | 0.0004 | 1.5 | 1.0x |
| python | 1.1426 | 1.1387 | 0.0280 | 9.6 | 22.5x |

**recursive_40**

| implementation | median (s) | min (s) | stddev (s) | memory (MiB) | vs fastest |
|---|---|---|---|---|---|
| arx | 0.9929 | 0.9905 | 0.0187 | 1.6 | 1.9x |
| c-O0 | 0.8980 | 0.8976 | 0.0218 | 1.5 | 1.8x |
| c-O2 | 0.5096 | 0.5085 | 0.0009 | 1.5 | 1.0x |
| python | 12.6159 | 12.5125 | 0.0849 | 9.7 | 24.8x |

### Observations

Ratios are computed from the medians above.

- **Recursion:** Arx is 1.1x slower than `c-O0` and 1.9x slower than `c-O2` on both
  `recursive_35` and `recursive_40`. It is 12.2x (fib 35) and 12.7x (fib 40) faster than CPython.
- **`arx-while`:** 1.4x slower than `c-O0`, 5.2x slower than `c-O2` and 7.7x faster than CPython.
- **`arx-range`:** 10.8x slower than `arx-while` and 1.4x slower than CPython, because `range`
  allocates a list on every call.
- **Memory:** peak memory is 1.5-1.7 MiB for Arx and C and 9.6-9.7 MiB for CPython.