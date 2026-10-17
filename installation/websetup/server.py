"""Explicit local-only HTTP status server; no installation actions are exposed."""
import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .preflight import build_report

_ALLOWED_AUTHORITY = re.compile(r"(?i)(?:localhost|127\.0\.0\.1|\[::1\])(?::([0-9]{1,5}))?\Z")


def _valid_authority(authority):
    match = _ALLOWED_AUTHORITY.fullmatch(authority)
    if match is None:
        return False
    port = match.group(1)
    return port is None or 1 <= int(port) <= 65535


def _trusted_origin(headers, host):
    origins = headers.get_all("Origin", [])
    if not origins:
        return True
    if len(origins) != 1:
        return False
    try:
        origin = urlsplit(origins[0])
    except ValueError:
        return False
    return (origin.scheme.lower() == "http" and _valid_authority(origin.netloc)
            and origin.netloc.lower() == host.lower()
            and not origin.path and not origin.query and not origin.fragment)


def _trusted_target(target):
    if not target.startswith("/") or target.startswith("//") or "#" in target:
        return None
    try:
        parsed = urlsplit(target)
    except ValueError:
        return None
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
        return None
    return parsed.path


def _request_path(handler):
    hosts = handler.headers.get_all("Host", [])
    if len(hosts) != 1 or not _valid_authority(hosts[0]):
        return None
    if not _trusted_origin(handler.headers, hosts[0]):
        return None
    return _trusted_target(handler.path)


def _reply(handler, status, content_type, body):
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    policy = "default-src 'self'; connect-src 'self'; style-src 'unsafe-inline'; "
    policy += "script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'"
    handler.send_header("Content-Security-Policy", policy)
    handler.end_headers()
    handler.wfile.write(body)


def _page_response(handler, page_path):
    try:
        with page_path.open("rb") as page:
            body = page.read(32769)
        if len(body) > 32768:
            raise OSError
    except OSError:
        _reply(handler, 500, "text/plain; charset=utf-8", "Statusseite nicht verfügbar.\n".encode("utf-8"))
        return
    _reply(handler, 200, "text/html; charset=utf-8", body)


def _report_response(handler, report_factory):
    try:
        report = report_factory()
        body = json.dumps(report, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    except Exception:
        report = {"schema": "websetup.preflight.v1", "error": "Statusdaten sind nicht verfügbar."}
        body = json.dumps(report).encode("utf-8")
    _reply(handler, 200, "application/json; charset=utf-8", body)


def _handler_for(root, report_factory):
    page_path = root / "installation" / "websetup" / "index.html"

    class Handler(BaseHTTPRequestHandler):
        server_version = "LocalPreflight"
        sys_version = ""

        def log_message(self, _format, *_args):
            return

        def _error(self, status, message):
            _reply(self, status, "text/plain; charset=utf-8", (message + "\n").encode("utf-8"))

        def send_error(self, code, message=None, explain=None):
            del message, explain
            self._error(code, "Anfrage abgewiesen.")

        def do_GET(self):
            path = _request_path(self)
            if path is None:
                self._error(400, "Anfrage abgewiesen.")
            elif path == "/":
                _page_response(self, page_path)
            elif path == "/api/preflight":
                _report_response(self, report_factory)
            else:
                self._error(404, "Nicht gefunden.")

        def _method_not_allowed(self):
            self._error(405, "Methode nicht zulässig.")

        do_POST = _method_not_allowed
        do_PUT = _method_not_allowed
        do_HEAD = _method_not_allowed
        do_DELETE = _method_not_allowed
        do_OPTIONS = _method_not_allowed
        do_PATCH = _method_not_allowed

    return Handler


class _LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False


def make_server(root=Path.cwd(), port=8765, report_factory=None):
    """Create a fixed-route server bound exclusively to the IPv4 loopback."""
    root = Path(root)
    report_factory = report_factory or (lambda: build_report(root=root))
    return _LocalServer(("127.0.0.1", port), _handler_for(root, report_factory))


def main():
    parser = argparse.ArgumentParser(description="Schreibgeschützte Einrichtungsdaten lokal anzeigen.")
    parser.add_argument("--port", type=int, default=8765, help="Lokaler Port (Standard: 8765)")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Der Port muss zwischen 1024 und 65535 liegen.")
    httpd = make_server(port=args.port)
    print("Lokale Statusseite: http://127.0.0.1:%d/" % args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
