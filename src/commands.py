from typing import TYPE_CHECKING

import discord
from discord import app_commands

from utils import (ErrorMessages, format_datetime, format_duration,
                   format_error_message, log_error)

if TYPE_CHECKING:
    from bot import MinecraftWhitelistStatusBot


class CommandHandler:
    def __init__(self, bot: "MinecraftWhitelistStatusBot"):
        self.bot = bot

    def is_admin(self, user: discord.Member | discord.User) -> bool:
        """Check if user has admin permissions"""
        if isinstance(user, discord.Member):
            return user.guild_permissions.administrator
        return False

    async def find_user_by_target(self, target: str) -> tuple[int, str] | None:
        """Find user by Discord ID or Minecraft username"""
        if target.isdigit():
            discord_id = int(target)
            minecraft_username = self.bot.db_manager.get_user(discord_id)
            if minecraft_username:
                return discord_id, minecraft_username
        else:
            all_users = self.bot.db_manager.get_all_users()
            for discord_id, minecraft_username, _, _, _ in all_users:
                if minecraft_username.lower() == target.lower():
                    return discord_id, minecraft_username
        return None

    async def remove_user_from_whitelist(
        self, discord_id: int, minecraft_username: str
    ) -> tuple[bool, str]:
        """Remove user from both database and server whitelist"""
        if not self.bot.db_manager.remove_user(discord_id):
            return False, "❌ Failed to remove from database."

        server_removed = await self.bot.minecraft_manager.remove_from_whitelist(
            minecraft_username
        )

        user_mention = (
            f"<@{discord_id}>"
            if self.bot.guild and self.bot.guild.get_member(discord_id)
            else f"Discord ID: {discord_id}"
        )

        if server_removed:
            return (
                True,
                f"✅ Removed {user_mention} (Minecraft ID: `{minecraft_username}`) from whitelist.",
            )
        else:
            return (
                True,
                f"⚠️ Removed from database but failed to remove from server whitelist.\nMinecraft ID: `{minecraft_username}`",
            )

    async def setup_commands(self):
        """Setup all slash commands"""

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
                    ErrorMessages.ADMIN_ONLY,
                    ephemeral=True,
                )
                return

            await interaction.response.defer()

            try:
                user_data = await self.find_user_by_target(target)

                if not user_data:
                    target_type = (
                        "Discord ID" if target.isdigit() else "Minecraft username"
                    )
                    await interaction.followup.send(
                        format_error_message(
                            f"{target_type} `{target}` is not registered."
                        )
                    )
                    return

                discord_id, minecraft_username = user_data
                success, message = await self.remove_user_from_whitelist(
                    discord_id, minecraft_username
                )
                await interaction.followup.send(message)

            except Exception as e:
                log_error("Remove whitelist command", e)
                await interaction.followup.send(ErrorMessages.GENERIC_ERROR)

        @app_commands.command(
            name="list_whitelist",
            description="Admin command: Display current whitelist registrations",
        )
        async def list_whitelist_command(interaction: discord.Interaction):
            if not self.is_admin(interaction.user):
                await interaction.response.send_message(
                    ErrorMessages.ADMIN_ONLY,
                    ephemeral=True,
                )
                return

            await interaction.response.defer()

            try:
                all_users = self.bot.db_manager.get_all_users()

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

                for i, (
                    discord_id,
                    minecraft_username,
                    _,
                    joined_at,
                    is_online,
                ) in enumerate(all_users[:25]):
                    user = (
                        interaction.guild.get_member(discord_id)
                        if interaction.guild
                        else None
                    )

                    if user:
                        user_display = f"**{user.display_name}**"
                    else:
                        user_display = f"**{minecraft_username}**"

                    status_emoji = "🟢" if is_online else "🔴"

                    embed.add_field(
                        name=f"{i + 1}. {user_display} {status_emoji}",
                        value=f"Minecraft ID: `{minecraft_username}`\n",
                        inline=False,
                    )

                if len(all_users) > 25:
                    embed.set_footer(text=f"... and {len(all_users) - 25} more users")

                await interaction.followup.send(embed=embed)

            except Exception as e:
                log_error("List whitelist command", e)
                await interaction.followup.send(ErrorMessages.GENERIC_ERROR)

        @app_commands.command(
            name="stat",
            description="Display player statistics (all players by default)",
        )
        @app_commands.describe(
            minecraft_username="Specific player to view detailed stats (optional)"
        )
        async def stat_command(
            interaction: discord.Interaction, minecraft_username: str = None
        ):
            await interaction.response.defer()

            try:
                if minecraft_username:
                    stats = self.bot.db_manager.get_player_stats(minecraft_username)
                    if not stats:
                        await interaction.followup.send(
                            format_error_message(
                                f"Player `{minecraft_username}` statistics not found."
                            )
                        )
                        return

                    embed = discord.Embed(
                        title=f"📊 {stats['username']} Statistics",
                        color=0x00FF00 if stats["is_online"] else 0x808080,
                    )

                    # Status
                    status_emoji = "🟢" if stats["is_online"] else "🔴"
                    status_text = "Online" if stats["is_online"] else "Offline"
                    embed.add_field(
                        name="Status",
                        value=f"{status_emoji} {status_text}",
                        inline=True,
                    )

                    # Total playtime
                    total_playtime_formatted = format_duration(
                        int(stats["total_playtime"])
                    )
                    embed.add_field(
                        name="Total Playtime",
                        value=f"⏱️ {total_playtime_formatted}",
                        inline=True,
                    )

                    # First join date
                    first_join_formatted = format_datetime(stats["first_join_at"])
                    embed.add_field(
                        name="First Login",
                        value=f"🎯 {first_join_formatted}",
                        inline=False,
                    )

                    # Last seen date
                    last_seen_formatted = format_datetime(stats["last_seen_at"])
                    embed.add_field(
                        name="Last Login",
                        value=f"👋 {last_seen_formatted}",
                        inline=False,
                    )

                    # Registration date
                    created_at_formatted = format_datetime(stats["created_at"])
                    embed.add_field(
                        name="Whitelist Registration",
                        value=f"📝 {created_at_formatted}",
                        inline=False,
                    )

                    await interaction.followup.send(embed=embed)

                else:
                    # Show stats for all players
                    all_stats = self.bot.db_manager.get_all_players_stats()

                    if not all_stats:
                        await interaction.followup.send(
                            "📄 No registered players found."
                        )
                        return

                    embed = discord.Embed(
                        title="📊 Player Statistics Overview",
                        color=0x00FF00,
                        description=f"Total registered players: {len(all_stats)}",
                    )

                    # Show top players by playtime (limit to 20 to avoid embed limits)
                    display_count = min(len(all_stats), 20)

                    for i, stats in enumerate(all_stats[:display_count]):
                        status_emoji = "🟢" if stats["is_online"] else "🔴"
                        total_playtime_formatted = format_duration(
                            int(stats["total_playtime"])
                        )

                        value_text = f"⏱️ {total_playtime_formatted}"

                        # Add first join info if available
                        if stats["first_join_at"]:
                            first_join_formatted = format_datetime(
                                stats["first_join_at"]
                            )
                            value_text += f"\n🎯 First: {first_join_formatted}"

                        # Add last seen info if available
                        if stats["last_seen_at"]:
                            last_seen_formatted = format_datetime(stats["last_seen_at"])
                            value_text += f"\n👋 Last: {last_seen_formatted}"

                        embed.add_field(
                            name=f"{i + 1}. {stats['username']} {status_emoji}",
                            value=value_text,
                            inline=False,
                        )

                    if len(all_stats) > 20:
                        embed.set_footer(
                            text=f"... and {len(all_stats) - 20} more players. Use '/stat <username>' for detailed stats."
                        )
                    else:
                        embed.set_footer(
                            text="Use '/stat <username>' for detailed player statistics."
                        )

                    await interaction.followup.send(embed=embed)

            except Exception as e:
                log_error("Stat command", e)
                await interaction.followup.send(ErrorMessages.GENERIC_ERROR)

        # Register commands with the bot
        self.bot.tree.add_command(remove_whitelist_command)
        self.bot.tree.add_command(list_whitelist_command)
        self.bot.tree.add_command(stat_command)
