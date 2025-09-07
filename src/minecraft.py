import asyncio
import re

import aiohttp

from rcon import Rcon
from utils import log_error


class MinecraftManager:
    def __init__(self, rcon_host: str, rcon_password: str, rcon_port: int = 25575):
        self.rcon_host = rcon_host
        self.rcon_password = rcon_password
        self.rcon_port = rcon_port

    async def validate_minecraft_username(self, username: str) -> tuple[bool, str]:
        if not re.match(r"^[a-zA-Z0-9_]{3,16}$", username):
            return (
                False,
                "Username must be 3-16 characters, alphanumeric and underscore only",
            )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"https://api.mojang.com/users/profiles/minecraft/{username}"
                ) as response:
                    if response.status == 200:
                        return True, "Valid Minecraft username"
                    elif response.status == 204:
                        return False, "This Minecraft username does not exist"
                    else:
                        return False, "Error occurred while checking username"
        except Exception as e:
            log_error("Minecraft username validation", e)
            return False, "Error occurred while checking username"

    async def is_server_running(self) -> bool:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._check_server_sync), timeout=5.0
            )
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            log_error("Server connection check", e)
            return False

    def _check_server_sync(self) -> bool:
        try:
            with Rcon(self.rcon_host, self.rcon_password, port=self.rcon_port) as mcr:
                mcr.command("list")
                return True
        except Exception:
            return False

    async def get_player_list(self) -> list[str]:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._get_player_list_sync), timeout=5.0
            )
        except asyncio.TimeoutError:
            return []
        except Exception as e:
            log_error("Player list retrieval", e)
            return []

    def _get_player_list_sync(self) -> list[str]:
        try:
            with Rcon(self.rcon_host, self.rcon_password, port=self.rcon_port) as mcr:
                response = mcr.command("list")
                if ": " in response:
                    player_part = response.split(": ", 1)[1]
                    if player_part.strip():
                        return [p.strip() for p in player_part.split(",")]
                return []
        except Exception:
            return []

    async def add_to_whitelist(self, username: str) -> bool:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._add_to_whitelist_sync, username),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            log_error("Whitelist addition", e)
            return False

    def _add_to_whitelist_sync(self, username: str) -> bool:
        try:
            with Rcon(self.rcon_host, self.rcon_password, port=self.rcon_port) as mcr:
                response = mcr.command(f"whitelist add {username}")
                return "Added" in response or "already" in response
        except Exception:
            return False

    async def remove_from_whitelist(self, username: str) -> bool:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._remove_from_whitelist_sync, username),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            log_error("Whitelist removal", e)
            return False

    def _remove_from_whitelist_sync(self, username: str) -> bool:
        try:
            with Rcon(self.rcon_host, self.rcon_password, port=self.rcon_port) as mcr:
                response = mcr.command(f"whitelist remove {username}")
                return "Removed" in response or "not on" in response
        except Exception:
            return False
