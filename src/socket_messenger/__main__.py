"""Command dispatcher for ``python -m socket_messenger``."""

from __future__ import annotations

import argparse

from .client import ChatClient, discover_command
from .server import ChatServer


def main() -> None:
    parser = argparse.ArgumentParser(prog="socket-messenger")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server = subparsers.add_parser("server", help="start a chat server")
    server.add_argument("--host", default="0.0.0.0")
    server.add_argument("--port", type=int, default=8_765)
    server.add_argument("--name", default="Local chat")
    server.add_argument("--no-discovery", action="store_true")
    server.add_argument("--discovery-port", type=int, default=37_020)

    client = subparsers.add_parser("client", help="connect to a chat server")
    client.add_argument("--host", default="127.0.0.1")
    client.add_argument("--port", type=int, default=8_765)
    client.add_argument("--username", required=True)

    discovery = subparsers.add_parser("discover", help="find servers on the local network")
    discovery.add_argument("--timeout", type=float, default=1.0)

    args = parser.parse_args()
    if args.command == "server":
        ChatServer(
            host=args.host,
            port=args.port,
            server_name=args.name,
            discovery_port=None if args.no_discovery else args.discovery_port,
        ).serve_forever()
    elif args.command == "client":
        ChatClient(args.host, args.port, args.username).run()
    else:
        discover_command(args.timeout)


if __name__ == "__main__":
    main()
