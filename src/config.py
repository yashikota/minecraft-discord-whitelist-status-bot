import os
from dataclasses import dataclass


@dataclass
class BotConfig:
    discord_bot_token: str
    discord_status_channel_id: int
    minecraft_rcon_host: str
    minecraft_rcon_port: int
    minecraft_rcon_password: str
    database_path: str = "whitelist.db"

    @classmethod
    def from_env(cls) -> "BotConfig":
        return cls(
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN", ""),
            discord_status_channel_id=int(os.getenv("DISCORD_STATUS_CHANNEL_ID", "0")),
            minecraft_rcon_host=os.getenv("MINECRAFT_RCON_HOST", "localhost"),
            minecraft_rcon_port=int(os.getenv("MINECRAFT_RCON_PORT", "25575")),
            minecraft_rcon_password=os.getenv("MINECRAFT_RCON_PASSWORD", ""),
        )

    def validate(self) -> tuple[bool, str]:
        if not self.discord_bot_token:
            return False, "DISCORD_BOT_TOKEN environment variable not set"

        if self.discord_status_channel_id == 0:
            return False, "DISCORD_STATUS_CHANNEL_ID environment variable not set"

        if not self.minecraft_rcon_password:
            return False, "MINECRAFT_RCON_PASSWORD environment variable not set"

        return True, "Configuration is valid"
