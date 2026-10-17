"""Build wheels with sccache and retain comparable per-package CI measurements."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sysconfig
import time
import tomllib


METRICS = Path("build-metrics")
REPORT = METRICS / "metrics.json"


def projects():
    if Path("tirx/pyproject.toml").exists():
        return [("ffi", Path("tirx/3rdparty/tvm-ffi")), ("tirx", Path("tirx")), ("tvm", Path("."))]
    return [("tvm", Path(".")), ("ffi", Path("3rdparty/tvm-ffi"))]


def project_config(project):
    return tomllib.loads((project / "pyproject.toml").read_text(encoding="utf-8"))


def output(command):
    return subprocess.check_output(command, text=True).strip()


def write_report(data):
    METRICS.mkdir(exist_ok=True)
    REPORT.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def load_report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def append_env(name, value):
    with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as stream:
        stream.write(f"{name}={value}\n")


def prepare():
    # uv's isolated build environments have random paths. Install the projects'
    # declared requirements in the job's dedicated .venv before disabling isolation.
    requirements = set()
    configs = [project_config(project) for _, project in projects()]
    local_names = {config["project"]["name"].lower().replace("_", "-") for config in configs}
    for config in configs:
        requirements.update(config["build-system"]["requires"])
    # The parent now builds against the source-built apache-tvm-tirx wheel.
    requirements = {item for item in requirements if re.split(r"[<>=!~\[; ]", item, 1)[0].lower().replace("_", "-") not in local_names}
    subprocess.run(["uv", "pip", "install", *sorted(requirements)], check=True)


def configure():
    compiler_names = ("cl",) if os.name == "nt" else ("cc", "c++")
    if os.environ["RUNNER_OS"] == "Linux":
        compiler_names += ("nvcc",)
    compilers = {}
    for name in compiler_names:
        executable = Path(shutil.which(name) or name).resolve(strict=True)
        compilers[name] = {
            "path": str(executable),
            "sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        }
        if os.name != "nt":
            compilers[name]["version"] = output([str(executable), "--version"])
    llvm_config = (
        Path(os.environ["LLVM_ROOT"]) / "bin/llvm-config"
        if os.environ["RUNNER_OS"] != "macOS"
        else Path(output(["brew", "--prefix", "llvm"])) / "bin/llvm-config"
    )
    if os.name == "nt":
        llvm_config = llvm_config.with_suffix(".exe")
    toolchain = {
        "compilers": compilers,
        "llvm": output([str(llvm_config), "--version"]),
        "cuda": os.environ.get("CUDA_VERSION", "") if platform.system() == "Linux" else "",
        "cmake": output(["cmake", "--version"]).splitlines()[0],
        "ninja": output(["ninja", "--version"]),
        "image": os.environ.get("ImageOS", ""),
        "include": os.environ.get("INCLUDE", ""),
        "sdk": os.environ.get("WindowsSDKVersion", ""),
        "macos_sdk": output(["xcrun", "--show-sdk-version"]) if platform.system() == "Darwin" else "",
        "z3": importlib.metadata.version("mlc-z3-static"),
    }
    fingerprint = hashlib.sha256(json.dumps(toolchain, sort_keys=True).encode()).hexdigest()[:20]
    prefix = f"sccache-v1-{os.environ['RUNNER_OS']}-{os.environ['RUNNER_ARCH']}-{fingerprint}-"
    source = output(["git", "rev-parse", "HEAD"])
    key = f"{prefix}{source}-{os.environ['GITHUB_RUN_ID']}"
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write(f"key={key}\nprefix={prefix}\nsource-prefix={prefix}{source}-\n")
    # Also normalize the Python-version-dependent site-packages prefix containing
    # Z3 headers. Compiler inputs and Python headers still determine object keys.
    append_env("SCCACHE_BASEDIRS", os.pathsep.join((str(Path.cwd()), sysconfig.get_paths()["purelib"])))
    # Visual Studio generators ignore COMPILER_LAUNCHER. Use Ninja for FFI too.
    append_env("CMAKE_GENERATOR", "Ninja")
    for language in ("C", "CXX", "CUDA", "OBJCXX"):
        append_env(f"CMAKE_{language}_COMPILER_LAUNCHER", "sccache")
    write_report({
        "os": os.environ["RUNNER_OS"],
        "python": platform.python_version(),
        "cpus": os.cpu_count(),
        "source": source,
        "ffi_source": output(["git", "-C", str(dict(projects())["ffi"]), "rev-parse", "HEAD"]),
        "workflow_sha": os.environ["GITHUB_SHA"],
        "run_id": os.environ["GITHUB_RUN_ID"],
        "run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "toolchain": toolchain,
        "build_dependencies": {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()},
        "cache_key": key,
        "force_recache": os.environ.get("SCCACHE_RECACHE") == "1",
        "phases": [],
    })


def restored():
    data = load_report()
    data["restore"] = {
        "seconds": round(time.time() - float(os.environ["RESTORE_START"]), 3),
        "exact_hit": os.environ.get("CACHE_HIT") == "true",
        "matched_key": os.environ.get("CACHE_MATCHED_KEY", ""),
    }
    write_report(data)


def build():
    # sccache treats RECACHE as a presence flag: even "0" forces a miss.
    if os.environ.get("SCCACHE_RECACHE") != "1":
        os.environ.pop("SCCACHE_RECACHE", None)
    # Restart after restore so the server sees the job's normalization/toolchain
    # environment and the fully restored on-disk cache.
    subprocess.run(["sccache", "--stop-server"], check=False)
    subprocess.run(["sccache", "--start-server"], check=True)
    cmake_args = os.environ["TVM_CMAKE_ARGS"]
    common = {f"CMAKE_{language}_COMPILER_LAUNCHER": "sccache" for language in ("C", "CXX", "CUDA", "OBJCXX")}
    if os.name == "nt":
        common.update(CMAKE_POLICY_DEFAULT_CMP0141="NEW", CMAKE_MSVC_DEBUG_INFORMATION_FORMAT="Embedded")
        common["CMAKE_PROJECT_TOP_LEVEL_INCLUDES"] = (Path(__file__).resolve().parent / "sccache-msvc.cmake").as_posix()
    package_projects = projects()
    split_core = any(name == "tirx" for name, _ in package_projects)
    wheelhouse = Path("wheelhouse")
    shutil.rmtree(wheelhouse, ignore_errors=True)
    wheelhouse.mkdir()
    for name, project in package_projects:
        args = cmake_args if name != "ffi" else ""
        if split_core:
            # Native core options acquired their own namespace during the split.
            for option in ("LLVM", "CUDA", "METAL", "Z3"):
                args = args.replace(f"-DUSE_{option}=", f"-DTVM_TIRX_USE_{option}=")
            if name == "tirx":
                args = ";".join(arg for arg in args.split(";") if not arg.startswith(("-DUSE_MLIR=", "-DUSE_TENSORRT_CODEGEN=")))
            elif name == "tvm":
                args = args.replace("-DUSE_TENSORRT_CODEGEN=", "-DTVM_USE_TENSORRT_CODEGEN=")
        # A rerun must compile from scratch, rather than hit Ninja's build tree.
        shutil.rmtree(project / "build", ignore_errors=True)
        subprocess.run(["sccache", "--zero-stats"], check=True)
        started = time.perf_counter()
        command = [
            "uv", "build", "--wheel", str(project), "--no-build-isolation",
            "--config-settings", "build-dir=build",
            "--verbose",
        ]
        if args:
            command += ["--config-settings", f"cmake.args={args}"]
        # Preserve FFI's upstream cmake.args defaults.
        for key, value in common.items():
            command += ["--config-settings", f"cmake.define.{key}={value}"]
        result = subprocess.run(command)
        seconds = time.perf_counter() - started
        stats = json.loads(output(["sccache", "--show-stats", "--stats-format=json"]))
        (METRICS / f"{name}-sccache.json").write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
        data = load_report()
        data["phases"].append({
            "name": name, "seconds": round(seconds, 3),
            "exit_code": result.returncode, "sccache": stats,
            "command": command,
            "parallel_level": os.environ.get("CMAKE_BUILD_PARALLEL_LEVEL", "default"),
        })
        write_report(data)
        print(f"{name}: {seconds:.1f} seconds, exit {result.returncode}", flush=True)
        if result.returncode:
            raise subprocess.CalledProcessError(result.returncode, "uv build")
        wheel_name = project_config(project)["project"]["name"].replace("-", "_")
        wheels = list((project / "dist").glob(f"{wheel_name}-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"Expected one {name} wheel, found {wheels}")
        shutil.copy2(wheels[0], wheelhouse / wheels[0].name)
        if split_core and name != "tvm":
            subprocess.run(["uv", "pip", "install", str(wheels[0])], check=True)
    subprocess.run(["sccache", "--stop-server"], check=True)


def summary():
    if not REPORT.exists():
        return
    data = load_report()
    cache_dir = Path(os.environ["SCCACHE_DIR"])
    data["cache_bytes"] = sum(path.stat().st_size for path in cache_dir.rglob("*") if path.is_file())
    write_report(data)
    lines = [
        f"### {data['os']} / Python {data['python']}",
        f"TVM: `{data['source']}`; FFI: `{data['ffi_source']}`",
        f"Restored: `{data.get('restore', {}).get('matched_key', '') or 'miss'}`",
        f"Restore: {data.get('restore', {}).get('seconds', 0):.1f}s; cache: {data['cache_bytes'] / 2**20:.1f} MiB",
        "", "| Package | Seconds | Hits | Misses | Hit rate | Uncacheable |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for phase in data["phases"]:
        stats = phase["sccache"]["stats"]
        hits = sum(stats["cache_hits"]["counts"].values())
        misses = sum(stats["cache_misses"]["counts"].values())
        rate = hits / (hits + misses) if hits + misses else 0
        lines.append(f"| {phase['name']} | {phase['seconds']:.1f} | {hits} | {misses} | {rate:.1%} | {stats['requests_not_cacheable']} |")
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "configure", "restored", "build", "summary"))
    globals()[parser.parse_args().command]()
