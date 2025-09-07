from bot import MinecraftWhitelistStatusBot
from config import BotConfig
from utils import log_error


def main():
    config = BotConfig.from_env()

    is_valid, error_message = config.validate()
    if not is_valid:
        log_error(f"Error: {error_message}")
        return

    bot = MinecraftWhitelistStatusBot(config)
    bot.run(config.discord_bot_token)


if __name__ == "__main__":
    main()
