import asyncio

from bot_core.api import register_api_routes
from bot_core.background import start_all
from bot_core.handlers import register_bot_handlers
from bot_core.runtime import app, logger


register_api_routes()
register_bot_handlers()


if __name__ == "__main__":
    try:
        asyncio.run(start_all())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Бот остановлен. Якен уходит в тень.")
