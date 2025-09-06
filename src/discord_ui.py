from typing import Protocol

import discord


class BotProtocol(Protocol):
    pending_users: set[int]

    def get_user_from_db(self, user_id: int) -> str | None: ...

    def add_user_to_db(self, discord_id: int, minecraft_username: str) -> bool: ...

    async def validate_minecraft_username(self, username: str) -> tuple[bool, str]: ...

    async def add_to_whitelist(self, username: str) -> bool: ...


class WhitelistModal(discord.ui.Modal, title="Minecraft Whitelist Application"):
    def __init__(self, bot: BotProtocol):
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
    def __init__(self, bot: BotProtocol, is_server_running: bool = True):
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
