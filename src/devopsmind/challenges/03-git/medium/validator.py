#!/usr/bin/env python3
import os
import subprocess
import sys

def run(cmd):
    return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()

def branch_exists(branch):
    out = run(["git", "branch", "--list", branch])
    return bool(out.strip())

def get_commit_parents(rev):
    out = run(["git", "rev-list", "--parents", "-n", "1", rev])
    parts = out.split()
    # first part is commit, rest are parents
    return parts[1:]

def file_in_commit(commit, path):
    try:
        ls = run(["git", "show", f"{commit}:{path}"])
        return True, ls
    except subprocess.CalledProcessError:
        return False, None

def validate():
    if not os.path.isdir(".git"):
        return False, ".git not found."

    if not branch_exists("feature/login"):
        return False, "Branch 'feature/login' not found. Create it with: git checkout -b feature/login"

    if not os.path.exists("login.txt"):
        return False, "login.txt missing in working directory."

    with open("login.txt") as f:
        content = f.read().strip()
    if content != "login implemented":
        return False, "login.txt content must be exactly: login implemented"

    # determine the tip commit of feature/login
    try:
        tip = run(["git", "rev-parse", "feature/login"])
    except subprocess.CalledProcessError:
        return False, "Failed to resolve feature/login tip."

    parents = get_commit_parents(tip)
    if len(parents) != 1:
        return False, "The tip of feature/login appears to be a merge commit (expected single parent). Rebase onto main instead of merging."

    # ensure the commit actually contains login.txt
    present, blob = file_in_commit(tip, "login.txt")
    if not present:
        return False, "Tip commit of feature/login does not contain login.txt. Make sure you committed the file on the feature branch."

    if blob.strip() != "login implemented":
        return False, "login.txt content in commit doesn't match expected content."

    return True, "Feature branch and rebase look correct."

