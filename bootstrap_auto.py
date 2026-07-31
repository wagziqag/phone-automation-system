#!/usr/bin/env python3
'''boot hook: auto-start poller if not running, then execute commands'''
import subprocess, time, os

HOME = os.path.expanduser("~")
WORKDIR = f"{HOME}/phone-automation-system"

# step 1: git pull latest
os.chdir(WORKDIR)
subprocess.run(["git", "pull", "origin", "master"], capture_output=True, timeout=30)

# step 2: start poller if not running
r = subprocess.run(["pgrep", "-f", "poller.py"], capture_output=True, text=True)
if r.returncode != 0:
    subprocess.Popen(["python3", "poller.py"], cwd=WORKDIR, 
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    print("BOOT: poller started")
else:
    print(f"BOOT: poller already running (pid {r.stdout.strip()})")

# step 3: quick status
r = subprocess.run(["pgrep", "-f", "poller"], capture_output=True, text=True)
print(f"poller PID: {r.stdout.strip()}")
