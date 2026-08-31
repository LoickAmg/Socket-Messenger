import pytest

from socket_messenger.protocol import (
    MAX_MESSAGE_LENGTH,
    ProtocolError,
    decode_message,
    encode_message,
    validate_chat,
    validate_hello,
)


def test_json_lines_round_trip_preserves_unicode() -> None:
    payload = {"type": "chat", "text": "Salut, monde !"}
    assert decode_message(encode_message(payload)) == payload


def test_hello_normalizes_whitespace() -> None:
    assert validate_hello({"type": "hello", "username": "  Ada   Lovelace  "}) == "Ada Lovelace"


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "chat", "text": ""},
        {"type": "chat", "text": "x" * (MAX_MESSAGE_LENGTH + 1)},
        {"type": "hello", "username": ""},
        {"type": "hello", "username": "x" * 33},
    ],
)
def test_invalid_payloads_raise_protocol_error(payload: dict[str, object]) -> None:
    with pytest.raises(ProtocolError):
        if payload["type"] == "chat":
            validate_chat(payload)
        else:
            validate_hello(payload)


def test_invalid_json_raises_protocol_error() -> None:
    with pytest.raises(ProtocolError, match="valid JSON"):
        decode_message(b"not-json\n")


def test_first_message_must_be_hello() -> None:
    with pytest.raises(ProtocolError, match="first message"):
        validate_hello({"type": "chat", "text": "hello"})
