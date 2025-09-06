from bot import MinecraftWhitelistStatusBot
from config import BotConfig


def main():
    config = BotConfig.from_env()

    is_valid, error_message = config.validate()
    if not is_valid:
        print(f"Error: {error_message}")
        return

    bot = MinecraftWhitelistStatusBot(config)
    bot.run(config.discord_bot_token)


if __name__ == "__main__":
    main()
