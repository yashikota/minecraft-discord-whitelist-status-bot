from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks

from commands import CommandHandler
from config import BotConfig
from database import DatabaseManager
from discord_ui import ServerStatusView
from minecraft import MinecraftManager
from utils import log_error, log_info


class MinecraftWhitelistStatusBot(commands.Bot):
    def __init__(self, config: BotConfig):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

        self.config = config
        self.pending_users: set[int] = set()
        self.status_message: discord.Message = None
        self.guild: discord.Guild = None

        self.db_manager = DatabaseManager(config.database_path)
        self.minecraft_manager = MinecraftManager(
            config.minecraft_rcon_host,
            config.minecraft_rcon_password,
            config.minecraft_rcon_port,
        )
        self.command_handler = CommandHandler(self)

    def get_user_from_db(self, user_id: int) -> str | None:
        return self.db_manager.get_user(user_id)

    def add_user_to_db(self, discord_id: int, minecraft_username: str) -> bool:
        return self.db_manager.add_user(discord_id, minecraft_username)

    async def validate_minecraft_username(self, username: str) -> tuple[bool, str]:
        return await self.minecraft_manager.validate_minecraft_username(username)

    async def add_to_whitelist(self, username: str) -> bool:
        return await self.minecraft_manager.add_to_whitelist(username)

    async def on_ready(self):
        log_info("Bot startup", f"{self.user.name} logged in!")

        await self.command_handler.setup_commands()
        try:
            synced = await self.tree.sync()
            log_info("Command sync", f"Synced {len(synced)} command(s)")
        except Exception as e:
            log_error("Command sync", e)

        await self.post_initial_status_message()
        self.update_status_task.start()

    async def post_initial_status_message(self):
        try:
            channel = self.get_channel(self.config.discord_status_channel_id)
            if not channel:
                print(
                    f"Error: Channel with ID {self.config.discord_status_channel_id} not found"
                )
                return
            self.guild = channel.guild

            embed, view = await self.create_server_status_embed()
            self.status_message = await channel.send(embed=embed, view=view)
            log_info("Status message", f"Posted to #{channel.name}")

        except Exception as e:
            log_error("Initial status message posting", e)

    @tasks.loop(seconds=5)
    async def update_status_task(self):
        if not self.status_message:
            return

        try:
            embed, view = await self.create_server_status_embed()
            await self.status_message.edit(embed=embed, view=view)

        except Exception as e:
            log_error("Status message update", e)
            if "Unknown Message" in str(e):
                await self.post_initial_status_message()

    @update_status_task.before_loop
    async def before_update_status_task(self):
        await self.wait_until_ready()

    def get_date_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def timestamp_to_discord_format(self, timestamp_str: str) -> str:
        """Convert SQLite timestamp to Discord relative time format"""
        try:
            dt = datetime.fromisoformat(timestamp_str)
            dt_utc = dt.replace(tzinfo=timezone.utc)
            unix_timestamp = int(dt_utc.timestamp())
            return f"<t:{unix_timestamp}:R>"
        except Exception as e:
            log_error("Timestamp conversion", e)
            return timestamp_str

    def format_player_display(
        self, player: str, user_map: dict, is_registered: bool = True
    ) -> str:
        """Format a single player for display in the embed"""
        if not is_registered:
            return f"❓ **{player}** (Unregistered)"

        discord_id, joined_at, _ = user_map[player]
        member = self.guild.get_member(discord_id) if self.guild else None

        relative_time = (
            self.timestamp_to_discord_format(joined_at) if joined_at else "Never joined"
        )

        if member:
            return f"**{member.display_name}** - {relative_time}"
        else:
            return f"**{player}** - {relative_time}"

    def create_online_players_display(
        self, player_list: list[str], user_map: dict
    ) -> list[str]:
        """Create formatted display list for online players"""
        online_players_display = []

        for player in player_list[:10]:
            if player in user_map:
                online_players_display.append(
                    self.format_player_display(player, user_map, is_registered=True)
                )
            else:
                online_players_display.append(
                    self.format_player_display(player, user_map, is_registered=False)
                )

        if len(player_list) > 10:
            online_players_display.append(f"... and {len(player_list) - 10} more")

        return online_players_display

    def update_player_statuses(self, player_list: list[str], user_map: dict) -> None:
        """Update online/offline status of all tracked players"""
        for username in user_map:
            is_currently_online = username in player_list
            discord_id, joined_at, was_online = user_map[username]

            if (is_currently_online and not was_online) or (
                not is_currently_online and was_online
            ):
                self.db_manager.update_player_online_status(
                    username, is_currently_online
                )

                if is_currently_online:
                    current_time = datetime.now(timezone.utc).isoformat()
                    user_map[username] = (discord_id, current_time, True)
                else:
                    user_map[username] = (discord_id, joined_at, False)

    async def create_server_status_embed(
        self,
    ) -> tuple[discord.Embed, ServerStatusView]:
        embed = discord.Embed(title="🎮 Minecraft Server Status", color=0x00FF00)
        is_running = await self.minecraft_manager.is_server_running()

        if is_running:
            player_list = await self.minecraft_manager.get_player_list()
            all_users = self.db_manager.get_all_users()
            user_map = {
                username: (discord_id, joined_at, is_online)
                for discord_id, username, _, joined_at, is_online in all_users
            }

            # Update player online/offline statuses
            self.update_player_statuses(player_list, user_map)

            if player_list:
                online_players_display = self.create_online_players_display(
                    player_list, user_map
                )
                embed.add_field(
                    name="🎯 Online Players",
                    value="\n".join(online_players_display)
                    if online_players_display
                    else "No registered players online",
                    inline=False,
                )
            else:
                # Set all players to offline
                for username in user_map:
                    self.db_manager.update_player_online_status(username, False)

                embed.add_field(
                    name="🎯 Online Players",
                    value="No players online",
                    inline=False,
                )
        else:
            embed.color = 0xFF0000
            embed.description = "🔴 Offline"

        view = ServerStatusView(self, is_running)
        return embed, view
