"""Tools for running external benchmark commands."""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.tools import tool


def _normalize_command(command: str | Sequence[str]) -> List[str]:
    if isinstance(command, str):
        return shlex.split(command)
    return list(command)

_TIME_UNITS_MS = {
    "us": 0.001,
    "µs": 0.001,
    "ms": 1.0,
    "s": 1000.0,
}

_DATA_UNITS_MB = {
    "KB": 1.0 / 1024.0,
    "MB": 1.0,
    "GB": 1024.0,
}


def _to_ms(value: float, unit: str) -> Optional[float]:
    factor = _TIME_UNITS_MS.get(unit)
    if factor is None:
        return None
    return value * factor


def _to_mb(value: float, unit: str) -> Optional[float]:
    factor = _DATA_UNITS_MB.get(unit)
    if factor is None:
        return None
    return value * factor


def parse_wrk_output(output: str) -> Dict[str, Any]:
    """Parse wrk/wrk2 output and extract summary metrics."""
    metrics: Dict[str, Any] = {
        "latency_ms": {},
        "percentiles_ms": {},
        "socket_errors": {},
    }

    latency_line = re.search(
        r"Latency\s+([\d\.]+)([a-zµ]+)\s+([\d\.]+)([a-zµ]+)\s+([\d\.]+)([a-zµ]+)",
        output,
        re.IGNORECASE,
    )
    if latency_line:
        avg = _to_ms(float(latency_line.group(1)), latency_line.group(2))
        stdev = _to_ms(float(latency_line.group(3)), latency_line.group(4))
        p99 = _to_ms(float(latency_line.group(5)), latency_line.group(6))
        if avg is not None:
            metrics["latency_ms"]["avg"] = avg
        if stdev is not None:
            metrics["latency_ms"]["stdev"] = stdev
        if p99 is not None:
            metrics["latency_ms"]["p99"] = p99

    for line in output.splitlines():
        match = re.match(r"^\s*([\d\.]+)%\s+([\d\.]+)([a-zµ]+)\s*$", line)
        if not match:
            continue
        percentile = match.group(1)
        value = _to_ms(float(match.group(2)), match.group(3))
        if value is not None:
            metrics["percentiles_ms"][percentile] = value

    rps_match = re.search(r"Requests/sec:\s*([\d\.]+)", output)
    if rps_match:
        metrics["requests_per_sec"] = float(rps_match.group(1))

    transfer_match = re.search(r"Transfer/sec:\s*([\d\.]+)\s*([KMG]B)", output)
    if transfer_match:
        transfer_mb = _to_mb(float(transfer_match.group(1)), transfer_match.group(2))
        if transfer_mb is not None:
            metrics["transfer_per_sec_mb"] = transfer_mb

    socket_match = re.search(
        r"Socket errors:\s*connect\s+(\d+),\s*read\s+(\d+),\s*write\s+(\d+),\s*timeout\s+(\d+)",
        output,
    )
    if socket_match:
        metrics["socket_errors"] = {
            "connect": int(socket_match.group(1)),
            "read": int(socket_match.group(2)),
            "write": int(socket_match.group(3)),
            "timeout": int(socket_match.group(4)),
        }

    summary_match = re.search(
        r"(\d+)\s+requests in\s+([\d\.]+)([smh]),\s+([\d\.]+)([KMG]B)\s+read",
        output,
    )
    if summary_match:
        metrics["total_requests"] = int(summary_match.group(1))
        duration = float(summary_match.group(2))
        duration_unit = summary_match.group(3)
        if duration_unit == "s":
            metrics["duration_seconds"] = duration
        elif duration_unit == "m":
            metrics["duration_seconds"] = duration * 60.0
        elif duration_unit == "h":
            metrics["duration_seconds"] = duration * 3600.0

        data_mb = _to_mb(float(summary_match.group(4)), summary_match.group(5))
        if data_mb is not None:
            metrics["data_read_mb"] = data_mb

    return metrics


def compare_benchmark_metrics(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Compare benchmark metrics before vs after."""
    def delta(before_val: Optional[float], after_val: Optional[float]) -> Dict[str, Any]:
        if before_val is None or after_val is None:
            return {"before": before_val, "after": after_val, "delta": None, "pct_change": None}
        diff = after_val - before_val
        pct = (diff / before_val * 100.0) if before_val != 0 else None
        return {
            "before": before_val,
            "after": after_val,
            "delta": diff,
            "pct_change": pct,
        }

    before_metrics = before.get("metrics", {})
    after_metrics = after.get("metrics", {})

    comparison = {
        "requests_per_sec": delta(before_metrics.get("requests_per_sec"), after_metrics.get("requests_per_sec")),
        "transfer_per_sec_mb": delta(
            before_metrics.get("transfer_per_sec_mb"),
            after_metrics.get("transfer_per_sec_mb"),
        ),
        "latency_avg_ms": delta(
            before_metrics.get("latency_ms", {}).get("avg"),
            after_metrics.get("latency_ms", {}).get("avg"),
        ),
        "latency_p50_ms": delta(
            before_metrics.get("percentiles_ms", {}).get("50.000"),
            after_metrics.get("percentiles_ms", {}).get("50.000"),
        ),
        "latency_p90_ms": delta(
            before_metrics.get("percentiles_ms", {}).get("90.000"),
            after_metrics.get("percentiles_ms", {}).get("90.000"),
        ),
        "latency_p99_ms": delta(
            before_metrics.get("percentiles_ms", {}).get("99.000"),
            after_metrics.get("percentiles_ms", {}).get("99.000"),
        ),
    }
    return comparison


def write_benchmark_report(
    output_dir: Path,
    before: Dict[str, Any],
    after: Dict[str, Any],
    comparison: Dict[str, Any],
) -> Dict[str, Any]:
    """Write benchmark summary artifacts to disk."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "benchmark_report.json"
    comparison_path = output_dir / "benchmark_comparison.json"

    report_path.write_text(json.dumps({"before": before, "after": after}, indent=2), encoding="utf-8")
    comparison_path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")

    return {
        "benchmark_report": report_path.as_posix(),
        "benchmark_comparison": comparison_path.as_posix(),
    }


def render_benchmark_charts(
    output_dir: Path,
    comparison: Dict[str, Any],
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> Dict[str, Any]:
    """Render benchmark comparison charts (optional, requires matplotlib)."""
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as exc:
        return {"error": f"matplotlib_not_installed: {exc}", "charts": []}

    charts = []
    output_dir.mkdir(parents=True, exist_ok=True)

    latency_items = [
        ("p50", comparison.get("latency_p50_ms")),
        ("p90", comparison.get("latency_p90_ms")),
        ("p99", comparison.get("latency_p99_ms")),
        ("avg", comparison.get("latency_avg_ms")),
    ]
    labels = [
        name
        for name, item in latency_items
        if item and item["before"] is not None and item["after"] is not None
    ]
    before_vals = [
        item["before"]
        for name, item in latency_items
        if item and item["before"] is not None and item["after"] is not None
    ]
    after_vals = [
        item["after"]
        for name, item in latency_items
        if item and item["before"] is not None and item["after"] is not None
    ]

    if labels:
        fig, ax = plt.subplots(figsize=(6, 4))
        x = range(len(labels))
        ax.bar([i - 0.2 for i in x], before_vals, width=0.4, label="Before")
        ax.bar([i + 0.2 for i in x], after_vals, width=0.4, label="After")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.set_ylabel("Latency (ms)")
        ax.set_title("Latency Comparison")
        ax.legend()
        chart_path = output_dir / "latency_comparison.png"
        fig.tight_layout()
        fig.savefig(chart_path, dpi=140)
        plt.close(fig)
        charts.append(chart_path.as_posix())

    throughput_items = [
        ("rps", comparison.get("requests_per_sec")),
        ("MB/s", comparison.get("transfer_per_sec_mb")),
    ]
    labels = [
        name
        for name, item in throughput_items
        if item and item["before"] is not None and item["after"] is not None
    ]
    before_vals = [
        item["before"]
        for name, item in throughput_items
        if item and item["before"] is not None and item["after"] is not None
    ]
    after_vals = [
        item["after"]
        for name, item in throughput_items
        if item and item["before"] is not None and item["after"] is not None
    ]

    if labels:
        fig, ax = plt.subplots(figsize=(6, 4))
        x = range(len(labels))
        ax.bar([i - 0.2 for i in x], before_vals, width=0.4, label="Before")
        ax.bar([i + 0.2 for i in x], after_vals, width=0.4, label="After")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.set_ylabel("Throughput")
        ax.set_title("Throughput Comparison")
        ax.legend()
        chart_path = output_dir / "throughput_comparison.png"
        fig.tight_layout()
        fig.savefig(chart_path, dpi=140)
        plt.close(fig)
        charts.append(chart_path.as_posix())

    return {"charts": charts}


def _run_benchmark_command_impl(
    command: str | List[str],
    command_env: str,
    workdir: str,
    timeout_seconds: int,
    output_dir: str,
    label: str,
) -> Dict[str, Any]:
    if not command:
        command = os.environ.get(command_env, "")

    use_shell = isinstance(command, str)
    argv = _normalize_command(command) if not use_shell else []
    if (use_shell and not command) or (not use_shell and not argv):
        return {"error": "empty_command", "command_env": command_env}

    cwd = Path(workdir).resolve() if workdir else Path.cwd().resolve()
    if not cwd.exists():
        return {"error": "workdir_not_found", "workdir": str(cwd)}

    start = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(
            command if use_shell else argv,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=timeout_seconds,
            shell=use_shell,
            executable="/bin/bash" if use_shell else None,
        )
        stdout_text = result.stdout or ""
        stderr_text = result.stderr or ""
        exit_code = result.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout_text = exc.stdout or ""
        stderr_text = exc.stderr or ""
        exit_code = None
    except FileNotFoundError:
        return {"error": "command_not_found", "command": argv}
    except Exception as exc:
        return {"error": "command_failed", "detail": str(exc)}

    duration = time.monotonic() - start

    metrics = parse_wrk_output(stdout_text) or parse_wrk_output(stderr_text)

    payload: Dict[str, Any] = {
        "command": command if use_shell else argv,
        "workdir": str(cwd),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_seconds": round(duration, 3),
        "stdout": stdout_text,
        "stderr": stderr_text,
        "metrics": metrics,
    }

    if output_dir:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = out_dir / f"{label}_stdout.txt"
        stderr_path = out_dir / f"{label}_stderr.txt"
        stdout_path.write_text(stdout_text or "", encoding="utf-8")
        stderr_path.write_text(stderr_text or "", encoding="utf-8")
        payload["stdout_path"] = stdout_path.as_posix()
        payload["stderr_path"] = stderr_path.as_posix()

    return payload


@tool
async def run_benchmark_command(
    command: str | List[str] = "",
    command_env: str = "BENCHMARK_CMD",
    workdir: str = "",
    timeout_seconds: int = 1800,
    output_dir: str = "",
    label: str = "benchmark",
) -> str:
    """Run an external benchmark command and return stdout/stderr metadata.

    Args:
        command (str | List[str]): Command string or argv list to execute. If empty, loads from command_env.
        command_env (str): Environment variable containing the command string. Default: BENCHMARK_CMD.
        workdir (str): Working directory for the command. Defaults to current directory.
        timeout_seconds (int): Timeout in seconds. Default: 1800.
        output_dir (str): Optional directory to write stdout/stderr files.
        label (str): Label prefix for output files when output_dir is set.

    Returns:
        str: JSON string with execution metadata and outputs.
    """
    payload = await asyncio.to_thread(
        _run_benchmark_command_impl,
        command,
        command_env,
        workdir,
        timeout_seconds,
        output_dir,
        label,
    )
    return json.dumps(payload)


@tool
async def run_benchmark_comparison(
    command_env: str = "BENCHMARK_CMD",
    workdir: str = "",
    timeout_seconds: int = 1800,
    output_dir: str = "",
    render_charts: bool = True,
) -> str:
    """Run benchmark commands before/after and return comparison payload."""
    command_before = os.environ.get(command_env, "")
    command_after = os.environ.get(command_env, "")

    before = await asyncio.to_thread(
        _run_benchmark_command_impl,
        command_before,
        command_env,
        workdir,
        timeout_seconds,
        output_dir,
        "before",
    )
    after = await asyncio.to_thread(
        _run_benchmark_command_impl,
        command_after,
        command_env,
        workdir,
        timeout_seconds,
        output_dir,
        "after",
    )

    if "error" in before:
        return json.dumps({"error": "before_failed", "before": before})
    if "error" in after:
        return json.dumps({"error": "after_failed", "after": after})

    comparison = compare_benchmark_metrics(before, after)
    payload: Dict[str, Any] = {
        "before": before,
        "after": after,
        "comparison": comparison,
    }

    if output_dir:
        report_paths = write_benchmark_report(
            Path(output_dir), before, after, comparison
        )
        payload["report_paths"] = report_paths
        if render_charts:
            payload["charts"] = render_benchmark_charts(
                Path(output_dir), comparison, before, after
            )

    return json.dumps(payload)
