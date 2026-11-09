#!/usr/bin/env python3
"""Generic harness for the Arx benchmarks repository.

  python3 harness/bench.py list
  python3 harness/bench.py check  [SUITE ...] [--case ID] [--lang L,L]
  python3 harness/bench.py run    [SUITE ...] [--case ID] [--lang L,L] [--quick]
  python3 harness/bench.py report [RESULTS_DIR]

A suite is a folder in suites/ containing benchmark.toml. Languages are defined in the LANGS
registry below; a language is used when its toolchain is installed. Requires Python >= 3.11,
hyperfine and the toolchains of the languages being run.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
SUITES = ROOT / "suites"
BUILD = ROOT / "build"
RESULTS = ROOT / "results"
BASELINES = ROOT / "harness" / "baselines"
C_OPT_LEVELS = ("O0", "O2")
RUST_OPT_LEVELS = ("0", "2")
NUMBA_PY = os.environ.get("NUMBA_PYTHON", str(Path.home() / ".venvs" / "numba" / "bin" / "python"))

_built: set = set()


def sh(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return (r.stdout or r.stderr).strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def run_checked(cmd: list[str], what: str) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"{what} failed (exit {r.returncode}):\n  {shlex.join(cmd)}\n{r.stderr.strip()}")


def require(*tools: str) -> None:
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        sys.exit("missing required tools on PATH: " + ", ".join(missing))


# ----------------------------------------------------------------------------- languages
# build(src, outdir) compiles if needed and returns {label: argv}. Case arguments are appended
# to argv by the harness (Arx programs take none).

def _build_once(key: tuple, cmd: list[str], what: str) -> None:
    if key not in _built:
        run_checked(cmd, what)
        _built.add(key)


def build_arx(src: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    binary = out / f"arx-{src.stem}"
    _build_once(("arx", str(src), str(binary)), ["arx", str(src), "--output-file", str(binary)],
                f"arx compile {src.name}")
    return {"arx": [str(binary)]}


def build_c(src: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    cmds = {}
    for opt in C_OPT_LEVELS:
        for checked in (False, True):
            label = f"c-{opt}" + ("-checked" if checked else "")
            binary = out / label
            cmd = ["clang", f"-{opt}", *(["-DCHECKED"] if checked else []), "-o", str(binary), str(src)]
            _build_once(("c", str(src), str(binary)), cmd, f"clang {label}")
            cmds[label] = [str(binary)]
    return cmds


def build_python(src: Path, out: Path) -> dict:
    return {"python": [sys.executable, str(src)]}

def build_rust(src: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    cmds = {}
    for opt in RUST_OPT_LEVELS:
        for checked in (False, True):
            label = f"rust-O{opt}" + ("-checked" if checked else "")
            binary = out / label
            cmd = ["rustc", "-C", f"opt-level={opt}", "-C", f"overflow-checks={'on' if checked else 'off'}",
                   "-C", "debuginfo=0", "-o", str(binary), str(src)]
            _build_once(("rust", str(src), str(binary)), cmd, f"rustc {label}")
            cmds[label] = [str(binary)]
    return cmds

def build_go(src: Path, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    binary = out / f"go-{src.stem}"
    _build_once(("go", str(src), str(binary)), ["go", "build", "-o", str(binary), str(src)],
                f"go build {src.name}")
    return {"go": [str(binary)]}


def build_lua(src: Path, out: Path) -> dict:
    return {"lua": ["lua", str(src)]}


def build_java(src: Path, out: Path) -> dict:
    classes = out / f"java-{src.stem}"
    classes.mkdir(parents=True, exist_ok=True)
    _build_once(("java", str(src), str(classes)), ["javac", "-d", str(classes), str(src)],
                f"javac {src.name}")
    base = ["java", "-cp", str(classes), src.stem]
    return {"java": base, "java-checked": ["java", "-Dchecked=true", "-cp", str(classes), src.stem]}


def build_julia(src: Path, out: Path) -> dict:
    base = ["julia", "--startup-file=no", "-O2", str(src)]
    return {"julia": base, "julia-checked": [*base, "--checked"]}


def build_numba(src: Path, out: Path) -> dict:
    return {"numba": [NUMBA_PY, str(src)]}


@dataclass(frozen=True)
class Lang:
    name: str
    tools: tuple
    version_cmd: tuple
    build: Callable[[Path, Path], dict]
    baseline: str  # file in harness/baselines/


LANGS = {
    "arx": Lang("arx", ("arx",), ("arx", "--version"), build_arx, "empty.x"),
    "c": Lang("c", ("clang",), ("clang", "--version"), build_c, "empty.c"),
    "python": Lang("python", (), (sys.executable, "--version"), build_python, "empty.py"),
    "rust": Lang("rust", ("rustc",), ("rustc", "--version"), build_rust, "empty.rs"),
    "go": Lang("go", ("go",), ("go", "version"), build_go, "empty.go"),
    "lua": Lang("lua", ("lua",), ("lua", "-v"), build_lua, "empty.lua"),
    "java": Lang("java", ("javac", "java"), ("java", "-version"), build_java, "Empty.java"),
    "julia": Lang("julia", ("julia",), ("julia", "--version"), build_julia, "empty.jl"),
    "numba": Lang("numba", (NUMBA_PY,), (NUMBA_PY, "-c",
                  "import sys, numba; print('numba', numba.__version__, '(Python', sys.version.split()[0] + ')')"),
                  build_numba, "empty_numba.py"),
}


def family(label: str) -> str:
    """Baseline key for a result label (arx-* share the arx baseline; -checked uses its sibling's)."""
    if label.startswith("arx"):
        return "arx"
    return label.removesuffix("-checked")


def select_langs(spec: str | None) -> dict:
    wanted = [s.strip() for s in spec.split(",")] if spec else list(LANGS)
    unknown = [w for w in wanted if w not in LANGS]
    if unknown:
        sys.exit(f"unknown language(s): {', '.join(unknown)}; available: {', '.join(LANGS)}")
    chosen = {}
    for w in wanted:
        missing = [t for t in LANGS[w].tools if shutil.which(t) is None]
        if missing:
            if spec:
                sys.exit(f"--lang {w}: missing tools on PATH: {', '.join(missing)}")
            print(f"SKIP {w}: missing {', '.join(missing)}", file=sys.stderr)
            continue
        chosen[w] = LANGS[w]
    if not chosen:
        sys.exit("no usable languages")
    clang_path = shutil.which("clang") or ""
    if "c" in chosen and sys.platform == "darwin" and any(m in clang_path for m in ("conda", "mamba", "miniforge")):
        print(f"WARNING: clang is {clang_path}; conda clang failed to link Arx output on macOS "
              "in testing. Put Apple's /usr/bin/clang first on PATH.", file=sys.stderr)
    return chosen


# ----------------------------------------------------------------------------- suites
def load_suites(names: list[str]) -> dict:
    found = {}
    for manifest in sorted(SUITES.glob("*/benchmark.toml")):
        with manifest.open("rb") as f:
            data = tomllib.load(f)
        data["dir"] = manifest.parent
        found[manifest.parent.name] = data
    if not names:
        return found
    unknown = [n for n in names if n not in found]
    if unknown:
        sys.exit(f"unknown suite(s): {', '.join(unknown)}; available: {', '.join(found)}")
    return {n: found[n] for n in names}


def select(suites: dict, case_id: str | None) -> list:
    plan = [(s, c) for s in suites.values() for c in s["case"] if not case_id or c["id"] == case_id]
    if not plan:
        sys.exit("no matching cases")
    return plan


def case_dir(suite: dict, case: dict) -> Path:
    """Working directory for a case; holds input.txt when the case defines `input`."""
    d = BUILD / suite["dir"].name / "cases" / case["id"]
    d.mkdir(parents=True, exist_ok=True)
    if "input" in case:
        (d / "input.txt").write_text(str(case["input"]) + "\n")
    return d


def commands(suite: dict, case: dict, langs: dict) -> dict:
    out = BUILD / suite["dir"].name
    refs = suite.get("references", {})
    args = [str(a) for a in case.get("args", [])]
    cmds = {}
    if "arx" in langs:
        for label, src in case.get("arx", {}).items():
            cmds[label] = langs["arx"].build(suite["dir"] / src, out)["arx"]
    for name, lang in langs.items():
        if name == "arx" or name not in refs:
            continue
        for label, argv in lang.build(suite["dir"] / refs[name], out).items():
            cmds[label] = [*argv, *args]
    return cmds


def prepare(plan: list, langs: dict) -> list:
    prepared = []
    for suite, case in plan:
        cmds = commands(suite, case, langs)
        if not cmds:
            print(f"SKIP {suite['dir'].name}/{case['id']}: no implementation for the selected languages",
                  file=sys.stderr)
            continue
        prepared.append((suite, case, cmds))
    if not prepared:
        sys.exit("nothing to run")
    return prepared


def verify(suite: dict, case: dict, cmds: dict) -> None:
    # Also serves as the first launch of each fresh binary (macOS checks new executables).
    cwd = case_dir(suite, case)
    for label, cmd in cmds.items():
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        got = r.stdout.strip()
        if r.returncode != 0 or got != case["expected"]:
            sys.exit(f"WRONG OUTPUT [{suite['dir'].name}/{case['id']}] {label}: "
                     f"exit {r.returncode}, got {got!r}, expected {case['expected']!r}\n{r.stderr.strip()}")
    print(f"OK  {suite['dir'].name}/{case['id']}: {', '.join(cmds)}")


# ----------------------------------------------------------------------------- baseline
def baseline_commands(langs: dict) -> dict:
    out = BUILD / "_baseline"
    cmds = {}
    for lang in langs.values():
        cmds.update({
            k: v
            for k, v in lang.build(BASELINES / lang.baseline, out).items()
            if not k.endswith("-checked")
        })
    return cmds


def baseline_dir() -> Path:
    d = BUILD / "_baseline" / "cwd"
    d.mkdir(parents=True, exist_ok=True)
    return d


def verify_baseline(cmds: dict) -> None:
    for label, cmd in cmds.items():
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=baseline_dir())
        if r.returncode != 0 or r.stdout.strip():
            sys.exit(f"baseline {label} misbehaved: exit {r.returncode}, stdout {r.stdout!r}\n{r.stderr.strip()}")
    print(f"OK  baseline: {', '.join(cmds)}")


# ----------------------------------------------------------------------------- environment
def cpu_name() -> str:
    if sys.platform == "darwin":
        return sh(["sysctl", "-n", "machdep.cpu.brand_string"])
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor()


def environment(langs: dict) -> dict:
    arx_repo = os.environ.get("ARX_REPO")
    clang_version = sh(["clang", "--version"]).splitlines()
    now = datetime.now(timezone.utc)
    versions = {}
    for name, lang in langs.items():
        lines = sh(list(lang.version_cmd)).splitlines()
        versions[name] = lines[0] if lines else ""
    return {
        "date": now.date().isoformat(),
        "timestamp_utc": now.strftime("%Y-%m-%dT%H%M%SZ"),
        "arx": sh(["arx", "--version"]),
        "arx_commit": sh(["git", "-C", arx_repo, "rev-parse", "--short", "HEAD"]) if arx_repo else "",
        "arx_path": shutil.which("arx"),
        "clang": clang_version[0] if clang_version else "",
        "clang_path": shutil.which("clang"),
        "languages": versions,
        "hyperfine": sh(["hyperfine", "--version"]),
        "python": platform.python_version(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu": cpu_name(),
        "cpu_count": os.cpu_count(),
        "harness_commit": sh(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"]),
        "harness_dirty": bool(sh(["git", "-C", str(ROOT), "status", "--porcelain"])),
    }


# ----------------------------------------------------------------------------- commands
def hyperfine(cmds: dict, runs: int, warmup: int, export: Path, cwd: Path) -> None:
    hf = ["hyperfine", "-N", "--warmup", str(warmup), "--runs", str(runs), "--export-json", str(export)]
    for label, cmd in cmds.items():
        hf += ["--command-name", label, shlex.join(cmd)]
    subprocess.run(hf, check=True, cwd=cwd)


def cmd_list(args) -> None:
    print("languages:")
    for name, lang in LANGS.items():
        missing = [t for t in lang.tools if shutil.which(t) is None]
        print(f"  - {name}: {'missing ' + ', '.join(missing) if missing else 'available'}")
    for name, s in load_suites([]).items():
        print(f"{name}: {s.get('description', '')}")
        for c in s["case"]:
            print(f"  - {c['id']} (args {c.get('args', [])}, input {c.get('input', '-')}, expected {c['expected']})")


def cmd_check(args) -> None:
    plan = select(load_suites(args.suites), args.case)
    langs = select_langs(args.lang)
    prepared = prepare(plan, langs)
    for suite, case, cmds in prepared:
        verify(suite, case, cmds)
    verify_baseline(baseline_commands(langs))


def cmd_run(args) -> None:
    plan = select(load_suites(args.suites), args.case)
    langs = select_langs(args.lang)
    require("hyperfine")
    prepared = prepare(plan, langs)
    base_cmds = baseline_commands(langs)
    verify_baseline(base_cmds)
    env = environment(langs)
    base = BUILD / "quick-results" if args.quick else RESULTS
    name = f"{env['timestamp_utc']}_{platform.system().lower()}-{platform.machine()}_arx-{env['arx'] or 'none'}"
    final = base / name
    if final.exists():
        sys.exit(f"{final} already exists; refusing to overwrite an earlier run")
    base.mkdir(parents=True, exist_ok=True)
    outdir = base / f".{name}.partial"  # hidden until the run completes
    if outdir.exists():
        shutil.rmtree(outdir)
    outdir.mkdir()
    (outdir / "environment.json").write_text(json.dumps(env, indent=2) + "\n")

    print("\n== baseline (empty programs) ==", flush=True)
    hyperfine(base_cmds, 3 if args.quick else 10, 1 if args.quick else 2, outdir / "_baseline.json", baseline_dir())

    for suite, case, cmds in prepared:
        verify(suite, case, cmds)
        sdir = outdir / suite["dir"].name
        sdir.mkdir(exist_ok=True)
        runs, warmup = (3, 1) if args.quick else (case.get("runs", 10), case.get("warmup", 2))
        print(f"\n== {suite['dir'].name}/{case['id']} ==", flush=True)
        hyperfine(cmds, runs, warmup, sdir / f"{case['id']}.json", case_dir(suite, case))
    marker = {
        "schema_version": 1,
        "status": "complete",
        "finished_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ"),
        "timestamp_utc": env["timestamp_utc"],
        "cases": [f"{suite['dir'].name}/{case['id']}" for suite, case, _ in prepared],
        "labels": sorted({label for _, _, cmds in prepared for label in cmds}),
        "quick": bool(args.quick),
    }
    (outdir / "complete.json").write_text(json.dumps(marker, indent=2) + "\n")
    outdir.rename(final)
    print(f"\nresults written to {final}")


def parse_row(r: dict) -> tuple:
    name = r.get("name") or r["command"]
    if "summary" in r:  # hyperfine 2.x
        tw = r["summary"]["time_wall_clock"]
        med, mn, sd = tw["median"], tw["min"], tw.get("stddev") or 0.0
        mem = r["summary"].get("memory_peak_resident", {}).get("median")
    else:  # hyperfine 1.x
        med, mn, sd = r["median"], r["min"], r.get("stddev") or 0.0
        mem = r.get("memory_usage_byte")
    mib = mem / (1024 * 1024) if isinstance(mem, (int, float)) else None
    return name, med, mn, sd, mib

def run_timestamp(d: Path) -> str:
    """Sortable UTC timestamp of a run, taken from its recorded data, not its directory name."""
    for fname, key in (("complete.json", "timestamp_utc"), ("environment.json", "timestamp_utc")):
        f = d / fname
        if f.exists():
            try:
                v = json.loads(f.read_text()).get(key)
            except json.JSONDecodeError:
                v = None
            if v:
                return v
    env = d / "environment.json"
    if env.exists():  # runs made before timestamps were recorded only have a date
        date = json.loads(env.read_text()).get("date", "")
        return f"{date}T000000Z" if date else ""
    return ""


def is_complete(d: Path) -> bool:
    """A run is complete only if it has a completion marker with status "complete"."""
    if not (d / "environment.json").exists() or d.name.startswith("."):
        return False
    marker = d / "complete.json"
    if marker.exists():
        try:
            return json.loads(marker.read_text()).get("status") == "complete"
        except json.JSONDecodeError:
            return False
    return False


def cmd_report(args) -> None:
    if args.dir:
        d = Path(args.dir)
    else:
        runs = [p for p in RESULTS.glob("*") if is_complete(p)]
        if not runs:
            sys.exit("no complete results found")
        d = max(runs, key=run_timestamp)
    if not is_complete(d):
        sys.exit(f"{d} is not a complete run (no complete.json); refusing to report it")
    env = json.loads((d / "environment.json").read_text())
    langs = env.get("languages")
    extra = " | " + ", ".join(f"{k}: {v}" for k, v in langs.items()) if langs else ""
    print(f"Environment: {env['cpu']} | {env['os']} | arx {env['arx']} {env['arx_commit']} | "
          f"{env['clang']} | {env['hyperfine']} | Python {env['python']}{extra}\n")

    base = {}
    bf = d / "_baseline.json"
    if bf.exists():
        for row in json.loads(bf.read_text())["results"]:
            name, med, *_ = parse_row(row)
            base[name] = med

    for sdir in sorted(p for p in d.iterdir() if p.is_dir()):
        print(f"#### {sdir.name}\n")
        for f in sorted(sdir.glob("*.json")):
            parsed = [parse_row(r) for r in json.loads(f.read_text())["results"]]
            best = min(x[1] for x in parsed)
            has_mem = any(x[4] is not None for x in parsed)
            head = ["implementation", "median (s)", "min (s)", "stddev (s)"]
            if has_mem:
                head.append("memory (MiB)")
            if base:
                head += ["startup (s)", "net (s)"]
            head.append("vs fastest (wall)")
            print(f"**{f.stem}**\n\n| " + " | ".join(head) + " |\n|" + "---|" * len(head))
            for name, med, mn, sd, mib in parsed:
                row = [name, f"{med:.4f}", f"{mn:.4f}", f"{sd:.4f}"]
                if has_mem:
                    row.append(f"{mib:.1f}" if mib is not None else "-")
                if base:
                    b = base.get(family(name))
                    row += [f"{b:.4f}", f"{max(med - b, 0.0):.4f}"] if b is not None else ["-", "-"]
                row.append(f"{med / best:.1f}x")
                print("| " + " | ".join(row) + " |")
            print()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    for name, fn in (("check", cmd_check), ("run", cmd_run)):
        s = sub.add_parser(name)
        s.add_argument("suites", nargs="*")
        s.add_argument("--case")
        s.add_argument("--lang", help="comma-separated languages (default: all installed)")
        if name == "run":
            s.add_argument("--quick", action="store_true", help="3 runs, 1 warm-up; writes to build/quick-results")
        s.set_defaults(fn=fn)
    r = sub.add_parser("report")
    r.add_argument("dir", nargs="?")
    r.set_defaults(fn=cmd_report)
    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()