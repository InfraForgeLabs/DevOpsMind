#!/usr/bin/env python3
import os, hcl2

def load_tf(path):
    with open(path) as f:
        return hcl2.load(f)

def validate():
    # Check required files
    for f in ["main.tf", "variables.tf", "outputs.tf"]:
        if not os.path.exists(f):
            return False, f"{f} missing."

    # Load files
    try:
        vars_tf = load_tf("variables.tf")
    except Exception as e:
        return False, f"variables.tf invalid: {e}"
    try:
        main_tf = load_tf("main.tf")
    except Exception as e:
        return False, f"main.tf invalid: {e}"
    try:
        out_tf = load_tf("outputs.tf")
    except Exception as e:
        return False, f"outputs.tf invalid: {e}"

    # Validate variables
    variables = vars_tf.get("variable", [])
    var_names = []
    for v in variables:
        var_names += list(v.keys())
    if "instance_type" not in var_names or "ami" not in var_names:
        return False, "variables.tf must define 'instance_type' and 'ami'."

    # Validate EC2 resource
    resources = main_tf.get("resource", [])
    found = None
    for r in resources:
        if "aws_instance" in r and "dev" in r["aws_instance"]:
            found = r["aws_instance"]["dev"]
            break

    if not found:
        return False, "Resource aws_instance.dev missing."

    if found.get("instance_type") != "${var.instance_type}" and found.get("instance_type") != "var.instance_type":
        return False, "instance_type must reference var.instance_type."

    if found.get("ami") != "${var.ami}" and found.get("ami") != "var.ami":
        return False, "ami must reference var.ami."

    # Validate output
    outputs = out_tf.get("output", [])
    out_names = [list(o.keys())[0] for o in outputs]
    if "instance_id" not in out_names:
        return False, "outputs.tf must define output instance_id."

    # Check its value
    for o in outputs:
        if "instance_id" in o:
            if o["instance_id"].get("value") not in ("aws_instance.dev.id", "${aws_instance.dev.id}"):
                return False, "Output instance_id must reference aws_instance.dev.id."

    return True, "Hard Terraform challenge is correct!"

