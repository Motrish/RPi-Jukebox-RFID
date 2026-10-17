"""Run a verified web bundle behind a private, loopback-only nginx process."""

from __future__ import annotations

import argparse
import http.client
import os
from pathlib import Path
import shutil
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from typing import Callable, Optional, Sequence


CHECKOUT_ROOT = Path(__file__).resolve().parents[2]
if str(CHECKOUT_ROOT) not in sys.path:
    sys.path.insert(0, str(CHECKOUT_ROOT))

from installation.websetup import bundle, server  # noqa: E402
from tools.web_bundle import BundleError  # noqa: E402

_READY_TIMEOUT = 8.0
_NGINX_TEST_TIMEOUT = 8.0
_CHILD_STOP_TIMEOUT = 2.0


class _SafeLaunchError(Exception):
    """A deliberately authored diagnostic that contains no local path data."""


_TEMPLATE_TOKENS = {
    "@@BOOTSTRAP_LISTEN_PORT@@": "listen_port",
    "@@BOOTSTRAP_UPSTREAM_PORT@@": "upstream_port",
    "@@BOOTSTRAP_WEBROOT@@": "webroot",
    "@@BOOTSTRAP_READY_TOKEN@@": "ready_token",
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, help="verified web bundle archive")
    parser.add_argument("--manifest", required=True, help="web bundle manifest")
    parser.add_argument("--repository", required=True, help="expected repository identity")
    parser.add_argument("--commit", required=True, help="expected source commit")
    parser.add_argument("--port", type=int, default=8780, help="loopback port (1024..65535)")
    parser.add_argument("--nginx-binary", help="existing nginx executable")
    return parser


def _nginx_executable(value: Optional[str]) -> str:
    executable = value if value is not None else shutil.which("nginx")
    if executable is None:
        raise _SafeLaunchError("nginx was not found; install the existing nginx prerequisite")
    try:
        path = Path(executable).resolve(strict=True)
        if not path.is_file() or not os.access(str(path), os.X_OK):
            raise _SafeLaunchError("nginx-binary must identify an existing executable")
    except OSError:
        raise _SafeLaunchError("nginx-binary must identify an existing executable") from None
    return str(path)


def _nginx_quote(value: str) -> str:
    if "$" in value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise _SafeLaunchError("private filesystem path cannot be represented safely by nginx")
    return '"{}"'.format(value.replace("\\", "\\\\").replace('"', '\\"'))


def _render_config(template_path: Path, destination: Path, listen_port: int,
                   upstream_port: int, webroot: Path, ready_token: str) -> None:
    try:
        source = template_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise _SafeLaunchError("the fixed nginx template is unavailable") from None
    replacements = {
        "@@BOOTSTRAP_LISTEN_PORT@@": str(listen_port),
        "@@BOOTSTRAP_UPSTREAM_PORT@@": str(upstream_port),
        "@@BOOTSTRAP_WEBROOT@@": _nginx_quote(str(webroot)),
        "@@BOOTSTRAP_READY_TOKEN@@": ready_token,
    }
    for token, value in replacements.items():
        if source.count(token) != 1:
            raise _SafeLaunchError("the fixed nginx template has invalid parameters")
        source = source.replace(token, value)
    if any(token in source for token in _TEMPLATE_TOKENS):
        raise _SafeLaunchError("the fixed nginx template has unexpanded parameters")
    try:
        with destination.open("x", encoding="utf-8", newline="\n") as config:
            config.write(source)
    except OSError:
        raise _SafeLaunchError("private nginx configuration could not be written") from None


def _assert_outer_port_available(port: int) -> None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", port))
    except OSError:
        raise _SafeLaunchError("the requested loopback port is already occupied") from None


def _finish_process(process: subprocess.Popen, timeout: float) -> None:
    if process.poll() is not None:
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=timeout)
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)


def _nginx_config_test(popen_factory: Callable, executable: str,
                       prefix: Path, config: Path) -> None:
    command = [executable, "-t", "-p", str(prefix) + os.sep, "-c", str(config)]
    try:
        process = popen_factory(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True,
        )
    except OSError:
        raise _SafeLaunchError("nginx configuration test could not start") from None
    try:
        _output, _error = process.communicate(timeout=_NGINX_TEST_TIMEOUT)
    except subprocess.TimeoutExpired:
        _finish_process(process, _CHILD_STOP_TIMEOUT)
        raise _SafeLaunchError("nginx configuration test exceeded its time limit") from None
    if process.returncode != 0:
        raise _SafeLaunchError("nginx rejected the private configuration")


def _wait_ready(process: subprocess.Popen, port: int, ready_token: str,
                stop_requested: threading.Event) -> bool:
    deadline = time.monotonic() + _READY_TIMEOUT
    while time.monotonic() < deadline and not stop_requested.is_set():
        if process.poll() is not None:
            return False
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.25)
        try:
            connection.request(
                "GET", "/setup/",
                headers={"Host": "127.0.0.1:{}".format(port),
                         "X-I01B-Readiness": ready_token},
            )
            response = connection.getresponse()
            response.read()
            if response.status == 204 and process.poll() is None:
                return True
        except (OSError, http.client.HTTPException):
            pass
        finally:
            connection.close()
        stop_requested.wait(0.05)
    return False


def _start_upstream(make_server_factory: Callable):
    try:
        httpd = make_server_factory(root=CHECKOUT_ROOT, port=0)
        thread = threading.Thread(target=httpd.serve_forever, name="websetup-preflight", daemon=True)
        thread.start()
    except Exception:
        try:
            httpd.server_close()
        except (NameError, OSError):
            pass
        raise _SafeLaunchError("the local preflight listener could not start") from None
    return httpd, thread


def _stop_upstream(httpd, thread: Optional[threading.Thread]) -> None:
    if thread is not None and thread.is_alive():
        httpd.shutdown()
        thread.join(timeout=3.0)
    httpd.server_close()


def _wait_until_stopped(child: subprocess.Popen, args: argparse.Namespace, ready_token: str,
                        stop_requested: threading.Event) -> int:
    if not _wait_ready(child, args.port, ready_token, stop_requested):
        if stop_requested.is_set():
            return 0
        if child.poll() is not None:
            raise _SafeLaunchError("nginx exited before becoming ready; the port may be occupied")
        raise _SafeLaunchError("nginx did not become ready before the startup deadline")
    if child.poll() is not None:
        raise _SafeLaunchError("nginx exited before becoming ready")
    print("Setup: http://127.0.0.1:{}/setup/".format(args.port), flush=True)
    print("React Vorschau: http://127.0.0.1:{}/#/design-preview".format(args.port), flush=True)
    while not stop_requested.wait(0.05):
        if child.poll() is not None:
            raise _SafeLaunchError("nginx exited unexpectedly")
    return 0


def _serve_verified_bundle(args: argparse.Namespace, webroot: Path,
                           make_server_factory: Callable, popen_factory: Callable,
                           executable: str, stop_requested: threading.Event) -> int:
    private_parent = webroot.parent.parent
    prefix = private_parent / "nginx-prefix"
    logs = prefix / "logs"
    logs.mkdir(parents=True, mode=0o700)
    for name in ("client_body_temp", "proxy_temp", "fastcgi_temp", "uwsgi_temp", "scgi_temp"):
        (logs / name).mkdir(mode=0o700)
    config = prefix / "nginx.conf"
    httpd, thread = _start_upstream(make_server_factory)
    child = None
    try:
        upstream_port = int(httpd.server_address[1])
        if not 1 <= upstream_port <= 65535:
            raise _SafeLaunchError("the local preflight listener returned an invalid port")
        template = CHECKOUT_ROOT / "resources" / "default-settings" / "nginx.bootstrap-loopback.conf"
        ready_token = secrets.token_hex(32)
        _render_config(template, config, args.port, upstream_port, webroot, ready_token)
        _nginx_config_test(popen_factory, executable, prefix, config)
        if stop_requested.is_set():
            return 0
        command = [executable, "-p", str(prefix) + os.sep, "-c", str(config),
                   "-g", "daemon off; master_process off;"]
        try:
            child = popen_factory(
                command, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except OSError:
            raise _SafeLaunchError("nginx could not start") from None
        return _wait_until_stopped(child, args, ready_token, stop_requested)
    finally:
        if child is not None:
            _finish_process(child, _CHILD_STOP_TIMEOUT)
        _stop_upstream(httpd, thread)


def _serve(args: argparse.Namespace, make_server_factory: Callable,
           popen_factory: Callable) -> int:
    stop_requested = threading.Event()
    original_handlers = {}

    def request_stop(_signum, _frame):
        stop_requested.set()

    for signum in (signal.SIGINT, signal.SIGTERM):
        original_handlers[signum] = signal.signal(signum, request_stop)

    try:
        with tempfile.TemporaryDirectory(prefix="i01b-bootstrap-") as temporary:
            private_parent = Path(temporary)
            if os.name == "posix":
                private_parent.chmod(0o700)
            with bundle.staged_bundle(
                args.archive, args.manifest, args.repository, args.commit, private_parent,
            ) as webroot:
                _nginx_quote(str(webroot))
                _assert_outer_port_available(args.port)
                executable = _nginx_executable(args.nginx_binary)
                return _serve_verified_bundle(
                    args, webroot, make_server_factory, popen_factory,
                    executable, stop_requested,
                )
    finally:
        for signum, handler in original_handlers.items():
            signal.signal(signum, handler)


def run(argv: Optional[Sequence[str]] = None, *, make_server_factory=None,
        popen_factory=None) -> int:
    """Run the launcher and return its process exit status."""
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)
    if not 1024 <= args.port <= 65535:
        print("bootstrap-web: --port must be between 1024 and 65535", file=sys.stderr)
        return 2
    make_server_factory = make_server_factory or server.make_server
    popen_factory = popen_factory or subprocess.Popen
    try:
        return _serve(args, make_server_factory, popen_factory)
    except BundleError as error:
        print("bootstrap-web: bundle rejected: {}".format(error), file=sys.stderr)
    except _SafeLaunchError as error:
        print("bootstrap-web: {}".format(error), file=sys.stderr)
    except Exception:
        print("bootstrap-web: local setup could not be started safely", file=sys.stderr)
    return 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
