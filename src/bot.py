from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import BotConfig
from database import DatabaseManager
from discord_ui import ServerStatusView
from minecraft import MinecraftManager


class MinecraftWhitelistStatusBot(commands.Bot):
    def __init__(self, config: BotConfig):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        self.config = config
        self.pending_users: set[int] = set()
        self.status_message: discord.Message = None

        self.db_manager = DatabaseManager(config.database_path)
        self.minecraft_manager = MinecraftManager(
            config.minecraft_rcon_host,
            config.minecraft_rcon_password,
            config.minecraft_rcon_port,
        )

    def get_user_from_db(self, user_id: int) -> str | None:
        return self.db_manager.get_user(user_id)

    def add_user_to_db(self, discord_id: int, minecraft_username: str) -> bool:
        return self.db_manager.add_user(discord_id, minecraft_username)

    async def validate_minecraft_username(self, username: str) -> tuple[bool, str]:
        return await self.minecraft_manager.validate_minecraft_username(username)

    async def add_to_whitelist(self, username: str) -> bool:
        return await self.minecraft_manager.add_to_whitelist(username)

    async def on_ready(self):
        print(f"{self.user.name} logged in!")

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
            channel = self.get_channel(self.config.discord_status_channel_id)
            if not channel:
                print(
                    f"Error: Channel with ID {self.config.discord_status_channel_id} not found"
                )
                return

            embed, view = await self.create_server_status_embed()
            self.status_message = await channel.send(embed=embed, view=view)
            print(f"Status message posted to #{channel.name}")

        except Exception as e:
            print(f"Error posting initial status message: {e}")

    @tasks.loop(seconds=5)
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

    def get_date_str(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    async def create_server_status_embed(
        self,
    ) -> tuple[discord.Embed, ServerStatusView]:
        embed = discord.Embed(title="🎮 Minecraft Server Status", color=0x00FF00)

        is_running = await self.minecraft_manager.is_server_running()

        if is_running:
            player_list = await self.minecraft_manager.get_player_list()

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
                    minecraft_username = self.db_manager.get_user(discord_id)

                    if not minecraft_username:
                        await interaction.followup.send(
                            f"❌ Discord ID `{discord_id}` is not registered."
                        )
                        return

                    if self.db_manager.remove_user(discord_id):
                        server_removed = (
                            await self.minecraft_manager.remove_from_whitelist(
                                minecraft_username
                            )
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
                    all_users = self.db_manager.get_all_users()
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

                    if self.db_manager.remove_user(discord_id):
                        server_removed = (
                            await self.minecraft_manager.remove_from_whitelist(
                                minecraft_username
                            )
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
                all_users = self.db_manager.get_all_users()

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
