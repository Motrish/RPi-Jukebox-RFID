"""Explicit local runner for an already initialized library catalog."""

import argparse
import secrets
import sqlite3
import sys
from pathlib import Path

from components.library_catalog import LibraryCatalog

from .server import make_read_authorizer, make_server


def _port(value):
    if not value.isascii() or not value.isdecimal():
        raise argparse.ArgumentTypeError("port must be a decimal integer")
    if len(value) > 1 and value.startswith("0"):
        raise argparse.ArgumentTypeError("port must be canonical")
    port = int(value)
    if not 1024 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1024 and 65535")
    return port


def _arguments(argv):
    parser = argparse.ArgumentParser(
        description=(
            "Serve authenticated, read-only library metadata on loopback."
        )
    )
    parser.add_argument("--database", required=True)
    parser.add_argument("--library-root", required=True)
    parser.add_argument("--port", required=True, type=_port)
    parser.add_argument(
        "--origin-host",
        choices=("127.0.0.1", "localhost"),
        default="127.0.0.1",
    )
    return parser.parse_args(argv)


def _interactive_tty():
    try:
        return sys.stdin.isatty() is True and sys.stdout.isatty() is True
    except Exception:
        return False


def _existing_schema_one(database):
    connection = None
    try:
        uri = Path(database).expanduser().resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=0.250)
        row = connection.execute("PRAGMA user_version").fetchone()
        return row is not None and row[0] == 1
    except (OSError, sqlite3.Error, ValueError):
        return False
    finally:
        if connection is not None:
            connection.close()


def _close_server_quietly(server):
    if server is not None:
        try:
            server.server_close()
        except Exception:
            pass


def _close_catalog_quietly(catalog):
    if catalog is not None:
        try:
            catalog.close()
        except Exception:
            pass


def main(argv=None):
    """Run the API until interrupted, closing the server and owned catalog."""
    try:
        arguments = _arguments(argv)
    except SystemExit as error:
        return error.code
    if not _interactive_tty():
        print(
            "The library API requires an interactive terminal.",
            file=sys.stderr,
        )
        return 1
    if not _existing_schema_one(arguments.database):
        print("The existing library catalog is unavailable.", file=sys.stderr)
        return 1

    catalog = None
    server = None
    token = None
    try:
        catalog = LibraryCatalog(arguments.database, arguments.library_root)
        token = secrets.token_urlsafe(32)
        alphabet = (
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
        )
        if len(token) != 43 or not token.isascii() or any(
            char not in alphabet for char in token
        ):
            raise ValueError("generated credential had an invalid form")

        gate = [None]

        def authorize(credential):
            current = gate[0]
            return current(credential) if current is not None else False

        server = make_server(
            catalog=catalog,
            read_authorizer=authorize,
            port=arguments.port,
            origin_host=arguments.origin_host,
        )
        gate[0] = make_read_authorizer(token)
        print(
            "Read-only bearer token (valid for 15 minutes): {}".format(token),
            flush=True,
        )
        server.serve_forever(poll_interval=0.25)
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("The library API could not start.", file=sys.stderr)
        return 1
    finally:
        try:
            _close_server_quietly(server)
        finally:
            _close_catalog_quietly(catalog)


if __name__ == "__main__":
    raise SystemExit(main())
