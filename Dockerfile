FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8765/tcp
EXPOSE 37020/udp

ENTRYPOINT ["python", "-m", "socket_messenger", "server", "--host", "0.0.0.0"]
