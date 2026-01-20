import datetime
import os
import sys
import uuid


def log(msg):
    print(msg)
    with open("verification_result.txt", "a") as f:
        f.write(str(msg) + "\n")

run_id = str(uuid.uuid4())
log(f"RUN_ID: {run_id}")
log(f"TIME: {datetime.datetime.now()}")
log(f"CWD: {os.getcwd()}")
log(f"PYTHON: {sys.executable}")

try:
    log("\n--- debug_runner.py content (first 5 lines) ---")
    with open("debug_runner.py", "r") as f:
        for _ in range(5):
            log(f.readline().strip())
except Exception as e:
    log(f"Error reading debug_runner.py: {e}")

try:
    log("\n--- debug_log.txt stats ---")
    s = os.stat("debug_log.txt")
    log(f"Size: {s.st_size}")
    log(f"Mtime: {datetime.datetime.fromtimestamp(s.st_mtime)}")
except Exception as e:
    log(f"Error stat debug_log.txt: {e}")

log("\nDONE")
