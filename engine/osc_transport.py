from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from typing import Any


OscValue = str | int | float | bool


@dataclass
class OscMessage:
    address: str
    args: list[OscValue]


class OscUdpClient:
    """Shared OSC UDP transport used by app adapters that speak native OSC."""

    def __init__(self, host: str = "127.0.0.1", send_port: int = 7000, recv_port: int | None = None, timeout: float = 1.0) -> None:
        self.host = host
        self.send_port = send_port
        self.recv_port = recv_port
        self.timeout = timeout

    def send(self, address: str, args: list[OscValue] | None = None) -> None:
        payload = encode_osc_message(address, args or [])
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(payload, (self.host, self.send_port))

    def request(self, address: str, args: list[OscValue] | None = None) -> OscMessage:
        if self.recv_port is None:
            raise RuntimeError("OSC request requires a recv_port")
        payload = encode_osc_message(address, args or [])
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(self.timeout)
            sock.bind((self.host, self.recv_port))
            sock.sendto(payload, (self.host, self.send_port))
            data, _ = sock.recvfrom(65536)
        return decode_osc_message(data)


def encode_osc_message(address: str, args: list[OscValue] | None = None) -> bytes:
    if not address.startswith("/"):
        raise RuntimeError(f"OSC address must start with '/': {address}")
    values = args or []
    tags = "," + "".join(type_tag(value) for value in values)
    output = bytearray(osc_string(address))
    output.extend(osc_string(tags))
    for value in values:
        output.extend(osc_arg(value))
    return bytes(output)


def decode_osc_message(data: bytes) -> OscMessage:
    address, offset = read_osc_string(data, 0)
    tags, offset = read_osc_string(data, offset)
    args: list[OscValue] = []
    for tag in tags.lstrip(","):
        if tag == "s":
            value, offset = read_osc_string(data, offset)
            args.append(value)
        elif tag == "i":
            require_len(data, offset, 4, "truncated OSC int")
            args.append(struct.unpack(">i", data[offset : offset + 4])[0])
            offset += 4
        elif tag == "f":
            require_len(data, offset, 4, "truncated OSC float")
            args.append(struct.unpack(">f", data[offset : offset + 4])[0])
            offset += 4
        elif tag == "T":
            args.append(True)
        elif tag == "F":
            args.append(False)
        else:
            raise RuntimeError(f"Unsupported OSC type tag: {tag}")
    return OscMessage(address, args)


def type_tag(value: OscValue) -> str:
    if isinstance(value, bool):
        return "T" if value else "F"
    if isinstance(value, int):
        return "i"
    if isinstance(value, float):
        return "f"
    return "s"


def osc_arg(value: OscValue) -> bytes:
    if isinstance(value, bool):
        return b""
    if isinstance(value, int):
        return struct.pack(">i", value)
    if isinstance(value, float):
        return struct.pack(">f", value)
    return osc_string(str(value))


def osc_string(value: str) -> bytes:
    data = bytearray(value.encode("utf-8"))
    data.append(0)
    while len(data) % 4 != 0:
        data.append(0)
    return bytes(data)


def read_osc_string(data: bytes, start: int) -> tuple[str, int]:
    end = start
    while end < len(data) and data[end] != 0:
        end += 1
    if end >= len(data):
        raise RuntimeError("unterminated OSC string")
    value = data[start:end].decode("utf-8")
    offset = end + 1
    while offset % 4 != 0:
        offset += 1
    return value, offset


def require_len(data: bytes, offset: int, length: int, message: str) -> None:
    if offset + length > len(data):
        raise RuntimeError(message)
