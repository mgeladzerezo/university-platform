import socket
import struct
from typing import Protocol


class VirusScanner(Protocol):
    def is_clean(self, data: bytes) -> bool: ...


class ClamAvScanner:
    """Talks to clamd over TCP using the INSTREAM command."""

    _CHUNK = 64 * 1024

    def __init__(self, host: str, port: int, timeout: float = 30.0):
        self._address = (host, port)
        self._timeout = timeout

    def is_clean(self, data: bytes) -> bool:
        with socket.create_connection(self._address, timeout=self._timeout) as conn:
            conn.sendall(b"zINSTREAM\0")
            for start in range(0, len(data), self._CHUNK):
                chunk = data[start : start + self._CHUNK]
                conn.sendall(struct.pack(">I", len(chunk)) + chunk)
            conn.sendall(struct.pack(">I", 0))
            reply = self._read_reply(conn)
        return parse_clamd_reply(reply)

    @staticmethod
    def _read_reply(conn: socket.socket) -> str:
        buffer = b""
        while not buffer.endswith(b"\0"):
            received = conn.recv(4096)
            if not received:
                break
            buffer += received
        return buffer.rstrip(b"\0").decode()


def parse_clamd_reply(reply: str) -> bool:
    if reply.endswith("OK"):
        return True
    if reply.endswith("FOUND"):
        return False
    raise RuntimeError(f"Unexpected clamd reply: {reply!r}")
