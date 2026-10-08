import json
import socket
import struct
import subprocess
import sys
from pathlib import Path

SERVER = Path(__file__).resolve().parent.parent
PYTHON = SERVER / ".venv" / "Scripts" / "python.exe"
LOG = SERVER / "data" / "server.log"
PORT = 7331
IDLE_MINUTES = 15
HIDDEN = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP


def read_message():
    size = sys.stdin.buffer.read(4)
    if len(size) < 4:
        return {}
    return json.loads(sys.stdin.buffer.read(struct.unpack("<I", size)[0]))


def send_message(message):
    data = json.dumps(message).encode()
    sys.stdout.buffer.write(struct.pack("<I", len(data)) + data)
    sys.stdout.buffer.flush()


def running(port=PORT):
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def start(port=PORT):
    LOG.parent.mkdir(exist_ok=True)
    log = open(LOG, "a", encoding="utf-8")
    command = [str(PYTHON), str(SERVER / "app.py"), "--port", str(port), "--idle", str(IDLE_MINUTES)]
    options = {"cwd": SERVER.parent, "stdin": subprocess.DEVNULL, "stdout": log, "stderr": subprocess.STDOUT}
    try:
        subprocess.Popen(command, creationflags=HIDDEN | subprocess.CREATE_BREAKAWAY_FROM_JOB, **options)
    except OSError:
        subprocess.Popen(command, creationflags=HIDDEN, **options)


if __name__ == "__main__":
    read_message()
    if running():
        send_message({"status": "running"})
    else:
        start()
        send_message({"status": "starting"})
