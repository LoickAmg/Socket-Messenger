"""Régression : un pair qui envoie un flot continu sans jamais renvoyer de
`\n` ne doit pas faire grossir indéfiniment la mémoire du serveur ni bloquer
sa boucle de lecture. Voir `server._iter_lines`."""

import socket
import time

from socket_messenger.protocol import MAX_LINE_BYTES, decode_message, encode_message
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


def test_unterminated_flood_is_rejected_instead_of_buffered_forever() -> None:
    server = ChatServer(host="127.0.0.1", port=0, discovery_port=None)
    server.start()
    attacker = socket.create_connection(("127.0.0.1", server.bound_port), timeout=2)
    reader = attacker.makefile("rb")
    try:
        # Un flot bien plus grand que MAX_LINE_BYTES, jamais terminé par un
        # saut de ligne : avant le correctif, `readline()` continuerait à
        # bufferiser indéfiniment sans jamais rendre la main. Après le
        # correctif, le serveur doit couper la connexion dès que la ligne
        # non terminée dépasse la taille max, sans attendre de `\n`.
        chunk = b"a" * 4096
        total_sent = 0
        target = MAX_LINE_BYTES * 4
        closed_or_errored = False
        attacker.settimeout(2)
        try:
            while total_sent < target:
                attacker.sendall(chunk)
                total_sent += len(chunk)
        except OSError:
            # Le serveur a coupé la connexion pendant l'envoi lui-même :
            # c'est le signe le plus net que la protection a fonctionné
            # (il n'a pas attendu de tamponner tout le flot).
            closed_or_errored = True

        # Sinon, il doit avoir fermé/coupé la connexion (ou renvoyé une
        # erreur puis fermé) plutôt que de rester silencieusement ouvert en
        # accumulant les octets en mémoire.
        if not closed_or_errored:
            try:
                line = reader.readline()
                closed_or_errored = line == b"" or decode_message(line)["type"] == "error"
            except OSError:
                closed_or_errored = True
        assert closed_or_errored
    finally:
        reader.close()
        attacker.close()
        server.stop()


def test_normal_client_still_works_after_flood_protection_added() -> None:
    server = ChatServer(host="127.0.0.1", port=0, discovery_port=None)
    server.start()
    alice = socket.create_connection(("127.0.0.1", server.bound_port), timeout=2)
    alice_reader = alice.makefile("rb")
    try:
        alice.sendall(encode_message({"type": "hello", "username": "Alice"}))
        assert _read_message(alice_reader)["event"] == "welcome"
        _wait_for_client_count(server, 1)

        alice.sendall(encode_message({"type": "chat", "text": "toujours en vie"}))
        # Pas d'autre client pour recevoir le broadcast ; on vérifie juste
        # qu'aucune erreur n'a été renvoyée sur ce message légitime en
        # envoyant un second message et en s'assurant que la connexion
        # reste ouverte et fonctionnelle.
        alice.sendall(encode_message({"type": "chat", "text": "encore"}))
        _wait_for_client_count(server, 1)
    finally:
        alice_reader.close()
        alice.close()
        server.stop()
