"""Interactive command-line TCP chat client."""

from __future__ import annotations

import argparse
import socket
import threading

from .discovery import discover
from .protocol import decode_message, encode_message


class ChatClient:
    """Read chat events in the background while the user types messages."""

    def __init__(self, host: str, port: int, username: str) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.connection: socket.socket | None = None
        self._stop = threading.Event()
        self._receiver: threading.Thread | None = None

    def run(self) -> None:
        self.connection = socket.create_connection((self.host, self.port), timeout=10)
        self.connection.settimeout(None)
        self.connection.sendall(encode_message({"type": "hello", "username": self.username}))
        self._receiver = threading.Thread(target=self._receive_loop, name="chat-receiver", daemon=True)
        self._receiver.start()
        print(f"Connected to {self.host}:{self.port}. Type /help for commands.")
        try:
            while not self._stop.is_set():
                try:
                    text = input("> ")
                except EOFError:
                    break
                command = text.strip()
                if command == "/help":
                    print("Commands: /help, /quit")
                elif command in {"/quit", "/exit"}:
                    break
                elif command:
                    self.connection.sendall(encode_message({"type": "chat", "text": command}))
        except (BrokenPipeError, ConnectionError):
            print("The connection to the server was closed.")
        finally:
            self.close()

    def close(self) -> None:
        self._stop.set()
        if self.connection is not None:
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.connection.close()
            self.connection = None

    def _receive_loop(self) -> None:
        assert self.connection is not None
        try:
            reader = self.connection.makefile("rb")
            for line in reader:
                message = decode_message(line)
                self._print_message(message)
        except (OSError, ValueError):
            if not self._stop.is_set():
                print("\nThe connection to the server was closed.")
        finally:
            self._stop.set()

    @staticmethod
    def _print_message(message: dict[str, object]) -> None:
        message_type = message.get("type")
        if message_type == "chat":
            print(f"\n[{message.get('username')}] {message.get('text')}")
        elif message_type == "error":
            print(f"\n[error] {message.get('message')}")
        else:
            print(f"\n[system] {message.get('message', message)}")


def discover_command(timeout: float) -> None:
    servers = list(discover(timeout=timeout))
    if not servers:
        print("No chat servers found.")
        return
    for server in servers:
        print(f"{server.name}\t{server.host}:{server.port}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Connect to a socket-messenger TCP chat room.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8_765)
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    ChatClient(args.host, args.port, args.username).run()


if __name__ == "__main__":
    main()
