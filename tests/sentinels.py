# SPDX-License-Identifier: GPL-3.0-or-later
"""Loopback listeners that record whether anything contacted them (used by the privacy leak tests)."""

import socket
import threading

LOOPBACK = "127.0.0.1"
SOCKET_TIMEOUT_SECONDS = 0.2


# Base: a socket on 127.0.0.1 with an OS-chosen port, served by a background thread until closed
class Sentinel:
    def __init__(self, name: str, socket_type: int) -> None:
        self.name = name
        self.socket = socket.socket(socket.AF_INET, socket_type)
        self.socket.settimeout(SOCKET_TIMEOUT_SECONDS)
        self.socket.bind((LOOPBACK, 0))
        self.port = self.socket.getsockname()[1]
        self.contacts = 0
        self.contacted = threading.Event()
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self.serve, daemon=True)

    # Count one contact and wake anyone waiting for it
    def record(self) -> None:
        self.contacts += 1
        self.contacted.set()

    # Subclasses receive one connection or datagram per call; timeouts just loop
    def serve(self) -> None:
        # Keep serving until close() is called
        while not self.stopping.is_set():
            try:
                self.receive_once()
            except (socket.timeout, OSError):
                continue

    def receive_once(self) -> None:
        raise NotImplementedError

    def __enter__(self) -> "Sentinel":
        self.thread.start()
        return self

    def __exit__(self, *exception_info: object) -> None:
        self.stopping.set()
        self.thread.join(timeout=2)
        self.socket.close()


# TCP listener: a fake peer, a fake HTTP tracker, or a dead proxy (accepts, records, hangs up)
class TcpSentinel(Sentinel):
    def __init__(self, name: str) -> None:
        super().__init__(name, socket.SOCK_STREAM)
        self.socket.listen(16)

    # Accept one connection, record it and close it straight away
    def receive_once(self) -> None:
        connection, _address = self.socket.accept()
        self.record()
        connection.close()


# UDP listener: a fake UDP tracker or DHT node
class UdpSentinel(Sentinel):
    def __init__(self, name: str) -> None:
        super().__init__(name, socket.SOCK_DGRAM)

    # Record any datagram
    def receive_once(self) -> None:
        self.socket.recvfrom(65536)
        self.record()
