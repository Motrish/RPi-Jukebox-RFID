"""Small loopback-only HTTP surface for the existing library catalog."""

import json
import re
import secrets
import socket
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from jukebox.contracts import validate_identifier


_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_DECIMAL_RE = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_MAX_TARGET_CHARS = 2048
_MAX_HEADER_BYTES = 8192
_MAX_HEADERS = 32
_MAX_RESPONSE_BYTES = 256 * 1024
_SOCKET_TIMEOUT_SECONDS = 5
_TOKEN_TTL_SECONDS = 900
_JSON_CONTENT_TYPE = "application/json;charset=utf-8"
_ERRORS = {
    "INVALID_REQUEST": "The request is invalid.",
    "UNAUTHORIZED": "Read authorization is required.",
    "NOT_FOUND": "The requested library item was not found.",
    "METHOD_NOT_ALLOWED": "The request method is not allowed.",
    "SERVICE_UNAVAILABLE": "The library service is unavailable.",
}


def _valid_token(value):
    return isinstance(value, str) and _TOKEN_RE.fullmatch(value) is not None


def make_read_authorizer(token, clock=None):
    """Return a credential checker valid for 900 monotonic seconds."""
    if not _valid_token(token):
        raise ValueError("token must be a 43-character URL-safe value")
    if clock is None:
        clock = time.monotonic
    if not callable(clock):
        raise TypeError("clock must be callable")
    started = clock()

    def authorize(credential):
        candidate = credential if isinstance(credential, str) else ""
        try:
            matches = secrets.compare_digest(candidate, token)
            elapsed = clock() - started
        except Exception:
            return False
        return matches and 0 <= elapsed < _TOKEN_TTL_SECONDS

    return authorize


def _validate_identifier(value):
    try:
        return validate_identifier(value)
    except Exception:
        raise ValueError("invalid identifier") from None


def _project_media(value):
    if not isinstance(value, dict):
        raise ValueError("invalid catalog record")
    if set(value) != {"libraryId", "displayName", "availability"}:
        raise ValueError("invalid catalog record")
    library_id = _validate_identifier(value["libraryId"])
    display_name = value["displayName"]
    if not isinstance(display_name, str) or not display_name:
        raise ValueError("invalid catalog record")
    try:
        encoded_name = display_name.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("invalid catalog record") from None
    if len(encoded_name) > 255 or any(
        ord(char) < 32 or ord(char) == 127 for char in display_name
    ):
        raise ValueError("invalid catalog record")
    availability = value["availability"]
    if availability not in {"AVAILABLE", "MISSING", "UNKNOWN"}:
        raise ValueError("invalid catalog record")
    return {
        "libraryId": library_id,
        "displayName": display_name,
        "availability": availability,
    }


def _project_list(value, limit):
    if not isinstance(value, dict) or set(value) != {"items", "nextCursor"}:
        raise ValueError("invalid catalog list")
    records = value["items"]
    if not isinstance(records, list) or len(records) > limit:
        raise ValueError("invalid catalog list")
    items = [_project_media(record) for record in records]
    cursor = value["nextCursor"]
    if cursor is not None:
        cursor = _validate_identifier(cursor)
        if not items or cursor != items[-1]["libraryId"]:
            raise ValueError("invalid catalog list")
    return {"items": items, "nextCursor": cursor}


def _target_parts(target):
    if (
        not isinstance(target, str)
        or not target
        or len(target) > _MAX_TARGET_CHARS
        or not target.startswith("/")
        or target.startswith("//")
        or "#" in target
        or "%" in target
        or "\\" in target
        or any(ord(char) < 33 or ord(char) > 126 for char in target)
    ):
        raise ValueError("invalid target")

    if target.count("?") > 1:
        raise ValueError("invalid target")
    if "?" in target:
        path, query = target.split("?", 1)
    else:
        path, query = target, None
    if any(part in {".", ".."} for part in path.split("/")):
        raise ValueError("invalid target")
    return path, query


def _parse_list_query(query):
    limit = 50
    cursor = None
    if query is None:
        return limit, cursor
    if not query:
        raise ValueError("invalid query")
    seen = set()
    for pair in query.split("&"):
        if not pair or pair.count("=") != 1:
            raise ValueError("invalid query")
        name, raw_value = pair.split("=", 1)
        if name not in {"limit", "cursor"} or name in seen or not raw_value:
            raise ValueError("invalid query")
        seen.add(name)
        if name == "limit":
            if _DECIMAL_RE.fullmatch(raw_value) is None:
                raise ValueError("invalid query")
            limit = int(raw_value)
            if not 1 <= limit <= 200:
                raise ValueError("invalid query")
        else:
            cursor = _validate_identifier(raw_value)
    return limit, cursor


def _parse_target(target):
    """Parse the two allowed origin-form targets without URL normalization."""
    path, query = _target_parts(target)
    if path == "/api/library/media":
        limit, cursor = _parse_list_query(query)
        return "list", limit, cursor

    prefix = "/api/library/media/"
    if path.startswith(prefix):
        if query is not None:
            raise ValueError("invalid target")
        library_id = path[len(prefix):]
        if not library_id or "/" in library_id:
            raise ValueError("invalid target")
        return "get", _validate_identifier(library_id), None
    raise LookupError("unknown target")


class _LibraryHTTPServer(HTTPServer):
    address_family = socket.AF_INET
    request_queue_size = 4

    def __init__(self, catalog, read_authorizer, port, origin_host):
        self.catalog = catalog
        self.read_authorizer = read_authorizer
        self.origin_host = origin_host
        super().__init__(("127.0.0.1", port), _LibraryRequestHandler)
        self.expected_authority = "{}:{}".format(
            origin_host, self.server_address[1]
        )
        self.expected_origin = "http://{}".format(self.expected_authority)

    def get_request(self):
        request, client_address = super().get_request()
        request.settimeout(_SOCKET_TIMEOUT_SECONDS)
        return request, client_address

    def handle_error(self, request, client_address):
        # BaseServer prints tracebacks; requests must not reach logs.
        return None


def make_server(catalog, read_authorizer, port, origin_host="127.0.0.1"):
    """Create a serial IPv4-loopback server around an injected catalog."""
    if origin_host not in {"127.0.0.1", "localhost"}:
        raise ValueError("origin_host must be a loopback name")
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    if not callable(read_authorizer):
        raise TypeError("read_authorizer must be callable")
    if catalog is None:
        raise TypeError("catalog is required")
    return _LibraryHTTPServer(catalog, read_authorizer, port, origin_host)


class _LibraryRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"
    server_version = "LibraryReadAPI"
    sys_version = ""

    def version_string(self):
        return self.server_version

    def log_message(self, format_string, *args):
        return None

    def send_error(self, code, message=None, explain=None):
        status = 405 if code == 501 else code
        if status == 405:
            self._send_json(
                status, "METHOD_NOT_ALLOWED", head=self.command == "HEAD"
            )
        else:
            self._send_json(
                400, "INVALID_REQUEST", head=self.command == "HEAD"
            )

    def do_GET(self):
        self.close_connection = True
        token = None
        try:
            self._check_request_limits()
            self._check_host_and_origin()
            token = self._bearer_credential()
            if token is None or not self._authorized(token):
                self._send_json(401, "UNAUTHORIZED")
                return

            try:
                operation = _parse_target(self._raw_target())
            except LookupError:
                status, payload = 404, self._error_document("NOT_FOUND")
            except ValueError:
                status, payload = 400, self._error_document("INVALID_REQUEST")
            else:
                try:
                    status, payload = self._read(operation)
                except Exception:
                    status, payload = (
                        503,
                        self._error_document("SERVICE_UNAVAILABLE"),
                    )

            self._write_json(status, payload, credential=token)
        except _RequestFailure as failure:
            self._send_json(failure.status, failure.code)
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            self.close_connection = True
        except Exception:
            self._send_json(503, "SERVICE_UNAVAILABLE")

    def do_HEAD(self):
        self.close_connection = True
        self._send_json(405, "METHOD_NOT_ALLOWED", head=True)

    def do_POST(self):
        self._method_not_allowed()

    def do_PUT(self):
        self._method_not_allowed()

    def do_DELETE(self):
        self._method_not_allowed()

    def do_OPTIONS(self):
        self._method_not_allowed()

    def __getattr__(self, name):
        if name.startswith("do_"):
            return self._method_not_allowed
        raise AttributeError(name)

    def _method_not_allowed(self):
        self.close_connection = True
        self._send_json(405, "METHOD_NOT_ALLOWED")

    def _raw_target(self):
        try:
            parts = self.raw_requestline.split(b" ", 2)
            target = parts[1]
            return target.decode("ascii")
        except (IndexError, UnicodeDecodeError):
            raise _RequestFailure(400, "INVALID_REQUEST") from None

    def _check_request_limits(self):
        self._check_target_limit()
        self._check_header_budget()
        self._check_body_headers()

    def _check_target_limit(self):
        raw_target = self.raw_requestline.split(b" ", 2)
        if len(raw_target) < 2 or len(raw_target[1]) > _MAX_TARGET_CHARS:
            raise _RequestFailure(400, "INVALID_REQUEST")

    def _check_header_budget(self):
        try:
            headers = list(self.headers.raw_items())
            size = sum(
                len(name.encode("ascii"))
                + 2
                + len(value.encode("latin-1"))
                + 2
                for name, value in headers
            )
        except (UnicodeEncodeError, AttributeError):
            raise _RequestFailure(400, "INVALID_REQUEST") from None
        if len(headers) > _MAX_HEADERS or size > _MAX_HEADER_BYTES:
            raise _RequestFailure(400, "INVALID_REQUEST")

    def _check_body_headers(self):
        if self.headers.get_all("Transfer-Encoding"):
            raise _RequestFailure(400, "INVALID_REQUEST")
        if self.headers.get_all("Expect"):
            raise _RequestFailure(400, "INVALID_REQUEST")
        lengths = self.headers.get_all("Content-Length") or []
        if len(lengths) > 1:
            raise _RequestFailure(400, "INVALID_REQUEST")
        if lengths:
            value = lengths[0]
            if not value or re.fullmatch(r"[0-9]+", value) is None:
                raise _RequestFailure(400, "INVALID_REQUEST")
            try:
                if int(value) != 0:
                    raise _RequestFailure(400, "INVALID_REQUEST")
            except ValueError:
                raise _RequestFailure(400, "INVALID_REQUEST") from None

    def _check_host_and_origin(self):
        host_values = self.headers.get_all("Host") or []
        if (
            len(host_values) != 1
            or host_values[0] != self.server.expected_authority
        ):
            raise _RequestFailure(400, "INVALID_REQUEST")
        origin_values = self.headers.get_all("Origin") or []
        if len(origin_values) > 1:
            raise _RequestFailure(400, "INVALID_REQUEST")
        if origin_values and origin_values[0] != self.server.expected_origin:
            raise _RequestFailure(400, "INVALID_REQUEST")

    def _bearer_credential(self):
        values = self.headers.get_all("Authorization") or []
        if len(values) != 1:
            return None
        value = values[0]
        if not value.startswith("Bearer "):
            return None
        credential = value[len("Bearer "):]
        if not _valid_token(credential):
            return None
        return credential

    def _authorized(self, credential):
        try:
            return self.server.read_authorizer(credential) is True
        except Exception:
            return False

    def _read(self, operation):
        kind, first, second = operation
        if kind == "list":
            return 200, _project_list(
                self.server.catalog.list_media(limit=first, cursor=second),
                first,
            )
        record = self.server.catalog.get_media(first)
        if record is None:
            return 404, self._error_document("NOT_FOUND")
        projected = _project_media(record)
        if projected["libraryId"] != first:
            raise ValueError("catalog returned a different library item")
        return 200, projected

    @staticmethod
    def _error_document(code):
        return {"error": {"code": code, "message": _ERRORS[code]}}

    def _send_json(self, status, code, head=False):
        self._write_json(status, self._error_document(code), head=head)

    def _write_json(self, status, value, head=False, credential=None):
        try:
            payload = json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            ).encode("utf-8")
        except Exception:
            status = 503
            payload = json.dumps(
                self._error_document("SERVICE_UNAVAILABLE"),
                separators=(",", ":"),
            ).encode("utf-8")
        if len(payload) > _MAX_RESPONSE_BYTES:
            status = 503
            payload = json.dumps(
                self._error_document("SERVICE_UNAVAILABLE"),
                separators=(",", ":"),
            ).encode("utf-8")

        if credential is not None and not self._authorized(credential):
            status = 401
            payload = json.dumps(
                self._error_document("UNAUTHORIZED"),
                separators=(",", ":"),
            ).encode("utf-8")

        self.close_connection = True
        try:
            self.send_response(status)
            self.send_header("Content-Type", _JSON_CONTENT_TYPE)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            if not head:
                self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            self.close_connection = True


class _RequestFailure(Exception):
    def __init__(self, status, code):
        self.status = status
        self.code = code
        super().__init__(code)
