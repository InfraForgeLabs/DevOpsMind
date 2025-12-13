#!/usr/bin/env python3
import os
import subprocess

def validate():
    if not os.path.exists("utils.py"):
        return False, "utils.py missing."

    if not os.path.exists("test_utils.py"):
        return False, "test_utils.py is missing. It should be provided by DevOpsMind."

    try:
        out = subprocess.check_output(["pytest", "-q"], stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError as e:
        return False, f"Tests failed:\n{e.output.decode()}"

    if "1 passed" in out or "2 passed" in out or "passed" in out:
        return True, "All tests passed!"
    else:
        return False, f"Unexpected test output: {out}"
