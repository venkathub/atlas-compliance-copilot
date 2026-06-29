"""CLI for the GPU lifecycle helper.

Subcommands:
  up      resume + health-poll + discover OLLAMA_BASE_URL (+ --write-env) + arm watchdog
  down    pause + cancel the watchdog
  run     resume -> run `-- <cmd...>` -> GUARANTEED pause (the calibration-job path)
  _watchdog  (internal) detached deadline pauser armed by `up`

Wired into infra/Makefile as `make gpu-up` / `gpu-down`.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from atlas_gpu.bootstrap import provision_from_scratch, write_env
from atlas_gpu.lifecycle import Watchdog, http_health_check, run_with_gpu
from atlas_gpu.providers import GpuProviderError, make_provider
from atlas_gpu.provision import ProvisionConfig, ServeTarget

LOCK_PATH = Path(__file__).resolve().parent.parent / ".gpu-session.lock"


def _idle_timeout_s(env: dict | None = None) -> float:
    env = os.environ if env is None else env
    return float(env.get("GPU_IDLE_TIMEOUT_MIN", "20")) * 60.0


def _arm_watchdog(no_watchdog: bool) -> None:
    """Arm the detached deadline-pauser (second net): force-pause after the idle timeout."""
    LOCK_PATH.write_text(f"{time.time() + _idle_timeout_s()}\n")
    if no_watchdog:
        return
    subprocess.Popen(  # noqa: S603 - internal, no shell
        [sys.executable, "-m", "atlas_gpu", "_watchdog", "--lock", str(LOCK_PATH)],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    log_ok(
        f"watchdog armed: GPU auto-pauses in {_idle_timeout_s() / 60:.0f} min if not torn down"
    )


# ── subcommands ──────────────────────────────────────────────────────────────


def cmd_up(args: argparse.Namespace) -> int:
    provider = make_provider()
    # Resume + discover, but DO NOT pause (interactive session stays up).
    provider.resume()
    base_url = provider.endpoint()
    if not args.skip_health:
        from atlas_gpu.lifecycle import poll_until_ready

        poll_until_ready(base_url, http_health_check, timeout_s=args.ready_timeout)
    print(base_url)
    if args.write_env:
        write_env(args.write_env, "OLLAMA_BASE_URL", base_url)
        # machine_id drifts on resume — persist the live id so the next session is in sync.
        write_env(args.write_env, "GPU_INSTANCE_ID", str(provider.instance_id))
        log_ok(f"wrote OLLAMA_BASE_URL + GPU_INSTANCE_ID to {args.write_env}")
    _arm_watchdog(args.no_watchdog)
    return 0


def cmd_provision(args: argparse.Namespace) -> int:
    """From-scratch E2E: create a GPU, install Ollama/vLLM, discover + write endpoints."""
    try:
        target = ServeTarget.parse(args.serve)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    provider = make_provider()
    # CLI overrides on top of env-derived CreateSpec.
    if args.gpu:
        provider.create_spec.gpu_type = args.gpu
    if args.storage:
        provider.create_spec.storage_gb = args.storage
    if args.name:
        provider.create_spec.name = args.name

    config = ProvisionConfig.from_env(target)
    try:
        result = provision_from_scratch(
            provider,
            config,
            env_file=args.write_env,
            ready_timeout_s=args.ready_timeout,
            dry_run=args.dry_run,
        )
    except (GpuProviderError, TimeoutError) as e:
        print(f"error: {e}", file=sys.stderr)
        # A create that partially succeeded leaves a billable instance — be loud.
        log_ok("provisioning failed; check `atlas_gpu` / the JarvisLabs console and tear down")
        return 1

    if result.dry_run:
        log_ok(f"[dry-run] serve target: {target.value}; startup script:")
        print(result.script)
        return 0

    if result.ollama_base_url:
        log_ok(f"OLLAMA_BASE_URL={result.ollama_base_url}")
    if result.vllm_base_url:
        log_ok(f"ATLAS_VLLM_BASE_URL={result.vllm_base_url}")
    log_ok(f"instance {result.machine_id} provisioned and serving")
    _arm_watchdog(args.no_watchdog)
    return 0


def cmd_teardown(args: argparse.Namespace) -> int:
    """Pause (default, keeps data) or destroy the provisioned instance; cancel watchdog."""
    LOCK_PATH.unlink(missing_ok=True)
    provider = make_provider()
    try:
        if args.destroy:
            provider.destroy()
            log_ok("GPU instance DESTROYED; watchdog cancelled")
        else:
            provider.pause()
            log_ok("GPU paused; watchdog cancelled")
    except GpuProviderError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    # Cancel the watchdog first (remove the lock so it won't double-pause), then pause.
    LOCK_PATH.unlink(missing_ok=True)
    provider = make_provider()
    provider.pause()
    log_ok("GPU paused; watchdog cancelled")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    if not args.command:
        print("error: `run` needs a command after `--`", file=sys.stderr)
        return 2

    if args.dry_run:
        provider = _EchoProvider()
        skip_health = True
    else:
        provider = make_provider()
        skip_health = args.skip_health

    def body(base_url: str) -> int:
        env = {**os.environ, "OLLAMA_BASE_URL": base_url}
        log_ok(f"running command against {base_url}: {' '.join(args.command)}")
        if args.dry_run:
            return 0
        return subprocess.run(  # noqa: S603
            args.command, env=env
        ).returncode

    try:
        return run_with_gpu(
            provider, body, ready_timeout_s=args.ready_timeout, skip_health=skip_health
        )
    except (GpuProviderError, TimeoutError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def cmd_watchdog(args: argparse.Namespace) -> int:
    lock = Path(args.lock)

    def cancelled() -> bool:
        return not lock.exists()

    if not lock.exists():
        return 0
    deadline = float(lock.read_text().strip() or "0")
    provider = make_provider()
    wd = Watchdog(provider, idle_timeout_s=0)
    wd.deadline = deadline
    fired = wd.run(cancelled=cancelled)
    lock.unlink(missing_ok=True)
    return 0 if fired or cancelled() else 0


class _EchoProvider:
    """Dry-run provider: logs the lifecycle ordering without touching a real GPU."""

    name = "dry-run"

    def resume(self) -> None:
        log_ok("[dry-run] resume()")

    def pause(self) -> None:
        log_ok("[dry-run] pause()  <-- GUARANTEED")

    def status(self) -> str:
        return "running"

    def endpoint(self) -> str:
        return os.environ.get("OLLAMA_BASE_URL", "http://dry-run.local:11434")


def log_ok(msg: str) -> None:
    print(f"[atlas_gpu] {msg}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="atlas_gpu", description="Fail-safe GPU lifecycle helper")
    p.add_argument("--ready-timeout", type=float, default=600.0, help="health-poll timeout (s)")
    sub = p.add_subparsers(dest="cmd", required=True)

    up = sub.add_parser("up", help="resume + discover OLLAMA_BASE_URL + arm watchdog")
    up.add_argument("--write-env", help="env file to update with OLLAMA_BASE_URL")
    up.add_argument("--skip-health", action="store_true")
    up.add_argument("--no-watchdog", action="store_true")
    up.set_defaults(func=cmd_up)

    down = sub.add_parser("down", help="pause + cancel watchdog")
    down.set_defaults(func=cmd_down)

    prov = sub.add_parser(
        "provision", help="from scratch: create GPU + install Ollama/vLLM + write endpoints"
    )
    prov.add_argument(
        "--serve", default="ollama", help="serve target: ollama | vllm | both (default: ollama)"
    )
    prov.add_argument("--gpu", help="GPU type override (e.g. A100, L4); else GPU_TYPE env")
    prov.add_argument("--storage", type=int, help="storage GB override; else GPU_STORAGE_GB env")
    prov.add_argument("--name", help="instance name override")
    prov.add_argument("--write-env", help="env file to update with the discovered endpoints")
    prov.add_argument("--no-watchdog", action="store_true")
    prov.add_argument("--dry-run", action="store_true", help="print plan + startup script only")
    prov.add_argument(
        "--ready-timeout", type=float, default=1800.0, help="endpoint readiness timeout (s)"
    )
    prov.set_defaults(func=cmd_provision)

    teardown = sub.add_parser("teardown", help="pause (default) or --destroy the instance")
    teardown.add_argument(
        "--destroy", action="store_true", help="permanently delete the instance (not just pause)"
    )
    teardown.set_defaults(func=cmd_teardown)

    run = sub.add_parser("run", help="resume -> run -- <cmd> -> guaranteed pause")
    run.add_argument("--skip-health", action="store_true")
    run.add_argument("--dry-run", action="store_true", help="show ordering without a real GPU")
    run.add_argument("command", nargs=argparse.REMAINDER, help="-- <command...>")
    run.set_defaults(func=cmd_run)

    wd = sub.add_parser("_watchdog", help=argparse.SUPPRESS)
    wd.add_argument("--lock", required=True)
    wd.set_defaults(func=cmd_watchdog)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="[atlas_gpu] %(message)s")
    args = build_parser().parse_args(argv)
    # `run` swallows a leading `--` in REMAINDER; strip it.
    if getattr(args, "command", None) and args.command and args.command[0] == "--":
        args.command = args.command[1:]
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
