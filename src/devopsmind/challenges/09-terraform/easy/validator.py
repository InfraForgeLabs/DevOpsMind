#!/usr/bin/env python3
import os, hcl2

def validate():
    if not os.path.exists("main.tf"):
        return False, "main.tf is missing."

    try:
        with open("main.tf") as f:
            data = hcl2.load(f)
    except Exception as e:
        return False, f"Invalid HCL: {e}"

    providers = data.get("provider", [])
    if not providers:
        return False, "Provider block missing."

    # providers is a list of dicts: [{"aws": {...}}]
    for p in providers:
        if "aws" in p:
            region = p["aws"].get("region")
            if region == "us-east-1":
                return True, "Terraform provider block is correct!"
            else:
                return False, "Provider aws must have region = 'us-east-1'."

    return False, "Provider 'aws' not found."

