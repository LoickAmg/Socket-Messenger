"""Threaded TCP chat server."""

from __future__ import annotations

import argparse
import socket
import threading
from dataclasses import dataclass, field
from typing import TextIO

from .discovery import DISCOVERY_PORT, DiscoveryResponder
from .protocol import (
    ProtocolError,
    decode_message,
    encode_message,
    validate_chat,
    validate_hello,
)

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8_765


@dataclass
class _Client:
    connection: socket.socket
    address: tuple[str, int]
    username: str
    send_lock: threading.Lock = field(default_factory=threading.Lock)


class ChatServer:
    """A small multi-client TCP chat room.

    The server uses one reader thread per connected client and a lock-protected
    registry. Every application message is a single JSON object terminated by
    a newline, which keeps framing deterministic over TCP.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        server_name: str = "Local chat",
        discovery_port: int | None = DISCOVERY_PORT,
    ) -> None:
        self.host = host
        self.port = port
        self.server_name = server_name
        self.discovery_port = discovery_port
        self._server_socket: socket.socket | None = None
        self._clients: dict[socket.socket, _Client] = {}
        self._clients_lock = threading.RLock()
        self._stop = threading.Event()
        self._accept_thread: threading.Thread | None = None
        self._discovery = DiscoveryResponder(server_name, port, discovery_port) if discovery_port else None
        self._discovery_thread: threading.Thread | None = None

    @property
    def bound_port(self) -> int:
        """Return the actual TCP port, including when the server used port 0."""
        if self._server_socket is None:
            return self.port
        return int(self._server_socket.getsockname()[1])

    @property
    def client_count(self) -> int:
        with self._clients_lock:
            return len(self._clients)

    def start(self) -> None:
        """Bind and start accepting clients in a background thread."""
        if self._server_socket is not None:
            raise RuntimeError("server already started")
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        server_socket.settimeout(0.5)
        self._server_socket = server_socket
        self.port = self.bound_port
        self._accept_thread = threading.Thread(target=self._accept_loop, name="chat-accept", daemon=True)
        self._accept_thread.start()
        if self._discovery is not None:
            self._discovery.tcp_port = self.port
            self._discovery_thread = threading.Thread(
                target=self._discovery.serve_forever, name="chat-discovery", daemon=True
            )
            self._discovery_thread.start()

    def serve_forever(self) -> None:
        """Run the server in the foreground until interrupted."""
        self.start()
        assert self._accept_thread is not None
        try:
            while not self._stop.wait(0.5):
                pass
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self) -> None:
        """Close the listening socket and all connected clients."""
        if self._stop.is_set():
            return
        self._stop.set()
        if self._discovery is not None:
            self._discovery.stop()
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
        with self._clients_lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            try:
                client.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.connection.close()

    def _accept_loop(self) -> None:
        assert self._server_socket is not None
        while not self._stop.is_set():
            try:
                connection, address = self._server_socket.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            thread = threading.Thread(
                target=self._handle_client,
                args=(connection, address),
                name=f"chat-client-{address[0]}:{address[1]}",
                daemon=True,
            )
            thread.start()

    def _handle_client(self, connection: socket.socket, address: tuple[str, int]) -> None:
        client: _Client | None = None
        reader: TextIO | None = None
        try:
            reader = connection.makefile("r", encoding="utf-8", newline="\n")
            first_line = reader.readline()
            if not first_line:
                return
            try:
                username = validate_hello(decode_message(first_line))
            except ProtocolError as exc:
                self._send_raw(connection, {"type": "error", "message": str(exc)})
                return
            client = _Client(connection, address, username)
            with self._clients_lock:
                if any(existing.username == username for existing in self._clients.values()):
                    self._send(client, {"type": "error", "message": "username is already in use"})
                    return
                self._clients[connection] = client
            self._send(client, {"type": "system", "event": "welcome", "message": f"Welcome, {username}!"})
            self._broadcast(
                {"type": "system", "event": "join", "username": username, "message": f"{username} joined the chat."},
                exclude=connection,
            )
            for line in reader:
                try:
                    text = validate_chat(decode_message(line))
                except ProtocolError as exc:
                    self._send(client, {"type": "error", "message": str(exc)})
                    continue
                self._broadcast({"type": "chat", "username": username, "text": text})
        except (ConnectionError, OSError):
            pass
        finally:
            if reader is not None:
                reader.close()
            if client is not None:
                with self._clients_lock:
                    was_present = self._clients.pop(connection, None) is not None
                if was_present and not self._stop.is_set():
                    self._broadcast(
                        {"type": "system", "event": "leave", "username": client.username, "message": f"{client.username} left the chat."},
                        exclude=connection,
                    )
            try:
                connection.close()
            except OSError:
                pass

    def _broadcast(self, message: dict[str, object], exclude: socket.socket | None = None) -> None:
        with self._clients_lock:
            clients = list(self._clients.values())
        stale: list[socket.socket] = []
        for client in clients:
            if client.connection is exclude:
                continue
            try:
                self._send(client, message)
            except OSError:
                stale.append(client.connection)
        for connection in stale:
            with self._clients_lock:
                self._clients.pop(connection, None)

    @staticmethod
    def _send_raw(connection: socket.socket, message: dict[str, object]) -> None:
        connection.sendall(encode_message(message))

    @staticmethod
    def _send(client: _Client, message: dict[str, object]) -> None:
        with client.send_lock:
            client.connection.sendall(encode_message(message))


def main() -> None:
    parser = argparse.ArgumentParser(description="Start a TCP chat server with optional UDP discovery.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="interface to bind (default: all interfaces)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="TCP port (default: 8765)")
    parser.add_argument("--name", default="Local chat", help="name advertised to UDP discovery")
    parser.add_argument("--no-discovery", action="store_true", help="disable UDP discovery")
    parser.add_argument("--discovery-port", type=int, default=DISCOVERY_PORT)
    args = parser.parse_args()
    server = ChatServer(
        host=args.host,
        port=args.port,
        server_name=args.name,
        discovery_port=None if args.no_discovery else args.discovery_port,
    )
    print(f"{args.name} listening on {args.host}:{args.port}")
    if not args.no_discovery:
        print(f"UDP discovery enabled on port {args.discovery_port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
