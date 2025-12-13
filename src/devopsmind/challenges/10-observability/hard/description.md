Implement a tiny alert evaluation engine.

Given a file cpu.txt structured like:

cpu=91
cpu=45
cpu=88
...

Task:
- Create alert.py
- Script must:
    - Read cpu.txt
    - Extract all cpu values (integers)
    - If ANY cpu value > 80 → print exactly: ALERT
    - Else print exactly: OK
    - No extra text or formatting allowed

This challenge teaches core alert evaluation logic similar to Prometheus alert rules.
