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

Requirements: Python >= 3.11, `hyperfine`, `clang` and `arx` (>= 1.28.0; the Arx sources use its declaration syntax) on `PATH`, plus the toolchains of the languages being run. See the
[top-level README](../../README.md#requirements). From the repository root:

```bash
python3 harness/bench.py list
python3 harness/bench.py check fibonacci
python3 harness/bench.py run fibonacci
python3 harness/bench.py report
python3 harness/bench.py report results/<run-dir>
```

Close other applications first and, on a laptop, use mains power with low-power mode off. For `recursive_40`, rerun if a `stddev` is above about 5% of its median. For cases under 100 ms,
single outlier runs inflate the standard deviation, so compare medians. Use `run fibonacci --quick` only as a smoke
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
C references do not. The commit is one after the 1.28.0 tag.

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

Run: `results/2026-11-09T211943Z_darwin-arm64_arx-1.28.0/`

> Apple M1 | macOS-27.0.1-arm64-arm-64bit-Mach-O | arx 1.28.0 fbd98b77 | Apple clang version 21.0.0 (clang-2100.3.34.2) | hyperfine 2.0.0 | Python 3.14.10 | arx: 1.28.0, c: Apple clang version 21.0.0 (clang-2100.3.34.2), python: Python 3.14.10, rust: rustc 1.99.1 (58cf8f9c3 2026-10-13) (Homebrew), go: go version go1.27.3 darwin/arm64, lua: Lua 5.5.1  Copyright (C) 1994-2026 Lua.org, PUC-Rio, java: java version "25.0.1" 2025-10-21 LTS, julia: julia version 1.13.3, numba: numba 0.68.1 (Python 3.14.10)

The run used a clean working tree (`harness_dirty: false`). Every implementation read `n` from
`input.txt`. Tables are generated with `python3 harness/bench.py report` from the raw JSON stored
next to `environment.json`. `vs fastest (wall)` compares wall-clock medians within a case.

**iterative_1m**

| implementation | median (s) | min (s) | stddev (s) | memory (MiB) | startup (s) | net (s) | vs fastest (wall) |
|---|---|---|---|---|---|---|---|
| arx-while | 0.0767 | 0.0759 | 0.0064 | 1.6 | 0.0048 | 0.0719 | 6.2x |
| arx-range | 0.8195 | 0.8133 | 0.0162 | 1.7 | 0.0048 | 0.8146 | 65.8x |
| c-O0 | 0.0559 | 0.0546 | 0.0050 | 1.6 | 0.0027 | 0.0532 | 4.5x |
| c-O0-checked | 0.1342 | 0.1329 | 0.0078 | 1.6 | 0.0027 | 0.1315 | 10.8x |
| c-O2 | 0.0170 | 0.0158 | 0.0008 | 1.5 | 0.0026 | 0.0145 | 1.4x |
| c-O2-checked | 0.0125 | 0.0114 | 0.0051 | 1.5 | 0.0026 | 0.0099 | 1.0x |
| python | 0.6001 | 0.5976 | 0.0136 | 9.8 | 0.0179 | 0.5822 | 48.2x |
| rust-O0 | 0.0385 | 0.0377 | 0.0069 | 1.8 | 0.0033 | 0.0353 | 3.1x |
| rust-O0-checked | 0.0596 | 0.0585 | 0.0065 | 1.8 | 0.0033 | 0.0563 | 4.8x |
| rust-O2 | 0.0180 | 0.0169 | 0.0056 | 1.7 | 0.0031 | 0.0149 | 1.4x |
| rust-O2-checked | 0.0127 | 0.0117 | 0.0005 | 1.7 | 0.0031 | 0.0096 | 1.0x |
| go | 0.0202 | 0.0193 | 0.0047 | 4.1 | 0.0038 | 0.0164 | 1.6x |
| lua | 0.2343 | 0.2324 | 0.0097 | 1.9 | 0.0034 | 0.2309 | 18.8x |
| java | 0.0546 | 0.0529 | 0.0065 | 40.8 | 0.0374 | 0.0172 | 4.4x |
| java-checked | 0.0600 | 0.0574 | 0.0063 | 40.9 | 0.0374 | 0.0226 | 4.8x |
| julia | 0.1567 | 0.1534 | 0.0083 | 208.3 | 0.0924 | 0.0643 | 12.6x |
| julia-checked | 0.1577 | 0.1535 | 0.0156 | 208.3 | 0.0924 | 0.0653 | 12.7x |
| numba | 0.3740 | 0.3689 | 0.0089 | 114.5 | 0.1838 | 0.1902 | 30.0x |

**recursive_35**

| implementation | median (s) | min (s) | stddev (s) | memory (MiB) | startup (s) | net (s) | vs fastest (wall) |
|---|---|---|---|---|---|---|---|
| arx | 0.0606 | 0.0594 | 0.0058 | 1.6 | 0.0048 | 0.0557 | 1.8x |
| c-O0 | 0.0550 | 0.0538 | 0.0004 | 1.6 | 0.0027 | 0.0524 | 1.7x |
| c-O0-checked | 0.1016 | 0.1013 | 0.0085 | 1.6 | 0.0027 | 0.0990 | 3.1x |
| c-O2 | 0.0332 | 0.0325 | 0.0061 | 1.5 | 0.0026 | 0.0306 | 1.0x |
| c-O2-checked | 0.0408 | 0.0400 | 0.0058 | 1.5 | 0.0026 | 0.0383 | 1.2x |
| python | 0.7144 | 0.7134 | 0.0150 | 9.7 | 0.0179 | 0.6965 | 21.6x |
| rust-O0 | 0.0552 | 0.0543 | 0.0080 | 1.8 | 0.0033 | 0.0520 | 1.7x |
| rust-O0-checked | 0.0695 | 0.0683 | 0.0068 | 1.8 | 0.0033 | 0.0663 | 2.1x |
| rust-O2 | 0.0331 | 0.0321 | 0.0005 | 1.7 | 0.0031 | 0.0300 | 1.0x |
| rust-O2-checked | 0.0409 | 0.0400 | 0.0048 | 1.7 | 0.0031 | 0.0378 | 1.2x |
| go | 0.0359 | 0.0353 | 0.0058 | 4.1 | 0.0038 | 0.0321 | 1.1x |
| lua | 0.5304 | 0.5282 | 0.0128 | 1.9 | 0.0034 | 0.5271 | 16.0x |
| java | 0.0675 | 0.0659 | 0.0065 | 40.2 | 0.0374 | 0.0301 | 2.0x |
| java-checked | 0.0737 | 0.0717 | 0.0049 | 40.5 | 0.0374 | 0.0363 | 2.2x |
| julia | 0.1810 | 0.1788 | 0.0092 | 208.3 | 0.0924 | 0.0886 | 5.5x |
| julia-checked | 0.1823 | 0.1805 | 0.0098 | 208.2 | 0.0924 | 0.0899 | 5.5x |
| numba | 0.4020 | 0.3975 | 0.0134 | 114.6 | 0.1838 | 0.2182 | 12.1x |

**recursive_40**

| implementation | median (s) | min (s) | stddev (s) | memory (MiB) | startup (s) | net (s) | vs fastest (wall) |
|---|---|---|---|---|---|---|---|
| arx | 0.6205 | 0.6196 | 0.0120 | 1.6 | 0.0048 | 0.6157 | 1.9x |
| c-O0 | 0.5627 | 0.5619 | 0.0188 | 1.6 | 0.0027 | 0.5601 | 1.8x |
| c-O0-checked | 1.0769 | 1.0753 | 0.0200 | 1.6 | 0.0027 | 1.0742 | 3.4x |
| c-O2 | 0.3196 | 0.3192 | 0.0016 | 1.5 | 0.0026 | 0.3170 | 1.0x |
| c-O2-checked | 0.4032 | 0.4027 | 0.0170 | 1.5 | 0.0026 | 0.4007 | 1.3x |
| python | 7.8676 | 7.8620 | 0.0048 | 9.8 | 0.0179 | 7.8497 | 24.6x |
| rust-O0 | 0.5630 | 0.5621 | 0.0185 | 1.8 | 0.0033 | 0.5597 | 1.8x |
| rust-O0-checked | 0.7236 | 0.7215 | 0.0158 | 1.8 | 0.0033 | 0.7203 | 2.3x |
| rust-O2 | 0.3199 | 0.3195 | 0.0134 | 1.7 | 0.0031 | 0.3168 | 1.0x |
| rust-O2-checked | 0.4052 | 0.4034 | 0.0134 | 1.7 | 0.0031 | 0.4021 | 1.3x |
| go | 0.3520 | 0.3509 | 0.0144 | 4.1 | 0.0038 | 0.3482 | 1.1x |
| lua | 5.8828 | 5.8668 | 0.0100 | 1.9 | 0.0034 | 5.8794 | 18.4x |
| java | 0.3204 | 0.3200 | 0.0143 | 40.3 | 0.0374 | 0.2830 | 1.0x |
| java-checked | 0.3788 | 0.3508 | 0.0142 | 40.5 | 0.0374 | 0.3415 | 1.2x |
| julia | 0.5561 | 0.5536 | 0.0027 | 208.3 | 0.0924 | 0.4636 | 1.7x |
| julia-checked | 0.5565 | 0.5532 | 0.0023 | 208.3 | 0.0924 | 0.4640 | 1.7x |
| numba | 0.8048 | 0.8020 | 0.0060 | 114.5 | 0.1838 | 0.6210 | 2.5x |

### Observations

Ratios are computed from the medians above.

**Recursion (`recursive_40`, lowest noise)**

- Arx is 1.10x slower than `c-O0` and 1.94x slower than `c-O2`. It is 12.7x faster than CPython
  and 9.5x faster than Lua.
- `c-O2`, `rust-O2` and `java` are equal within 0.3% (0.320 s). `go` is 1.10x slower than
  `c-O2`. `julia` (0.556 s) and `numba` (0.805 s) include JIT compilation.
- Overflow checking costs 1.26x (`c-O2-checked`), 1.27x (`rust-O2-checked`) and 1.18x
  (`java-checked`) at full optimization, 1.91x for `c-O0-checked` and 1.29x for
  `rust-O0-checked`. `julia-checked` shows no measurable difference. Arx, which checks every
  operation, is 1.74x faster than `c-O0-checked`, 1.17x faster than `rust-O0-checked`, and about
  1.5x slower than the `-O2` checked builds.
- `recursive_35` shows the same picture: Arx is 1.10x slower than `c-O0`, 1.83x slower than
  `c-O2` and 11.8x faster than CPython.

**Loops (`iterative_1m`)**

- `arx-while` is 1.37x slower than `c-O0`, 4.5x slower than `c-O2` and 1.40x slower than `java`.
  It is 3.1x faster than Lua and 7.8x faster than CPython.
- `arx-range` is 10.7x slower than `arx-while` and 1.37x slower than CPython, because `range`
  allocates a list on every call.
- At `-O2`, the checked C and Rust builds are faster than the unchecked builds (`c-O2-checked`
  0.0125 s against `c-O2` 0.0170 s; `rust-O2-checked` 0.0127 s against `rust-O2` 0.0180 s). The
  result repeated in every full run and in both compilers. The cause has not been investigated,
  so it should not be read as "checking is free".

**Start-up and JIT**

- Empty-program start-up is about 3 ms for C, Rust, Go and Lua, 18 ms for CPython, 37 ms for
  Java, 92 ms for Julia and 184 ms for Numba. `net` subtracts this, but JIT compilation remains
  inside `net`. The Arx and Go baselines each contain one outlier, which raises their median
  start-up slightly (Arx 4.8 ms here, 3.3 ms in earlier runs).

**Memory**

- Peak resident memory is 1.5-1.9 MiB for Arx, C, Rust and Lua, 4.1 MiB for Go, 9.7 MiB for
  CPython, about 40 MiB for Java, about 115 MiB for Numba and about 208 MiB for Julia.

**Noise**

- All `recursive_40` rows are under 5% coefficient of variation. Rows for `recursive_35` and
  `iterative_1m` reach 18% and 41% because of single outlier runs (for example `c-O2-checked`:
  min 11.4 ms, max 39.8 ms), so compare medians there.

<!-- results:end -->