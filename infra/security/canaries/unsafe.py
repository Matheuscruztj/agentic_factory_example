import subprocess
import requests

def unsafe(value, conn):
    eval(value)
    subprocess.run(value, shell=True)
    conn.execute(f"SELECT * FROM users WHERE name = '{value}'")
    requests.get(value, verify=False)

def benign(ctx, label, command):
    ctx.execute(f"name-{label}", command)
