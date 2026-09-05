"""UDP discovery for local-network chat servers."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from dataclasses import dataclass

DISCOVERY_PORT = 37_020
DISCOVER_REQUEST = b"SOCKET_MESSENGER_DISCOVER\n"


@dataclass(frozen=True, slots=True)
class DiscoveredServer:
    """A server announced by UDP discovery."""

    name: str
    host: str
    port: int


class DiscoveryResponder:
    """Answer discovery broadcasts while a TCP chat server is running."""

    def __init__(self, server_name: str, tcp_port: int, port: int = DISCOVERY_PORT) -> None:
        self.server_name = server_name
        self.tcp_port = tcp_port
        self.port = port
        self._stop = threading.Event()
        self._socket: socket.socket | None = None

    def serve_forever(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket = sock
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", self.port))
            sock.settimeout(0.5)
            while not self._stop.is_set():
                try:
                    datagram, address = sock.recvfrom(1_024)
                except TimeoutError:
                    continue
                if datagram.strip() != DISCOVER_REQUEST.strip():
                    continue
                payload = {
                    "service": "socket-messenger",
                    "name": self.server_name,
                    "port": self.tcp_port,
                }
                sock.sendto(json.dumps(payload).encode("utf-8"), address)
        except OSError:
            if not self._stop.is_set():
                raise
        finally:
            sock.close()
            self._socket = None

    def stop(self) -> None:
        self._stop.set()
        if self._socket is not None:
            self._socket.close()


def discover(
    timeout: float = 1.0,
    port: int = DISCOVERY_PORT,
    broadcast_address: str = "255.255.255.255",
) -> Iterator[DiscoveredServer]:
    """Broadcast a discovery request and yield valid server announcements."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(timeout)
        sock.sendto(DISCOVER_REQUEST, (broadcast_address, port))
        while True:
            try:
                response_bytes, address = sock.recvfrom(4_096)
            except TimeoutError:
                return
            try:
                payload = json.loads(response_bytes.decode("utf-8"))
                if payload.get("service") != "socket-messenger":
                    continue
                name = payload["name"]
                tcp_port = int(payload["port"])
                if not isinstance(name, str) or not 1 <= tcp_port <= 65_535:
                    continue
            except (ValueError, KeyError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
                continue
            yield DiscoveredServer(name=name, host=address[0], port=tcp_port)
