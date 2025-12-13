#!/usr/bin/env python3
import os
import subprocess

def validate():
    if not os.path.exists("metrics.txt"):
        return False, "metrics.txt missing (provided by challenge)."
    if not os.path.exists("metrics.py"):
        return False, "metrics.py missing."

    # Prepare test metrics file
    with open("metrics.txt", "w") as f:
        f.write("latency_ms=100\nlatency_ms=200\nlatency_ms=300\n")

    try:
        out = subprocess.check_output(["python3", "metrics.py"], stderr=subprocess.STDOUT).decode().strip()
    except subprocess.CalledProcessError as e:
        return False, f"Script crashed: {e.output.decode().strip()}"

    try:
        val = float(out)
    except:
        return False, f"Output must be numeric only, got: {repr(out)}"

    expected = (100 + 200 + 300) / 3
    if abs(val - expected) < 0.001:
        return True, "Average latency computed correctly!"
    else:
        return False, f"Expected {expected}, got {val}"

