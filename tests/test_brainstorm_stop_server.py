"""stop-server.sh must treat a killed-but-unreaped (zombie) server as stopped.

`kill -0` succeeds on a zombie, so a server whose parent has not reaped it yet
read as "still running": stop-server.sh waited its full grace period, sent
SIGKILL to a dead process and then reported {"status": "failed"} although the
server was gone.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOP = ROOT / "plugins/tcs-workflow/skills/brainstorm/scripts/stop-server.sh"

# A parent that starts a child and never waits for it: once the child is
# killed it stays a zombie until this parent exits.
NON_REAPING_PARENT = (
    "import subprocess, sys, time\n"
    "p = subprocess.Popen(['sleep', '300'])\n"
    "print(p.pid, flush=True)\n"
    "time.sleep(60)\n"
)


def _state(pid):
    out = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                         capture_output=True, text=True)
    return out.stdout.strip()


def test_a_zombie_server_counts_as_stopped(tmp_path):
    parent = subprocess.Popen([sys.executable, "-c", NON_REAPING_PARENT],
                              stdout=subprocess.PIPE, text=True)
    try:
        child = int(parent.stdout.readline())
        session = tmp_path / "session"
        (session / "state").mkdir(parents=True)
        (session / "state" / "server.pid").write_text(f"{child}\n")

        started = time.time()
        result = subprocess.run(["bash", str(STOP), str(session)],
                                capture_output=True, text=True, timeout=30)
        elapsed = time.time() - started

        assert _state(child).startswith("Z"), "fixture did not leave a zombie"
        assert json.loads(result.stdout) == {"status": "stopped"}, result.stdout
        assert result.returncode == 0
        assert not (session / "state" / "server.pid").exists()
        assert elapsed < 1.5, f"waited {elapsed:.1f}s for a dead process"
    finally:
        parent.kill()
        parent.wait()
