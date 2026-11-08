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
- Cases with short run times (`recursive_35`, `iterative_1m`) use 30 timed runs and 5 warm-up runs;
  `recursive_40` uses 5 runs. Medians are reported because single outlier runs inflate the standard
  deviation on cases under 100 ms.

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

Run: `results/2026-11-08T002839Z_darwin-arm64_arx-1.27.1/`

> MacBook Air (Apple M1, 8 cores) | macOS 27.0.1 (arm64) | Arx 1.27.1 (`df5fa613`) | Apple clang 21.0.0 |
> rustc 1.99.1 | go 1.27.3 | Lua 5.5.1 | Java 25.0.1 | Julia 1.13.3 | Numba 0.68.1 (Python 3.14.10) |
> CPython 3.14.10 | hyperfine 2.0.0

The run used a clean working tree (`harness_dirty: false`). Every implementation read `n` from
`input.txt`. Tables are generated with `python3 harness/bench.py report` from the raw JSON stored
next to `environment.json`. `vs fastest (wall)` compares wall-clock medians within a case.

**iterative_1m**

| implementation | median (s) | min (s) | stddev (s) | memory (MiB) | startup (s) | net (s) | vs fastest (wall) |
|---|---|---|---|---|---|---|---|
| arx-while | 0.0801 | 0.0763 | 0.0067 | 1.6 | 0.0033 | 0.0767 | 6.7x |
| arx-range | 0.8819 | 0.8558 | 0.0267 | 1.7 | 0.0033 | 0.8786 | 73.4x |
| c-O0 | 0.0569 | 0.0553 | 0.0076 | 1.6 | 0.0029 | 0.0540 | 4.7x |
| c-O0-checked | 0.1377 | 0.1356 | 0.0115 | 1.6 | 0.0029 | 0.1348 | 11.5x |
| c-O2 | 0.0169 | 0.0156 | 0.0066 | 1.5 | 0.0029 | 0.0140 | 1.4x |
| c-O2-checked | 0.0120 | 0.0113 | 0.0006 | 1.5 | 0.0029 | 0.0091 | 1.0x |
| python | 0.6587 | 0.6352 | 0.0199 | 9.8 | 0.0172 | 0.6415 | 54.8x |
| rust-O0 | 0.0398 | 0.0383 | 0.0079 | 1.8 | 0.0034 | 0.0364 | 3.3x |
| rust-O0-checked | 0.0646 | 0.0623 | 0.0060 | 1.8 | 0.0034 | 0.0611 | 5.4x |
| rust-O2 | 0.0184 | 0.0169 | 0.0006 | 1.7 | 0.0032 | 0.0152 | 1.5x |
| rust-O2-checked | 0.0125 | 0.0116 | 0.0005 | 1.7 | 0.0032 | 0.0093 | 1.0x |
| go | 0.0198 | 0.0186 | 0.0068 | 4.1 | 0.0038 | 0.0160 | 1.7x |
| lua | 0.2482 | 0.2389 | 0.0121 | 1.9 | 0.0038 | 0.2444 | 20.7x |
| java | 0.0563 | 0.0533 | 0.0087 | 40.8 | 0.0385 | 0.0178 | 4.7x |
| java-checked | 0.0619 | 0.0580 | 0.0029 | 40.9 | 0.0385 | 0.0234 | 5.1x |
| julia | 0.1713 | 0.1623 | 0.0150 | 208.5 | 0.0974 | 0.0739 | 14.3x |
| julia-checked | 0.1783 | 0.1672 | 0.0176 | 208.4 | 0.0974 | 0.0809 | 14.8x |
| numba | 0.4093 | 0.3994 | 0.0179 | 114.8 | 0.1960 | 0.2133 | 34.1x |

**recursive_35**

| implementation | median (s) | min (s) | stddev (s) | memory (MiB) | startup (s) | net (s) | vs fastest (wall) |
|---|---|---|---|---|---|---|---|
| arx | 0.0609 | 0.0603 | 0.0007 | 1.6 | 0.0033 | 0.0575 | 1.8x |
| c-O0 | 0.0562 | 0.0547 | 0.0020 | 1.6 | 0.0029 | 0.0533 | 1.7x |
| c-O0-checked | 0.1067 | 0.1037 | 0.0044 | 1.6 | 0.0029 | 0.1038 | 3.2x |
| c-O2 | 0.0337 | 0.0324 | 0.0011 | 1.5 | 0.0029 | 0.0308 | 1.0x |
| c-O2-checked | 0.0407 | 0.0401 | 0.0006 | 1.5 | 0.0029 | 0.0378 | 1.2x |
| python | 0.7455 | 0.7271 | 0.0205 | 9.8 | 0.0172 | 0.7282 | 22.4x |
| rust-O0 | 0.0562 | 0.0552 | 0.0072 | 1.8 | 0.0034 | 0.0528 | 1.7x |
| rust-O0-checked | 0.0704 | 0.0697 | 0.0073 | 1.8 | 0.0034 | 0.0670 | 2.1x |
| rust-O2 | 0.0332 | 0.0326 | 0.0005 | 1.7 | 0.0032 | 0.0301 | 1.0x |
| rust-O2-checked | 0.0426 | 0.0416 | 0.0063 | 1.7 | 0.0032 | 0.0395 | 1.3x |
| go | 0.0367 | 0.0358 | 0.0011 | 4.1 | 0.0038 | 0.0329 | 1.1x |
| lua | 0.5539 | 0.5396 | 0.0178 | 1.9 | 0.0038 | 0.5501 | 16.7x |
| java | 0.0688 | 0.0664 | 0.0017 | 40.3 | 0.0385 | 0.0304 | 2.1x |
| java-checked | 0.0751 | 0.0739 | 0.0082 | 40.5 | 0.0385 | 0.0367 | 2.3x |
| julia | 0.2023 | 0.1901 | 0.0159 | 208.5 | 0.0974 | 0.1049 | 6.1x |
| julia-checked | 0.2065 | 0.1943 | 0.0212 | 208.3 | 0.0974 | 0.1090 | 6.2x |
| numba | 0.4366 | 0.4256 | 0.0239 | 114.9 | 0.1960 | 0.2406 | 13.1x |

**recursive_40**

| implementation | median (s) | min (s) | stddev (s) | memory (MiB) | startup (s) | net (s) | vs fastest (wall) |
|---|---|---|---|---|---|---|---|
| arx | 0.6681 | 0.6475 | 0.0158 | 1.6 | 0.0033 | 0.6648 | 2.0x |
| c-O0 | 0.5918 | 0.5789 | 0.0215 | 1.6 | 0.0029 | 0.5889 | 1.8x |
| c-O0-checked | 1.1277 | 1.1011 | 0.0321 | 1.6 | 0.0029 | 1.1248 | 3.4x |
| c-O2 | 0.3339 | 0.3256 | 0.0140 | 1.5 | 0.0029 | 0.3309 | 1.0x |
| c-O2-checked | 0.4227 | 0.4109 | 0.0185 | 1.5 | 0.0029 | 0.4197 | 1.3x |
| python | 8.4589 | 8.4465 | 0.0401 | 9.8 | 0.0172 | 8.4417 | 25.3x |
| rust-O0 | 0.5966 | 0.5754 | 0.0232 | 1.8 | 0.0034 | 0.5932 | 1.8x |
| rust-O0-checked | 0.7501 | 0.7404 | 0.0311 | 1.8 | 0.0034 | 0.7467 | 2.2x |
| rust-O2 | 0.3340 | 0.3308 | 0.0204 | 1.7 | 0.0032 | 0.3309 | 1.0x |
| rust-O2-checked | 0.4179 | 0.4137 | 0.0231 | 1.7 | 0.0032 | 0.4147 | 1.3x |
| go | 0.3826 | 0.3770 | 0.0187 | 4.1 | 0.0038 | 0.3788 | 1.1x |
| lua | 6.2422 | 6.2172 | 0.0212 | 1.9 | 0.0038 | 6.2384 | 18.7x |
| java | 0.3353 | 0.3335 | 0.0051 | 40.2 | 0.0385 | 0.2968 | 1.0x |
| java-checked | 0.3942 | 0.3921 | 0.0136 | 40.5 | 0.0385 | 0.3557 | 1.2x |
| julia | 0.6371 | 0.6170 | 0.0325 | 208.4 | 0.0974 | 0.5397 | 1.9x |
| julia-checked | 0.6485 | 0.6327 | 0.0182 | 208.4 | 0.0974 | 0.5511 | 1.9x |
| numba | 0.8725 | 0.8646 | 0.0283 | 115.0 | 0.1960 | 0.6765 | 2.6x |

### Observations

Ratios are computed from the medians above.

**Recursion (`recursive_40`, lowest noise)**

- Arx is 1.13x slower than `c-O0` and 2.0x slower than `c-O2`. It is 12.7x faster than CPython
  and 9.3x faster than Lua.
- `c-O2`, `rust-O2` and `java` are equal within 0.4% (0.334 s to 0.335 s). `go` is 1.15x slower.
  `julia` (0.637 s) and `numba` (0.873 s) include JIT compilation.
- Overflow checking costs 1.27x (`c-O2-checked`), 1.25x (`rust-O2-checked`) and 1.18x
  (`java-checked`) at full optimization, and 1.91x for `c-O0-checked`. Arx, which checks every
  operation, is 1.7x faster than `c-O0-checked`, 1.1x faster than `rust-O0-checked`, and 1.6x
  slower than the `-O2` checked builds.
- `recursive_35` shows the same picture: Arx is 1.08x slower than `c-O0`, 1.81x slower than
  `c-O2` and 12.2x faster than CPython.

**Loops (`iterative_1m`)**

- `arx-while` is 1.41x slower than `c-O0`, 4.7x slower than `c-O2`, 3.1x faster than Lua and
  8.2x faster than CPython. It is 1.4x slower than `java`.
- `arx-range` is 11.0x slower than `arx-while` and 1.34x slower than CPython, because `range`
  allocates a list on every call.
- At `-O2`, the checked C and Rust builds are faster than the unchecked builds (`c-O2-checked`
  0.0120 s against `c-O2` 0.0169 s; `rust-O2-checked` 0.0125 s against `rust-O2` 0.0184 s). The
  result repeated across three runs and two compilers. The cause has not been investigated, so
  it should not be read as "checking is free".

**Start-up and JIT**

- Empty-program start-up is about 3 ms for Arx, C, Rust, Go and Lua, 17 ms for CPython, 39 ms for
  Java, 97 ms for Julia and 196 ms for Numba. `net` subtracts this, but JIT compilation remains
  inside `net`.

**Memory**

- Peak resident memory is 1.5-1.8 MiB for Arx, C, Rust and Lua, 4.1 MiB for Go, 9.8 MiB for
  CPython, about 40 MiB for Java, about 115 MiB for Numba and about 208 MiB for Julia.

**Noise**

- `recursive_*` rows are mostly under 5% coefficient of variation. Some `iterative_1m` rows
  between 15 ms and 60 ms show 15-40% because of single outlier runs (for example `c-O2`: min
  15.6 ms, max 53 ms), so compare medians there. Start-up baselines of 3 ms show 9-22% on
  sub-millisecond absolute spread.
