"""Serve the site on the local network so an iPad can open the handwriting
recorder at /_draw/ and save straight into handwriting.json in the repo.

    python3 _draw/serve.py
"""

import json
import socket
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = 8742
ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "handwriting.json"
MAX_BYTES = 2_000_000


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/_draw/save":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", 0))
        if not 0 < length <= MAX_BYTES:
            self.send_error(413)
            return

        try:
            data = json.loads(self.rfile.read(length))
            assert isinstance(data["strokes"], list) and data["strokes"]
            assert data["width"] > 0 and data["height"] > 0
        except (ValueError, KeyError, TypeError, AssertionError):
            self.send_error(400, "Not a handwriting recording")
            return

        OUTPUT.write_text(json.dumps(data, separators=(",", ":")) + "\n")
        self.send_response(204)
        self.end_headers()
        print(f"Saved {len(data['strokes'])} strokes to {OUTPUT.name}")


def lan_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", PORT), partial(Handler, directory=str(ROOT)))
    ip = lan_ip()
    print(f"On your iPad, open   http://{ip}:{PORT}/_draw/")
    print(f"Preview the site at  http://{ip}:{PORT}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
