"""
Simple Minecraft RCON client without signal dependency
Based on mcrcon but uses socket timeout instead of signals
"""
import socket
import struct


class SimpleRconException(Exception):
    pass


class SimpleRcon:
    """A simple RCON client that works in threads"""

    def __init__(self, host, password, port=25575, timeout=5):
        self.host = host
        self.password = password
        self.port = port
        self.timeout = timeout
        self.socket = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, type, value, tb):
        self.disconnect()

    def connect(self):
        """Connect to the RCON server"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(self.timeout)

        try:
            self.socket.connect((self.host, self.port))
            # Send authentication packet
            self._send(3, self.password)
        except Exception as e:
            if self.socket:
                self.socket.close()
                self.socket = None
            raise SimpleRconException(f"Connection failed: {e}")

    def disconnect(self):
        """Disconnect from the RCON server"""
        if self.socket is not None:
            self.socket.close()
            self.socket = None

    def _read(self, length):
        """Read specified number of bytes from socket"""
        data = b""
        while len(data) < length:
            try:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    raise SimpleRconException("Connection closed by server")
                data += chunk
            except socket.timeout:
                raise SimpleRconException("Read timeout")
            except Exception as e:
                raise SimpleRconException(f"Read error: {e}")
        return data

    def _send(self, out_type, out_data):
        """Send RCON packet and return response"""
        if self.socket is None:
            raise SimpleRconException("Must connect before sending data")

        try:
            # Send request packet
            out_payload = (
                struct.pack("<ii", 0, out_type) +
                out_data.encode("utf8") +
                b"\x00\x00"
            )
            out_length = struct.pack("<i", len(out_payload))
            self.socket.send(out_length + out_payload)

            # Read response packet
            in_length_data = self._read(4)
            (in_length,) = struct.unpack("<i", in_length_data)

            in_payload = self._read(in_length)
            in_id, in_type = struct.unpack("<ii", in_payload[:8])
            in_data_partial = in_payload[8:-2]
            in_padding = in_payload[-2:]

            # Sanity checks
            if in_padding != b"\x00\x00":
                raise SimpleRconException("Incorrect padding")
            if in_id == -1:
                raise SimpleRconException("Login failed")

            return in_data_partial.decode("utf8")

        except SimpleRconException:
            raise
        except Exception as e:
            raise SimpleRconException(f"Send error: {e}")

    def command(self, command):
        """Execute RCON command and return response"""
        return self._send(2, command)
