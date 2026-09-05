# Socket Messenger

**Messagerie Socket Python**. Cette application met en pratique les sockets réseau bas niveau de la bibliothèque standard Python avec un serveur TCP multi-client, un client CLI interactif et une découverte de services en UDP sur le réseau local.

## Fonctionnalités

- Serveur TCP concurrent, avec un thread dédié par client.
- Protocole JSON Lines explicite : un objet JSON UTF-8 par ligne.
- Authentification de session légère par nom d’utilisateur, avec contrôle des doublons.
- Diffusion des messages à tous les membres du salon.
- Événements système d’arrivée, de départ et de bienvenue.
- Limitation des tailles de nom et de message pour éviter les entrées abusives.
- Découverte UDP par broadcast, désactivable pour les environnements qui ne l’autorisent pas.
- Tests unitaires du protocole et test d’intégration avec deux vrais clients TCP.
- Dockerfile minimal et workflow GitHub Actions pour les tests.

> Ce projet est volontairement pédagogique : il ne remplace pas une messagerie de production. Il n’intègre ni chiffrement TLS, ni persistance, ni authentification forte. Pour une utilisation sur Internet, il faudrait ajouter au minimum TLS, une gestion d’identité robuste et un contrôle anti-abus persistant.

## Prérequis

- Python 3.11 ou plus récent.
- `pip` et, pour les tests, `pytest`.

Créer un environnement virtuel depuis le dossier du projet :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Sous macOS ou Linux, les deux premières commandes deviennent :

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

## Démarrage local

Ouvrir un premier terminal et lancer le serveur :

```bash
python -m socket_messenger server --name "Salon local"
```

Le serveur écoute par défaut sur `0.0.0.0:8765` et répond aux requêtes de découverte UDP sur le port `37020`.

Dans un second terminal, se connecter avec un premier utilisateur :

```bash
python -m socket_messenger client --host 127.0.0.1 --port 8765 --username Alice
```

Dans un troisième terminal, ouvrir une autre session :

```bash
python -m socket_messenger client --host 127.0.0.1 --port 8765 --username Bob
```

Saisir un message puis appuyer sur Entrée. Utiliser `/help` pour afficher les commandes disponibles et `/quit` pour quitter.

Pour rechercher les serveurs annoncés sur le réseau local :

```bash
python -m socket_messenger discover --timeout 1.5
```

Pour utiliser un port différent, par exemple lors de plusieurs instances locales :

```bash
python -m socket_messenger server --port 9000 --discovery-port 37021
python -m socket_messenger client --port 9000 --username Alice
```

La découverte UDP peut être désactivée :

```bash
python -m socket_messenger server --no-discovery
```

## Protocole

Le client commence par envoyer :

```json
{"type":"hello","username":"Alice"}
```

Puis il envoie des messages de discussion :

```json
{"type":"chat","text":"Bonjour !"}
```

Le serveur diffuse notamment :

```json
{"type":"chat","username":"Alice","text":"Bonjour !"}
```

Chaque message est terminé par `\\n`. Ce délimiteur est important : TCP est un flux d’octets et ne conserve pas les frontières des appels `send`.

## Tests et qualité

```bash
python -m pytest
```

Les tests vérifient le round-trip JSON, la validation des entrées et l’échange réel de messages entre deux sockets TCP.

## Structure

```text
socket-messenger/
├── .github/workflows/ci.yml
├── src/socket_messenger/
│   ├── __init__.py
│   ├── __main__.py
│   ├── client.py
│   ├── discovery.py
│   ├── protocol.py
│   └── server.py
├── tests/
│   ├── test_protocol.py
│   └── test_server.py
├── Dockerfile
├── LICENSE
├── pyproject.toml
└── README.md
```
