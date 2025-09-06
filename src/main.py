import asyncio
import os
import re
import sqlite3
from datetime import datetime

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from simple_rcon import SimpleRcon


class WhitelistModal(discord.ui.Modal, title="Minecraft Whitelist Application"):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    username = discord.ui.TextInput(
        label="Minecraft Username",
        placeholder="Enter your Minecraft username...",
        required=True,
        max_length=16,
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        username = self.username.value.strip()

        existing_username = self.bot.get_user_from_db(user_id)
        if existing_username:
            await interaction.response.send_message(
                f"✅ Already registered as `{existing_username}`",
                ephemeral=True,
            )
            return

        if user_id in self.bot.pending_users:
            await interaction.response.send_message(
                "⏳ Already processing. Please wait.", ephemeral=True
            )
            return

        self.bot.pending_users.add(user_id)
        await interaction.response.send_message(
            f"🔍 Checking username `{username}`...", ephemeral=True
        )

        try:
            is_valid, message = await self.bot.validate_minecraft_username(username)

            if is_valid:
                whitelist_success = await self.bot.add_to_whitelist(username)
                if whitelist_success:
                    if self.bot.add_user_to_db(user_id, username):
                        await interaction.followup.send(
                            f"✅ Added `{username}` to whitelist!", ephemeral=True
                        )
                    else:
                        await interaction.followup.send(
                            f"⚠️ Added to whitelist but failed to save to database. Please contact admin.",
                            ephemeral=True,
                        )
                else:
                    await interaction.followup.send(
                        f"❌ Failed to add `{username}` to whitelist. Server may have issues.",
                        ephemeral=True,
                    )
            else:
                await interaction.followup.send(f"❌ {message}", ephemeral=True)

        except Exception as e:
            print(f"Error: {e}")
            await interaction.followup.send(
                "❌ Error occurred during processing. Please try again.", ephemeral=True
            )

        finally:
            self.bot.pending_users.discard(user_id)


class ServerStatusView(discord.ui.View):
    def __init__(self, bot, is_server_running: bool = True):
        super().__init__(timeout=300)
        self.bot = bot
        self.is_server_running = is_server_running
        self.update_button_state()

    @discord.ui.button(label="📋 Apply for Whitelist", style=discord.ButtonStyle.green)
    async def whitelist_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        user_id = interaction.user.id

        if not self.is_server_running:
            await interaction.response.send_message(
                "❌ Server is offline.", ephemeral=True
            )
            return

        existing_username = self.bot.get_user_from_db(user_id)
        if existing_username:
            await interaction.response.send_message(
                f"✅ Already registered as `{existing_username}`",
                ephemeral=True,
            )
            return

        modal = WhitelistModal(self.bot)
        await interaction.response.send_modal(modal)

    def update_button_state(self):
        if not self.is_server_running:
            self.whitelist_button.disabled = True
            self.whitelist_button.style = discord.ButtonStyle.grey
        else:
            self.whitelist_button.disabled = False
            self.whitelist_button.style = discord.ButtonStyle.green


class MinecraftWhitelistStatusBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        self.pending_users: set[int] = set()
        self.status_message: discord.Message = None
        self.status_channel_id: int = int(os.getenv("DISCORD_STATUS_CHANNEL_ID", "0"))

        self.rcon_host: str = os.getenv("MINECRAFT_RCON_HOST", "localhost")
        self.rcon_port: int = int(os.getenv("MINECRAFT_RCON_PORT", "25575"))
        self.rcon_password: str = os.getenv("MINECRAFT_RCON_PASSWORD", "")

        self.db_path = "whitelist.db"
        self.init_database()

    def init_database(self):
        """Initialize SQLite database and create table"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS whitelist_users (
                        discord_id INTEGER PRIMARY KEY,
                        minecraft_username TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                print("Database initialized successfully")
        except Exception as e:
            print(f"Database initialization error: {e}")

    def add_user_to_db(self, discord_id: int, minecraft_username: str) -> bool:
        """Add user to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO whitelist_users (discord_id, minecraft_username) VALUES (?, ?)",
                    (discord_id, minecraft_username),
                )
                conn.commit()
                return True
        except Exception as e:
            print(f"User addition error: {e}")
            return False

    def get_user_from_db(self, discord_id: int) -> str | None:
        """Get user's Minecraft username from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT minecraft_username FROM whitelist_users WHERE discord_id = ?",
                    (discord_id,),
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            print(f"User retrieval error: {e}")
            return None

    def remove_user_from_db(self, discord_id: int) -> bool:
        """Remove user from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM whitelist_users WHERE discord_id = ?", (discord_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"User deletion error: {e}")
            return False

    def get_all_users_from_db(self) -> list[tuple[int, str]]:
        """Get all users from database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT discord_id, minecraft_username FROM whitelist_users"
                )
                return cursor.fetchall()
        except Exception as e:
            print(f"All users retrieval error: {e}")
            return []

    async def on_ready(self):
        print(f"{self.user.name} logged in!")

        if self.status_channel_id == 0:
            print("Error: DISCORD_STATUS_CHANNEL_ID environment variable not set")
            await self.close()
            return

        if self.rcon_password == "":
            print("Error: MINECRAFT_RCON_PASSWORD environment variable not set")
            await self.close()
            return

        await self.setup_commands()
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

        await self.post_initial_status_message()
        self.update_status_task.start()

    async def post_initial_status_message(self):
        try:
            channel = self.get_channel(self.status_channel_id)
            if not channel:
                print(f"Error: Channel with ID {self.status_channel_id} not found")
                return

            embed, view = await self.create_server_status_embed()
            self.status_message = await channel.send(embed=embed, view=view)
            print(f"Status message posted to #{channel.name}")

        except Exception as e:
            print(f"Error posting initial status message: {e}")

    @tasks.loop(seconds=30)
    async def update_status_task(self):
        if not self.status_message:
            return

        try:
            embed, view = await self.create_server_status_embed()
            await self.status_message.edit(embed=embed, view=view)

        except Exception as e:
            print(f"Error updating status message: {e}")
            if "Unknown Message" in str(e):
                await self.post_initial_status_message()

    @update_status_task.before_loop
    async def before_update_status_task(self):
        await self.wait_until_ready()

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
            print(f"API call error: {e}")
            return False, "Error occurred while checking username"

    async def is_server_running(self) -> bool:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._check_server_sync), timeout=5.0
            )
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            print(f"Server connection error: {e}")
            return False

    def _check_server_sync(self) -> bool:
        try:
            with SimpleRcon(self.rcon_host, self.rcon_password, port=self.rcon_port) as mcr:
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
            print(f"Player list error: {e}")
            return []

    def _get_player_list_sync(self) -> list[str]:
        try:
            with SimpleRcon(self.rcon_host, self.rcon_password, port=self.rcon_port) as mcr:
                response = mcr.command("list")
                if ": " in response:
                    player_part = response.split(": ", 1)[1]
                    if player_part.strip():
                        return [p.strip() for p in player_part.split(",")]
                return []
        except Exception:
            return []

    def get_date_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def add_to_whitelist(self, username: str) -> bool:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._add_to_whitelist_sync, username),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            print(f"Whitelist add error: {e}")
            return False

    def _add_to_whitelist_sync(self, username: str) -> bool:
        try:
            with SimpleRcon(self.rcon_host, self.rcon_password, port=self.rcon_port) as mcr:
                response = mcr.command(f"whitelist add {username}")
                return "Added" in response or "already" in response
        except Exception:
            return False

    async def remove_from_whitelist(self, username: str) -> bool:
        """Remove user from server whitelist"""
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._remove_from_whitelist_sync, username),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            return False
        except Exception as e:
            print(f"Whitelist remove error: {e}")
            return False

    def _remove_from_whitelist_sync(self, username: str) -> bool:
        try:
            with SimpleRcon(self.rcon_host, self.rcon_password, port=self.rcon_port) as mcr:
                response = mcr.command(f"whitelist remove {username}")
                return "Removed" in response or "not on" in response
        except Exception:
            return False

    async def create_server_status_embed(
        self,
    ) -> tuple[discord.Embed, ServerStatusView]:
        embed = discord.Embed(title="🎮 Minecraft Server Status", color=0x00FF00)

        is_running = await self.is_server_running()

        if is_running:
            player_list = await self.get_player_list()

            if player_list:
                player_display = "\n".join(f"• {player}" for player in player_list[:10])
                if len(player_list) > 10:
                    player_display += f"\n... and {len(player_list) - 10} more"
                player_block = f"```fix\n{player_display}\n```"
                embed.add_field(
                    name="🎯 Online Players", value=player_block, inline=False
                )
            else:
                embed.add_field(
                    name="🎯 Online Players",
                    value="```fix\nNo players online\n```",
                    inline=False,
                )
        else:
            embed.color = 0xFF0000
            embed.description = "🔴 Offline"

        view = ServerStatusView(self, is_running)
        return embed, view

    def is_admin(self, user: discord.Member | discord.User) -> bool:
        if isinstance(user, discord.Member):
            return user.guild_permissions.administrator
        return False

    async def setup_commands(self):
        @app_commands.command(
            name="remove_whitelist",
            description="Admin command: Remove user from whitelist",
        )
        @app_commands.describe(target="Discord ID or Minecraft username to remove")
        async def remove_whitelist_command(
            interaction: discord.Interaction, target: str
        ):
            if not self.is_admin(interaction.user):
                await interaction.response.send_message(
                    "❌ This command can only be used by administrators.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()

            try:
                if target.isdigit():
                    discord_id = int(target)
                    minecraft_username = self.get_user_from_db(discord_id)

                    if not minecraft_username:
                        await interaction.followup.send(
                            f"❌ Discord ID `{discord_id}` is not registered."
                        )
                        return

                    if self.remove_user_from_db(discord_id):
                        server_removed = await self.remove_from_whitelist(
                            minecraft_username
                        )

                        if server_removed:
                            user_mention = (
                                f"<@{discord_id}>"
                                if interaction.guild.get_member(discord_id)
                                else f"Discord ID: {discord_id}"
                            )
                            await interaction.followup.send(
                                f"✅ Removed {user_mention} (Minecraft: `{minecraft_username}`) from whitelist."
                            )
                        else:
                            await interaction.followup.send(
                                f"⚠️ Removed from database but failed to remove from server whitelist.\nMinecraft: `{minecraft_username}`"
                            )
                    else:
                        await interaction.followup.send(
                            f"❌ Failed to remove from database."
                        )

                else:
                    all_users = self.get_all_users_from_db()
                    target_user = None

                    for discord_id, minecraft_username in all_users:
                        if minecraft_username.lower() == target.lower():
                            target_user = (discord_id, minecraft_username)
                            break

                    if not target_user:
                        await interaction.followup.send(
                            f"❌ Minecraft username `{target}` is not registered."
                        )
                        return

                    discord_id, minecraft_username = target_user

                    if self.remove_user_from_db(discord_id):
                        server_removed = await self.remove_from_whitelist(
                            minecraft_username
                        )

                        if server_removed:
                            user_mention = (
                                f"<@{discord_id}>"
                                if interaction.guild.get_member(discord_id)
                                else f"Discord ID: {discord_id}"
                            )
                            await interaction.followup.send(
                                f"✅ Removed {user_mention} (Minecraft: `{minecraft_username}`) from whitelist."
                            )
                        else:
                            await interaction.followup.send(
                                f"⚠️ Removed from database but failed to remove from server whitelist.\nMinecraft: `{minecraft_username}`"
                            )
                    else:
                        await interaction.followup.send(
                            f"❌ Failed to remove from database."
                        )

            except Exception as e:
                print(f"Remove whitelist command error: {e}")
                await interaction.followup.send(
                    "❌ An error occurred. Please contact an administrator."
                )

        @app_commands.command(
            name="list_whitelist",
            description="Admin command: Display current whitelist registrations",
        )
        async def list_whitelist_command(interaction: discord.Interaction):
            if not self.is_admin(interaction.user):
                await interaction.response.send_message(
                    "❌ This command can only be used by administrators.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer()

            try:
                all_users = self.get_all_users_from_db()

                if not all_users:
                    await interaction.followup.send(
                        "📄 No users are currently registered."
                    )
                    return

                embed = discord.Embed(
                    title="📋 Whitelist Registrations",
                    color=0x00FF00,
                    description=f"Total registered users: {len(all_users)}",
                )

                for i, (discord_id, minecraft_username) in enumerate(all_users[:25]):
                    user = interaction.guild.get_member(discord_id)
                    user_display = user.display_name if user else f"ID: {discord_id}"
                    embed.add_field(
                        name=f"{i + 1}. {user_display}",
                        value=f"Minecraft: `{minecraft_username}`",
                        inline=False,
                    )

                if len(all_users) > 25:
                    embed.set_footer(text=f"... and {len(all_users) - 25} more users")

                await interaction.followup.send(embed=embed)

            except Exception as e:
                print(f"List whitelist command error: {e}")
                await interaction.followup.send(
                    "❌ An error occurred. Please contact an administrator."
                )

        self.tree.add_command(remove_whitelist_command)
        self.tree.add_command(list_whitelist_command)


bot = MinecraftWhitelistStatusBot()


def main():
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        return

    bot.run(token)


if __name__ == "__main__":
    main()
