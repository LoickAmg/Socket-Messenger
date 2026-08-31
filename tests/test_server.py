import socket
import time

from socket_messenger.protocol import decode_message, encode_message
from socket_messenger.server import ChatServer


def _read_message(reader) -> dict[str, object]:
    line = reader.readline()
    assert line, "server closed the connection unexpectedly"
    return decode_message(line)


def _wait_for_client_count(server: ChatServer, expected: int) -> None:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if server.client_count == expected:
            return
        time.sleep(0.01)
    assert server.client_count == expected


def test_two_clients_exchange_a_chat_message() -> None:
    server = ChatServer(host="127.0.0.1", port=0, discovery_port=None)
    server.start()
    alice = socket.create_connection(("127.0.0.1", server.bound_port), timeout=2)
    bob = socket.create_connection(("127.0.0.1", server.bound_port), timeout=2)
    alice_reader = alice.makefile("rb")
    bob_reader = bob.makefile("rb")
    try:
        alice.sendall(encode_message({"type": "hello", "username": "Alice"}))
        assert _read_message(alice_reader)["event"] == "welcome"
        _wait_for_client_count(server, 1)

        bob.sendall(encode_message({"type": "hello", "username": "Bob"}))
        assert _read_message(bob_reader)["event"] == "welcome"
        assert _read_message(alice_reader) == {
            "type": "system",
            "event": "join",
            "username": "Bob",
            "message": "Bob joined the chat.",
        }
        _wait_for_client_count(server, 2)

        alice.sendall(encode_message({"type": "chat", "text": "Bonjour Bob"}))
        assert _read_message(bob_reader) == {
            "type": "chat",
            "username": "Alice",
            "text": "Bonjour Bob",
        }
    finally:
        alice.close()
        bob.close()
        server.stop()
