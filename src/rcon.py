import socket
import struct


class RconException(Exception):
    pass


class Rcon:
    def __init__(self, host: str, password: str, port: int = 25575, timeout: int = 5):
        self.host = host
        self.password = password
        self.port = port
        self.timeout = timeout
        self.socket: socket.socket | None = None

    def __enter__(self) -> "Rcon":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def connect(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(self.timeout)

        try:
            self.socket.connect((self.host, self.port))
            self._send(3, self.password)
        except Exception as e:
            if self.socket:
                self.socket.close()
                self.socket = None
            raise RconException(f"Connection failed: {e}")

    def disconnect(self) -> None:
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def _read(self, length: int) -> bytes:
        data = b""
        while len(data) < length:
            try:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    raise RconException("Connection closed by server")
                data += chunk
            except socket.timeout:
                raise RconException("Read timeout")
            except Exception as e:
                raise RconException(f"Read error: {e}")
        return data

    def _send(self, out_type: int, out_data: str) -> str:
        if self.socket is None:
            raise RconException("Must connect before sending data")

        try:
            out_payload = (
                struct.pack("<ii", 0, out_type) + out_data.encode("utf8") + b"\x00\x00"
            )
            out_length = struct.pack("<i", len(out_payload))
            self.socket.send(out_length + out_payload)

            in_length_data = self._read(4)
            (in_length,) = struct.unpack("<i", in_length_data)

            in_payload = self._read(in_length)
            in_id, in_type = struct.unpack("<ii", in_payload[:8])
            in_data_partial = in_payload[8:-2]
            in_padding = in_payload[-2:]

            if in_padding != b"\x00\x00":
                raise RconException("Incorrect padding")
            if in_id == -1:
                raise RconException("Login failed")

            return in_data_partial.decode("utf8")

        except RconException:
            raise
        except Exception as e:
            raise RconException(f"Send error: {e}")

    def command(self, command: str) -> str:
        return self._send(2, command)
