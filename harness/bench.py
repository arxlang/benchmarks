#!/usr/bin/env python3
"""Generic harness for the Arx benchmarks repository.

  python3 harness/bench.py list
  python3 harness/bench.py check  [SUITE ...] [--case ID]
  python3 harness/bench.py run    [SUITE ...] [--case ID] [--quick]
  python3 harness/bench.py report [RESULTS_DIR]

A suite is a folder in suites/ containing benchmark.toml. Requires Python >= 3.11,
hyperfine, clang and arx on PATH.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import shutil
import statistics
import subprocess
import sys
import tomllib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITES = ROOT / "suites"
BUILD = ROOT / "build"
RESULTS = ROOT / "results"
C_OPT_LEVELS = ("O0", "O2")


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


def environment() -> dict:
    arx_repo = os.environ.get("ARX_REPO")
    clang_version = sh(["clang", "--version"]).splitlines()
    now = datetime.now(timezone.utc)
    return {
        "date": now.date().isoformat(),
        "timestamp_utc": now.strftime("%Y-%m-%dT%H%M%SZ"),
        "arx": sh(["arx", "--version"]),
        "arx_commit": sh(["git", "-C", arx_repo, "rev-parse", "--short", "HEAD"]) if arx_repo else "",
        "arx_path": shutil.which("arx"),
        "clang": clang_version[0] if clang_version else "",
        "clang_path": shutil.which("clang"),
        "hyperfine": sh(["hyperfine", "--version"]),
        "python": platform.python_version(),
        "os": platform.platform(),
        "machine": platform.machine(),
        "cpu": cpu_name(),
        "cpu_count": os.cpu_count(),
        "harness_commit": sh(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"]),
        "harness_dirty": bool(sh(["git", "-C", str(ROOT), "status", "--porcelain"])),
    }


def prepare(plan: list, need_hyperfine: bool) -> None:
    refs_c = any("c" in s.get("references", {}) for s, _ in plan)
    needs_arx = any(c.get("arx") for _, c in plan)
    require(*(["hyperfine"] if need_hyperfine else []),
            *(["clang"] if refs_c else []), *(["arx"] if needs_arx else []))
    clang_path = shutil.which("clang") or ""
    if sys.platform == "darwin" and any(m in clang_path for m in ("conda", "mamba", "miniforge")):
        print(f"WARNING: clang is {clang_path}; conda clang failed to link Arx output on macOS "
              "in testing. Put Apple's /usr/bin/clang first on PATH.", file=sys.stderr)
    built_c = set()
    built_arx = set()
    for suite, case in plan:
        name = suite["dir"].name
        out = BUILD / name
        out.mkdir(parents=True, exist_ok=True)
        if "c" in suite.get("references", {}) and name not in built_c:
            for opt in C_OPT_LEVELS:
                run_checked(["clang", f"-{opt}", "-o", str(out / f"c-{opt}"),
                             str(suite["dir"] / suite["references"]["c"])], f"clang -{opt}")
            built_c.add(name)
        for src in dict.fromkeys(case.get("arx", {}).values()):
            if (name, src) in built_arx:
                continue
            run_checked(["arx", str(suite["dir"] / src), "--output-file",
                         str(out / arx_bin(src))], f"arx compile {src}")
            built_arx.add((name, src))


def arx_bin(src: str) -> str:
    return "arx-" + Path(src).stem


def case_dir(suite: dict, case: dict) -> Path:
    """Working directory for a case; holds input.txt when the case defines `input`."""
    d = BUILD / suite["dir"].name / "cases" / case["id"]
    d.mkdir(parents=True, exist_ok=True)
    if "input" in case:
        (d / "input.txt").write_text(str(case["input"]) + "\n")
    return d


def commands(suite: dict, case: dict) -> dict:
    out = BUILD / suite["dir"].name
    refs = suite.get("references", {})
    args = [str(a) for a in case.get("args", [])]
    cmds = {label: [str(out / arx_bin(src))] for label, src in case.get("arx", {}).items()}
    if "c" in refs:
        for opt in C_OPT_LEVELS:
            cmds[f"c-{opt}"] = [str(out / f"c-{opt}"), *args]
    if "python" in refs:
        cmds["python"] = [sys.executable, str(suite["dir"] / refs["python"]), *args]
    return cmds


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


def cmd_list(args) -> None:
    for name, s in load_suites([]).items():
        print(f"{name}: {s.get('description', '')}")
        for c in s["case"]:
            print(f"  - {c['id']} (args {c.get('args', [])}, input {c.get('input', '-')}, expected {c['expected']})")


def cmd_check(args) -> None:
    plan = select(load_suites(args.suites), args.case)
    prepare(plan, need_hyperfine=False)
    for suite, case in plan:
        verify(suite, case, commands(suite, case))


def cmd_run(args) -> None:
    plan = select(load_suites(args.suites), args.case)
    prepare(plan, need_hyperfine=True)
    env = environment()
    base = BUILD / "quick-results" if args.quick else RESULTS
    outdir = base / f"{env['timestamp_utc']}_{platform.system().lower()}-{platform.machine()}_arx-{env['arx']}"
    outdir.mkdir(parents=True, exist_ok=False)  # never overwrite an earlier run
    (outdir / "environment.json").write_text(json.dumps(env, indent=2) + "\n")
    for suite, case in plan:
        cmds = commands(suite, case)
        verify(suite, case, cmds)
        sdir = outdir / suite["dir"].name
        sdir.mkdir(exist_ok=True)
        runs, warmup = (3, 1) if args.quick else (case.get("runs", 10), case.get("warmup", 2))
        hf = ["hyperfine", "-N", "--warmup", str(warmup), "--runs", str(runs),
              "--export-json", str(sdir / f"{case['id']}.json")]
        for label, cmd in cmds.items():
            hf += ["--command-name", label, shlex.join(cmd)]
        print(f"\n== {suite['dir'].name}/{case['id']} ==", flush=True)
        subprocess.run(hf, check=True, cwd=case_dir(suite, case))
    print(f"\nresults written to {outdir}")


def cmd_report(args) -> None:
    if args.dir:
        d = Path(args.dir)
    else:
        runs = sorted(p for p in RESULTS.glob("*") if (p / "environment.json").exists())
        if not runs:
            sys.exit("no results found")
        d = runs[-1]
    env = json.loads((d / "environment.json").read_text())
    print(f"Environment: {env['cpu']} | {env['os']} | arx {env['arx']} {env['arx_commit']} | "
          f"{env['clang']} | {env['hyperfine']} | Python {env['python']}\n")
    for sdir in sorted(p for p in d.iterdir() if p.is_dir()):
        print(f"#### {sdir.name}\n")
        for f in sorted(sdir.glob("*.json")):
            rows = json.loads(f.read_text())["results"]
            parsed = []
            for r in rows:
                name = r.get("name") or r["command"]
                if "summary" in r:  # Hyperfine 2.0 (schema_version 2)
                    tw = r["summary"]["time_wall_clock"]
                    med, mn, sd = tw["median"], tw["min"], (tw.get("stddev") or 0.0)
                    mem = r["summary"].get("memory_peak_resident", {}).get("median")
                else:  # Hyperfine 1.x (schema_version 1)
                    med, mn, sd = r["median"], r["min"], (r.get("stddev") or 0.0)
                    mem = r.get("memory_usage_byte")
                mem_mib = (mem / (1024 * 1024)) if isinstance(mem, (int, float)) else None
                parsed.append((name, med, mn, sd, mem_mib))
            best = min(x[1] for x in parsed)
            has_mem = any(x[4] is not None for x in parsed)
            if has_mem:
                print(f"**{f.stem}**\n\n| implementation | median (s) | min (s) | stddev (s) | memory (MiB) | vs fastest |\n|---|---|---|---|---|---|")
                for name, med, mn, sd, mem_mib in parsed:
                    m_str = f"{mem_mib:.1f}" if mem_mib is not None else "-"
                    print(f"| {name} | {med:.4f} | {mn:.4f} | {sd:.4f} | {m_str} | {med / best:.1f}x |")
            else:
                print(f"**{f.stem}**\n\n| implementation | median (s) | min (s) | stddev (s) | vs fastest |\n|---|---|---|---|---|")
                for name, med, mn, sd, _ in parsed:
                    print(f"| {name} | {med:.4f} | {mn:.4f} | {sd:.4f} | {med / best:.1f}x |")
            print()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    for name, fn in (("check", cmd_check), ("run", cmd_run)):
        s = sub.add_parser(name)
        s.add_argument("suites", nargs="*")
        s.add_argument("--case")
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
