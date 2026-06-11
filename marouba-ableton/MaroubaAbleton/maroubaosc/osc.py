from __future__ import absolute_import, print_function

import errno
import logging
import os
import socket
import struct


def _port_from_env(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


OSC_LISTEN_PORT = _port_from_env("MAROUBA_ABLETON_OSC_SEND_PORT", 11000)
OSC_RESPONSE_PORT = _port_from_env("MAROUBA_ABLETON_OSC_RECV_PORT", 11001)

logger = logging.getLogger("marouba-ableton")


def _pad4(data):
    padding = (4 - (len(data) % 4)) % 4
    return data + (b"\0" * padding)


def _encode_string(value):
    if not isinstance(value, bytes):
        value = str(value).encode("utf-8")
    return _pad4(value + b"\0")


def _decode_string(data, offset):
    end = data.index(b"\0", offset)
    value = data[offset:end].decode("utf-8")
    offset = end + 1
    while offset % 4:
        offset += 1
    return value, offset


def _decode_message(data):
    address, offset = _decode_string(data, 0)
    tags, offset = _decode_string(data, offset)
    params = []
    if not tags.startswith(","):
        return address, params
    for tag in tags[1:]:
        if tag == "s":
            value, offset = _decode_string(data, offset)
            params.append(value)
        elif tag == "i":
            params.append(struct.unpack(">i", data[offset : offset + 4])[0])
            offset += 4
        elif tag == "f":
            params.append(struct.unpack(">f", data[offset : offset + 4])[0])
            offset += 4
    return address, params


def _encode_message(address, params):
    tags = ","
    body = b""
    for param in params:
        if isinstance(param, bool):
            tags += "i"
            body += struct.pack(">i", 1 if param else 0)
        elif isinstance(param, int):
            tags += "i"
            body += struct.pack(">i", param)
        elif isinstance(param, float):
            tags += "f"
            body += struct.pack(">f", param)
        else:
            tags += "s"
            body += _encode_string(param)
    return _encode_string(address) + _encode_string(tags) + body


class MaroubaOscServer(object):
    def __init__(
        self,
        local_addr=("127.0.0.1", OSC_LISTEN_PORT),
        remote_addr=("127.0.0.1", OSC_RESPONSE_PORT),
    ):
        self._local_addr = local_addr
        self._remote_addr = remote_addr
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setblocking(0)
        self._socket.bind(self._local_addr)
        self._callbacks = {}
        logger.info("OSC server listening on %s", self._local_addr)

    def add_handler(self, address, callback):
        self._callbacks[address] = callback

    def send(self, address, params=(), remote_addr=None):
        if remote_addr is None:
            remote_addr = self._remote_addr
        self._socket.sendto(_encode_message(address, params), remote_addr)

    def process(self):
        while True:
            try:
                data, remote_addr = self._socket.recvfrom(65536)
            except socket.error as error:
                if error.errno in (errno.EAGAIN, errno.EWOULDBLOCK):
                    return
                if error.errno == errno.ECONNRESET:
                    logger.warning("Non-fatal OSC socket reset")
                    return
                logger.exception("OSC socket error")
                return
            try:
                address, params = _decode_message(data)
                callback = self._callbacks.get(address)
                if callback is None:
                    logger.warning("Unknown OSC address: %s", address)
                    continue
                response = callback(tuple(params))
                if response is not None:
                    self.send(address, tuple(response), (remote_addr[0], OSC_RESPONSE_PORT))
            except Exception:
                logger.exception("Error handling OSC message")

    def shutdown(self):
        self._socket.close()
