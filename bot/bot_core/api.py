import os

import httpx
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import database
from bot_core.config import BASE_DIR, SETTINGS
from bot_core.gameplay import continue_after_story_roll, launch_act, pause_quest, register_story_dice_roll, resume_quest
from bot_core.lore import CHARACTER_LORE
from bot_core.runtime import app, bot, hf_client, logger, pending_responses


app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

assets_dir = os.path.join(BASE_DIR, "webapp", "dist", "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


def register_api_routes():
    allowed_world_update_keys = {"bot_mode", "gm_action_mode", "llm_tier"}
    hidden_world_state_keys = {"faction_states", "npc_states", "world_clocks"}

    def normalize_tier(value: str | None) -> str:
        tier = (value or "free").lower()
        return tier if tier in {"free", "paid"} else "free"

    def default_model_for_tier(tier: str) -> str:
        if tier == "paid":
            return SETTINGS.gemini_paid_model or "gemini-3.1-flash-lite-preview"
        return SETTINGS.gemini_free_model or "gemini-2.5-flash-lite"

    def sanitize_world_state_for_ui(world_state: dict) -> dict:
        return {key: value for key, value in world_state.items() if key not in hidden_world_state_keys}

    @app.get("/")
    async def serve_webapp():
        return FileResponse(os.path.join(BASE_DIR, "webapp", "dist", "index.html"))

    @app.get("/api/user/{user_id}")
    async def get_user_data(user_id: int):
        if user_id == SETTINGS.admin_id:
            world_state = sanitize_world_state_for_ui(await database.get_all_world_states())
            return {
                "role": "admin",
                "characters": await database.get_all_characters(),
                "groups": await database.get_groups(),
                "events": await database.get_recent_events(10),
                "key_events": await database.get_recent_key_events(30),
                "world_state": world_state,
            }

        all_chars = await database.get_all_characters()
        for char in all_chars:
            if char["tg_id"] == user_id:
                char_data = await database.get_character(char["id"])
                world_state = sanitize_world_state_for_ui(await database.get_all_world_states())
                whispers = await database.get_whispers(char["id"])
                return {
                    "role": "player",
                    "character": char_data,
                    "world_state": world_state,
                    "whispers": whispers,
                }
        return {"role": "unknown"}

    @app.post("/api/update_world")
    async def update_world(data: dict):
        key = data["key"]
        value = str(data["value"])

        if key not in allowed_world_update_keys:
            return {"status": "error", "message": "Ручное изменение этого параметра отключено."}

        await database.set_world_state(key, value)

        return {"status": "ok"}

    @app.post("/api/start_act")
    async def start_act(data: dict):
        return {"status": "error", "message": "Ручной запуск акта отключён. Актами управляет ГМ-ИИ."}

    @app.post("/api/update_name")
    async def update_name(data: dict):
        return {"status": "error", "message": "Ручная смена имени отключена. Имя меняется только по сюжетным тегам ГМ-ИИ."}

    @app.post("/api/update_player_id")
    async def update_player_id(data: dict):
        return {"status": "error", "message": "Ручная привязка игрока через API отключена."}

    @app.post("/api/update")
    async def update_stats(data: dict):
        return {"status": "error", "message": "Ручное изменение статов отключено. Статы ведёт ГМ-ИИ."}

    @app.post("/api/item")
    async def manage_item(data: dict):
        return {"status": "error", "message": "Ручное управление инвентарём отключено. Предметы выдаёт ГМ-ИИ."}

    @app.post("/api/knowledge")
    async def manage_knowledge(data: dict):
        return {"status": "error", "message": "Ручное добавление знаний отключено. Знания выдаёт ГМ-ИИ."}

    @app.post("/api/whisper")
    async def send_whisper(data: dict):
        char_id = data["char_id"]
        text = data["text"]
        char = await database.get_character(char_id)
        await database.save_whisper(char_id, text)
        if char and char["tg_id"]:
            try:
                await bot.send_message(char["tg_id"], f"👁 **Шепот Судьбы:**\n_{text}_", parse_mode="Markdown")
                await database.add_game_event("whisper", f"Шепот для {char_id}: {text[:50]}")
                return {"status": "ok"}
            except Exception as error:
                return {"status": "error", "message": str(error)}
        return {"status": "error", "message": "Player not found or ID is 0"}

    @app.get("/api/lore/{char_id}")
    async def get_character_lore(char_id: str):
        lore = CHARACTER_LORE.get(char_id)
        if lore:
            return {"status": "ok", "lore": lore}
        return {"status": "error", "message": "Lore not found"}

    @app.post("/api/reset_game")
    async def reset_game():
        pending_responses.clear()
        await database.reset_game_state()
        return {"status": "ok"}

    @app.post("/api/pause_quest")
    async def pause_quest_api():
        result = await pause_quest(reason="")
        return {"status": "ok" if result.get("ok") else "error", **result}

    @app.post("/api/resume_quest")
    async def resume_quest_api():
        result = await resume_quest()
        return {"status": "ok" if result.get("ok") else "error", **result}

    @app.post("/api/stop_quest")
    async def stop_quest_api():
        pending_responses.clear()
        await database.reset_game_state()
        return {"status": "ok"}

    @app.post("/api/update_model")
    async def update_model(data: dict):
        target_model = str(data["model"])
        world_state = await database.get_all_world_states()
        llm_tier = normalize_tier(world_state.get("llm_tier", SETTINGS.default_llm_tier))

        if llm_tier == "paid" and not target_model.startswith("gemini"):
            return {
                "status": "error",
                "message": "В paid-режиме разрешены только Gemini модели.",
            }

        await database.set_world_state("gemini_model", target_model)
        return {"status": "ok"}

    @app.post("/api/update_llm_tier")
    async def update_llm_tier(data: dict):
        tier = normalize_tier(str(data.get("tier", "free")))

        if tier == "paid" and not SETTINGS.gemini_paid_key:
            return {
                "status": "error",
                "message": "Paid-режим требует отдельный GEMINI_PAID_API_KEY в .env.",
            }

        await database.set_world_state("llm_tier", tier)

        world_state = await database.get_all_world_states()
        current_model = world_state.get("gemini_model", "")
        if tier == "paid" and not current_model.startswith("gemini"):
            current_model = default_model_for_tier("paid")
            await database.set_world_state("gemini_model", current_model)

        if tier == "free" and not current_model:
            current_model = default_model_for_tier("free")
            await database.set_world_state("gemini_model", current_model)

        return {"status": "ok", "tier": tier, "model": current_model}

    @app.post("/api/spotlight")
    async def set_spotlight(data: dict):
        char_id = data.get("char_id", "ALL")
        await database.set_world_state("active_spotlight", char_id)
        if char_id != "ALL":
            await database.reset_spotlight_turns(char_id)
        return {"status": "ok", "spotlight": char_id}

    @app.post("/api/spotlight_settings")
    async def update_spotlight_settings(data: dict):
        if "max_turns" in data:
            await database.set_world_state("spotlight_max_turns", str(data["max_turns"]))
        return {"status": "ok"}

    @app.get("/api/available_models")
    async def get_available_models():
        world_state = await database.get_all_world_states()
        llm_tier = normalize_tier(world_state.get("llm_tier", SETTINGS.default_llm_tier))

        models = [
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "provider": "Google"},
            {"id": "gemini-2.5-flash-lite", "name": "Gemini 2.5 Flash-Lite", "provider": "Google"},
            {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash", "provider": "Google"},
            {"id": "gemini-3.1-flash-lite-preview", "name": "Gemini 3.1 Flash Lite", "provider": "Google"},
        ]
        if llm_tier != "paid" and hf_client:
            models.extend(
                [
                    {"id": "google/gemma-3-27b-it", "name": "Gemma 3 27B", "provider": "HuggingFace"},
                    {"id": "Qwen/Qwen2.5-72B-Instruct", "name": "Qwen 2.5 72B", "provider": "HuggingFace"},
                    {"id": "Qwen/Qwen3-32B", "name": "Qwen 3 32B", "provider": "HuggingFace"},
                ]
            )
        if llm_tier != "paid" and SETTINGS.ollama_url:
            try:
                async with httpx.AsyncClient(timeout=5.0) as httpx_client:
                    response = await httpx_client.get(f"{SETTINGS.ollama_url}/api/tags")
                    if response.status_code == 200:
                        tags = response.json().get("models", [])
                        for tag in tags:
                            name = tag.get("name")
                            models.append({"id": f"ollama/{name}", "name": f"Ollama: {name}", "provider": "Local"})
            except Exception as error:
                logger.warning(f"Не удалось получить список моделей Ollama: {error}")
                if SETTINGS.ollama_model:
                    models.append(
                        {
                            "id": f"ollama/{SETTINGS.ollama_model}",
                            "name": f"Ollama: {SETTINGS.ollama_model}",
                            "provider": "Local",
                        }
                    )

        if llm_tier != "paid" and SETTINGS.groq_key and SETTINGS.groq_key != "YOUR_GROQ_API_KEY_HERE":
            models.extend(
                [
                    {"id": "grq:llama-3.1-8b-instant", "name": "Groq: Llama 3.1 8B", "provider": "Groq"},
                    {"id": "grq:llama-3.3-70b-versatile", "name": "Groq: Llama 3.3 70B", "provider": "Groq"},
                    {"id": "grq:openai/gpt-oss-120b", "name": "Groq: GPT-OSS 120B (Adv)", "provider": "Groq"},
                    {"id": "grq:meta-llama/llama-4-scout-17b-16e-instruct", "name": "Groq: Llama 4 Scout", "provider": "Groq"},
                    {"id": "grq:groq/compound", "name": "Groq: Compound (Web Search)", "provider": "Groq"},
                    {"id": "grq:groq/compound-mini", "name": "Groq: Compound Mini", "provider": "Groq"},
                    {"id": "grq:qwen/qwen3-32b", "name": "Groq: Qwen 3 32B", "provider": "Groq"},
                ]
            )

        return {"models": models}

    @app.post("/api/roll_dice")
    async def roll_dice(data: dict):
        all_chars = await database.get_all_characters()
        char_info = next((char for char in all_chars if str(char["id"]) == str(data["char_id"])), None)
        if not char_info or not char_info["tg_id"]:
            return {"status": "error"}

        char_name = char_info["name"]
        result = int(data["result"])
        text = f"🎲 **{char_name}** бросает кости судьбы: **{result}**"
        if result == 20:
            text += "\n🔥 **КРИТИЧЕСКИЙ УСПЕХ!** Многоликий благоволит тебе."
        elif result == 1:
            text += "\n💀 **КРИТИЧЕСКИЙ ПРОВАЛ!** Тень сгущается."

        await bot.send_message(char_info["tg_id"], text, parse_mode="Markdown")
        story_roll = await register_story_dice_roll(char_info["id"], char_name, result)
        if story_roll.get("pending_resolved"):
            await continue_after_story_roll(story_roll)
        return {"status": "ok", "story_roll": story_roll.get("story_roll", False), "continued": story_roll.get("continued", False)}
