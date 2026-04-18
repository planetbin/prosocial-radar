#!/usr/bin/env python3
"""
Daily scheduler daemon for Prosocial Research Radar.

Runs run_radar.py every day at a configured time (default 08:00).
Logs to logs/scheduler.log.

Usage:
    python scheduler.py             # run daily at 08:00 (default)
    python scheduler.py --time 07:30
    python scheduler.py --run-now   # trigger once immediately, then schedule

Run in background:
    nohup python scheduler.py > logs/scheduler.log 2>&1 &
    echo $! > logs/scheduler.pid
"""

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import schedule

LOG_DIR  = Path("logs")
LOG_FILE = LOG_DIR / "scheduler.log"
PID_FILE = LOG_DIR / "scheduler.pid"
WORKSPACE = Path(__file__).parent


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def run_radar():
    """Execute the full radar pipeline as a subprocess."""
    log = logging.getLogger("scheduler")
    log.info("=" * 60)
    log.info("Scheduled run starting...")

    cmd = [sys.executable, str(WORKSPACE / "run_radar.py"), "--top", "8"]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(WORKSPACE),
            capture_output=False,   # let output stream to log
            timeout=600,
        )
        if result.returncode == 0:
            log.info("Run completed successfully.")
        else:
            log.error("Run exited with code %d", result.returncode)
    except subprocess.TimeoutExpired:
        log.error("Run timed out after 600 seconds.")
    except Exception as exc:
        log.error("Run failed: %s", exc)


def write_pid():
    LOG_DIR.mkdir(exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def parse_args():
    p = argparse.ArgumentParser(description="Prosocial Radar daily scheduler")
    p.add_argument("--time",    default="08:00",
                   help="Daily run time in HH:MM 24h format (default: 08:00)")
    p.add_argument("--run-now", action="store_true",
                   help="Execute once immediately, then keep scheduled")
    return p.parse_args()


def main():
    setup_logging()
    args = parse_args()
    log  = logging.getLogger("scheduler")

    write_pid()

    log.info("Prosocial Research Radar — Scheduler started (PID %d)", os.getpid())
    log.info("Scheduled daily run time: %s", args.time)
    log.info("PID file: %s", PID_FILE)
    log.info("Log file: %s", LOG_FILE)

    # Schedule daily job
    schedule.every().day.at(args.time).do(run_radar)
    log.info("Next run: %s", schedule.next_run())

    # Optional immediate trigger
    if args.run_now:
        log.info("--run-now flag set: executing immediately.")
        run_radar()

    # Handle SIGTERM gracefully
    def _shutdown(signum, frame):
        log.info("Received signal %d — shutting down scheduler.", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Main loop
    while True:
        schedule.run_pending()
        # Log next run time once per hour to confirm daemon is alive
        now = datetime.now()
        if now.minute == 0 and now.second < 10:
            log.info("Scheduler alive. Next run: %s", schedule.next_run())
        time.sleep(10)


if __name__ == "__main__":
    main()
