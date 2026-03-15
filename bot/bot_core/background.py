import asyncio

import uvicorn

import database
from bot_core.runtime import app, bot, dp, logger
from bot_core.summarizer import run_summarizer_if_needed


async def memory_archiver():
    while True:
        await asyncio.sleep(300)
        try:
            world_state = await database.get_all_world_states()
            if world_state.get("bot_mode", "normal") != "quest":
                continue
            if world_state.get("quest_started", "0") != "1":
                continue

            try:
                world_turn_counter = int(world_state.get("world_turn_counter", "0"))
            except Exception:
                world_turn_counter = 0
            if world_turn_counter <= 0:
                continue

            result = await run_summarizer_if_needed(trigger="background", world_state=world_state, force=False)
            if result.get("ran"):
                logger.info("📦 Summarizer обновил долговременную память кампании.")
        except Exception as error:
            logger.error(f"Archiver Error: {error}")


async def start_all():
    await database.init_db()
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="error")
    server = uvicorn.Server(config)
    await asyncio.gather(dp.start_polling(bot), server.serve(), memory_archiver())
