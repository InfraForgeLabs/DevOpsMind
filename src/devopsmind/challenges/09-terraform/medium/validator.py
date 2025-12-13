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

    resources = data.get("resource", [])
    if not resources:
        return False, "No resource block found."

    # resources is list of dicts
    for r in resources:
        if "aws_s3_bucket" in r:
            bucket_res = r["aws_s3_bucket"]
            if "devops_bucket" not in bucket_res:
                return False, "Resource must be named devops_bucket."
            if bucket_res["devops_bucket"].get("bucket") == "devopsmind-bucket":
                return True, "S3 bucket resource is correct!"
            return False, "Bucket name must be devopsmind-bucket."

    return False, "aws_s3_bucket resource not defined."

