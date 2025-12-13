#!/usr/bin/env python3
import os
import subprocess
import sys
import re

def run(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()

def validate():
    if not os.path.isdir(".git"):
        return False, ".git not found."

    # ensure main exists
    try:
        run(["git", "rev-parse", "--verify", "main"])
    except subprocess.CalledProcessError:
        return False, "Branch 'main' does not exist."

    # check login.txt exists on main
    try:
        # get file content from main
        content = run(["git", "show", "main:login.txt"])
    except subprocess.CalledProcessError:
        return False, "login.txt not present on main. Make sure you squash-merged feature/login into main."

    if content.strip() != "login implemented":
        return False, "login.txt content on main must be exactly: login implemented"

    # ensure there's at least one commit on main with message containing 'Add auth feature'
    try:
        log = run(["git", "log", "main", "--pretty=%H %s"])
    except subprocess.CalledProcessError as e:
        return False, f"Failed to read git log: {e.output.decode().strip()}"

    found = False
    for line in log.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2 and "Add auth feature" in parts[1]:
            found = True
            break
    if not found:
        return False, "No commit message on main contains the required substring: 'Add auth feature'"

    # verify there are no merge commits on main: commit parents count should be 1 for all commits reachable from main
    try:
        revs = run(["git", "rev-list", "--parents", "main"])
    except subprocess.CalledProcessError as e:
        return False, f"Failed to list commits: {e.output.decode().strip()}"

    for line in revs.splitlines():
        parts = line.split()
        if len(parts) > 2:
            # commit + more than one parent -> merge commit
            return False, "Found a merge commit on main. The history must not contain merge commits introduced by this operation."

    return True, "Squash-merge validated: main contains login.txt, message present, and no merge commits."

