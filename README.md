# Minecraft Discord Whitelist Status Bot

A Discord bot to manage Minecraft server whitelist with real-time server status updates.

## Features

- **Auto Status Display**: Posts server status to Discord channel on startup
- **Real-time Updates**: Updates server status every 30 seconds
- **Whitelist Application**: Button-triggered modal for username input
- **Username Validation**: Verifies Minecraft usernames via Mojang API
- **Duplicate Prevention**: One registration per Discord user
- **RCON Integration**: Automatically adds users to server whitelist

## Setup

### 1. Discord Bot

1. Create a bot at [Discord Developer Portal](https://discord.com/developers/applications)
2. Get the bot token
3. Grant permissions: `Send Messages`, `Use Slash Commands`

### 2. Environment Variables

Create `.env` file:

```env
DISCORD_BOT_TOKEN=your_discord_bot_token_here
DISCORD_STATUS_CHANNEL_ID=123456789012345678
MINECRAFT_RCON_HOST=localhost
MINECRAFT_RCON_PORT=25575
MINECRAFT_RCON_PASSWORD=your_rcon_password_here
```

### 3. Run

```bash
docker compose up -d --build
```
