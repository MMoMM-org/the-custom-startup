"""Security tests for the brainstorm companion server (#269).

plugins/tcs-workflow/skills/brainstorm/scripts/server.cjs serves the screens the
agent writes and records the user's clicks to $STATE_DIR/events, which the agent
reads back as user input. These tests start the real server and check that:

1. every HTTP endpoint and the WebSocket upgrade require the per-session key,
   and the upgrade also rejects a foreign Origin (cross-site WebSocket hijacking);
2. a frame that declares a payload above the cap is refused without buffering it;
3. screen content is inserted literally (`$&` and friends are not expanded).
"""

import base64
import json
import os
import shutil
import socket
import stat
import struct
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "plugins/tcs-workflow/skills/brainstorm/scripts/server.cjs"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node required")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def _get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with _opener.open(req, timeout=5) as resp:
            return resp.status, dict(resp.headers), resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers), err.read().decode()


@pytest.fixture
def server(tmp_path):
    port = _free_port()
    session = tmp_path / "session"
    env = dict(os.environ, BRAINSTORM_DIR=str(session), BRAINSTORM_PORT=str(port))
    env.pop("BRAINSTORM_OWNER_PID", None)
    proc = subprocess.Popen(
        ["node", str(SERVER)], env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    info_file = session / "state" / "server-info"
    deadline = time.time() + 10
    while not info_file.exists() and time.time() < deadline:
        time.sleep(0.05)
    assert info_file.exists(), "server did not start"
    info = json.loads(info_file.read_text())
    yield {
        "proc": proc, "port": port, "info": info, "info_file": info_file,
        "content": session / "content", "events": session / "state" / "events",
    }
    proc.terminate()
    proc.wait(timeout=5)


def _key(srv):
    url = srv["info"]["url"]
    assert "?key=" in url, url
    return url.split("?key=", 1)[1]


def _cookie(srv):
    status, headers, _ = _get(srv["info"]["url"])
    assert status == 302
    return headers["Set-Cookie"].split(";", 1)[0]


def _ws_connect(srv, headers):
    sock = socket.create_connection(("127.0.0.1", srv["port"]), timeout=5)
    lines = [
        "GET / HTTP/1.1",
        f"Host: localhost:{srv['port']}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        "Sec-WebSocket-Key: " + base64.b64encode(os.urandom(16)).decode(),
        "Sec-WebSocket-Version: 13",
    ] + [f"{k}: {v}" for k, v in headers.items()]
    sock.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
    try:
        reply = sock.recv(4096)
    except (ConnectionResetError, socket.timeout):
        reply = b""
    return sock, reply


def _masked_frame(opcode, payload, declared_len=None):
    length = len(payload) if declared_len is None else declared_len
    head = bytes([0x80 | opcode])
    if length < 126:
        head += bytes([0x80 | length])
    elif length < 65536:
        head += bytes([0x80 | 126]) + struct.pack(">H", length)
    else:
        head += bytes([0x80 | 127]) + struct.pack(">Q", length)
    mask = os.urandom(4)
    return head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload))


def _recv_all(sock):
    data = b""
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
    except (ConnectionResetError, socket.timeout):
        pass
    return data


def test_server_info_carries_the_key_and_is_owner_only(server):
    assert len(_key(server)) >= 32
    assert stat.S_IMODE(server["info_file"].stat().st_mode) == 0o600


def test_http_requires_the_key(server):
    base = f"http://127.0.0.1:{server['port']}"
    assert _get(base + "/")[0] == 403
    assert _get(base + "/?key=wrong")[0] == 403
    assert _get(base + "/files/x.png")[0] == 403
    status, headers, _ = _get(server["info"]["url"])
    assert status == 302 and headers["Location"] == "/"
    assert "HttpOnly" in headers["Set-Cookie"]
    assert "SameSite=Strict" in headers["Set-Cookie"]
    assert _get(base + "/", {"Cookie": _cookie(server)})[0] == 200


def test_websocket_without_key_is_refused(server):
    sock, reply = _ws_connect(server, {})
    sock.close()
    assert not reply.startswith(b"HTTP/1.1 101")


def test_websocket_from_a_foreign_origin_is_refused(server):
    sock, reply = _ws_connect(
        server, {"Cookie": _cookie(server), "Origin": "http://evil.example"}
    )
    sock.close()
    assert not reply.startswith(b"HTTP/1.1 101")


def test_websocket_with_key_and_own_origin_records_events(server):
    origin = f"http://localhost:{server['port']}"
    sock, reply = _ws_connect(server, {"Cookie": _cookie(server), "Origin": origin})
    assert reply.startswith(b"HTTP/1.1 101")
    sock.sendall(_masked_frame(0x1, json.dumps({"choice": "a"}).encode()))
    deadline = time.time() + 5
    while not server["events"].exists() and time.time() < deadline:
        time.sleep(0.05)
    sock.close()
    assert json.loads(server["events"].read_text())["choice"] == "a"


def test_oversized_frame_is_refused_without_buffering(server):
    origin = f"http://localhost:{server['port']}"
    sock, reply = _ws_connect(server, {"Cookie": _cookie(server), "Origin": origin})
    assert reply.startswith(b"HTTP/1.1 101")
    # Declares 1 TiB but sends only a few bytes: an unbounded parser would wait
    # for (and buffer) the rest; the capped one closes with 1009 at once.
    sock.sendall(_masked_frame(0x1, b"xx", declared_len=1 << 40))
    data = _recv_all(sock)
    sock.close()
    assert data[:1] == bytes([0x88]), data
    assert struct.unpack(">H", data[2:4])[0] == 1009
    assert server["proc"].poll() is None


def test_screen_content_is_inserted_literally(server):
    (server["content"] / "screen.html").write_text(
        '<p id="t">cost $& and $1 and $$ and $` end</p>'
    )
    time.sleep(0.3)
    _, _, body = _get(
        f"http://127.0.0.1:{server['port']}/", {"Cookie": _cookie(server)}
    )
    assert "cost $& and $1 and $$ and $` end" in body
    assert "<!-- CONTENT -->" not in body
