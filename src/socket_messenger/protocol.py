"""Small, explicit JSON-lines protocol for the chat application."""

from __future__ import annotations

import json
from typing import Any

MAX_LINE_BYTES = 8_192
MAX_USERNAME_LENGTH = 32
MAX_MESSAGE_LENGTH = 2_000


class ProtocolError(ValueError):
    """Raised when a peer sends a malformed or unsupported message."""


def encode_message(message: dict[str, Any]) -> bytes:
    """Serialize one protocol message as UTF-8 JSON followed by a newline."""
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise ProtocolError("A message must be an object with a string type")
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def decode_message(raw_line: bytes | str) -> dict[str, Any]:
    """Decode and validate one JSON-lines protocol message."""
    if isinstance(raw_line, bytes):
        if len(raw_line) > MAX_LINE_BYTES:
            raise ProtocolError("Message too large")
        try:
            raw_line = raw_line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("Message must be valid UTF-8") from exc
    if len(raw_line.encode("utf-8")) > MAX_LINE_BYTES:
        raise ProtocolError("Message too large")
    try:
        message = json.loads(raw_line)
    except json.JSONDecodeError as exc:
        raise ProtocolError("Message must be valid JSON") from exc
    if not isinstance(message, dict) or not isinstance(message.get("type"), str):
        raise ProtocolError("A message must be an object with a string type")
    return message


def validate_hello(message: dict[str, Any]) -> str:
    """Return a normalized username or raise a protocol error."""
    if message.get("type") != "hello":
        raise ProtocolError("The first message must be a hello")
    username = message.get("username")
    if not isinstance(username, str):
        raise ProtocolError("username must be a string")
    username = " ".join(username.strip().split())
    if not username:
        raise ProtocolError("username cannot be empty")
    if len(username) > MAX_USERNAME_LENGTH:
        raise ProtocolError(f"username cannot exceed {MAX_USERNAME_LENGTH} characters")
    return username


def validate_chat(message: dict[str, Any]) -> str:
    """Return chat text or raise a protocol error."""
    if message.get("type") != "chat":
        raise ProtocolError("Unsupported client message type")
    text = message.get("text")
    if not isinstance(text, str):
        raise ProtocolError("text must be a string")
    text = text.strip()
    if not text:
        raise ProtocolError("text cannot be empty")
    if len(text) > MAX_MESSAGE_LENGTH:
        raise ProtocolError(f"text cannot exceed {MAX_MESSAGE_LENGTH} characters")
    return text
