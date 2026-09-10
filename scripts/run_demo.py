"""Start the whole demo with one command.

    python -m scripts.run_demo

Brings up the signup page and the Telegram bot together, and picks the model
for you: it makes one real Bedrock call first, and if that works you get the
real thing. If it doesn't, it says exactly why and falls back to the offline
stand-in so the demo still runs — loudly, because a rule-based stand-in must
never be mistaken for the model on stage.

    --fake      skip the check, force the stand-in
    --real      refuse to start unless Bedrock actually answers
    --port N    signup page port (default 8000)

Ctrl-C stops both.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chest.config import BEDROCK_MODEL_ID, PUBLIC_URL  # noqa: E402

RESET, DIM, GREEN, YELLOW, RED = "\033[0m", "\033[2m", "\033[32m", "\033[33m", "\033[31m"


def model_is_live() -> tuple[bool, str]:
    """One real call. Returns (ok, what to tell the human)."""
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_model.py")],
        capture_output=True, text=True,
    )
    output = proc.stdout.strip()
    if proc.returncode == 0:
        return True, output.splitlines()[-1].strip()
    # check_model.py already translates the failure; keep its diagnosis.
    detail = [ln for ln in output.splitlines() if ln.strip().startswith(("FAIL", "  "))]
    return False, "\n".join(detail) or output


def pump(stream, prefix: str, color: str) -> None:
    for line in iter(stream.readline, ""):
        print(f"{color}{prefix}{RESET} {line.rstrip()}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true", help="force the offline stand-in")
    ap.add_argument("--real", action="store_true", help="refuse to start without Bedrock")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    env = dict(os.environ)

    if args.fake:
        fake = True
        print(f"{YELLOW}forcing the offline stand-in (--fake){RESET}")
    else:
        print(f"{DIM}checking {BEDROCK_MODEL_ID}...{RESET}")
        ok, detail = model_is_live()
        fake = not ok
        if ok:
            print(f"{GREEN}Bedrock is answering.{RESET} {detail}")
        elif args.real:
            print(f"{RED}Bedrock is not answering, and --real was passed. Not starting.{RESET}")
            print(detail)
            return 1
        else:
            print(f"{RED}Bedrock is not answering:{RESET}\n{detail}")
            print(f"\n{YELLOW}Falling back to the offline stand-in. It matches regexes and "
                  f"calls the obvious tool.{RESET}")
            print(f"{YELLOW}It proves the plumbing and NOTHING about the model. Do not "
                  f"present this as the agent.{RESET}")

    if fake:
        env["CHEST_FAKE_MODEL"] = "1"
    else:
        env.pop("CHEST_FAKE_MODEL", None)

    procs = [
        ("web ", GREEN, [sys.executable, "-u", "-m", "uvicorn", "chest.channels.webhook:app",
                         "--host", "127.0.0.1", "--port", str(args.port)]),
        ("bot ", YELLOW, [sys.executable, "-u", "-m", "scripts.telegram_poll"]),
    ]
    running: list[subprocess.Popen] = []
    for prefix, color, cmd in procs:
        proc = subprocess.Popen(
            cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1,
        )
        running.append(proc)
        threading.Thread(target=pump, args=(proc.stdout, prefix, color), daemon=True).start()

    print(f"\n  signup: {PUBLIC_URL if ':' in PUBLIC_URL.split('//')[-1] else PUBLIC_URL}")
    print(f"  mode:   {'OFFLINE STAND-IN' if fake else 'live Bedrock — ' + BEDROCK_MODEL_ID}")
    print(f"  {DIM}ctrl-c to stop both{RESET}\n")

    try:
        while True:
            for proc in running:
                if proc.poll() is not None:
                    print(f"{RED}a process exited ({proc.returncode}); shutting down{RESET}")
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nstopping...")
    finally:
        for proc in running:
            proc.terminate()
        for proc in running:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
