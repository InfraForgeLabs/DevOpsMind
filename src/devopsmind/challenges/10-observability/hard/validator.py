#!/usr/bin/env python3
import os
import subprocess

def validate():
    if not os.path.exists("alert.py"):
        return False, "alert.py missing."

    # Create test CPU metrics
    with open("cpu.txt", "w") as f:
        f.write("cpu=20\ncpu=30\ncpu=90\n")

    try:
        out = subprocess.check_output(["python3", "alert.py"], stderr=subprocess.STDOUT).decode().strip()
    except subprocess.CalledProcessError as e:
        return False, f"Script crashed: {e.output.decode().strip()}"

    if out == "ALERT":
        return True, "Alert engine works correctly for high CPU!"
    return False, f"Expected ALERT, got {out}"

