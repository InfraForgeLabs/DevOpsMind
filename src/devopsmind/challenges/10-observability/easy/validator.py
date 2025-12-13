#!/usr/bin/env python3
import os

def validate():
    if not os.path.exists("app.log"):
        return False, "app.log missing (provided by challenge)."
    if not os.path.exists("errors.log"):
        return False, "errors.log missing."

    with open("app.log") as f:
        expected = [l for l in f if "ERROR" in l]

    with open("errors.log") as f:
        actual = f.readlines()

    if expected == actual:
        return True, "Correct log filtering!"
    return False, "errors.log does not match the expected ERROR lines."

