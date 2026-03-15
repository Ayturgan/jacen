import asyncio
import random
import re

from aiogram import F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

import database
from faq_utils import get_static_answer
from obsidian_utils import get_context
from bot_core.ai_service import find_location_image, generate_location_image, generate_text
from bot_core.config import ACTION_PATTERNS, DICE_PATTERNS, SETTINGS
from bot_core.continuity import get_continuity_guard, refresh_campaign_continuity
from bot_core.director import analyze_scene_turn, persist_director_notes
from bot_core.gameplay import (
    apply_ai_camera,
    continue_after_story_roll,
    deliver_game_response,
    launch_act,
    maybe_auto_advance_act,
    maybe_rotate_spotlight,
    pause_quest,
    prepare_game_response,
    register_story_dice_roll,
    remember_active_group,
    resume_quest,
)
from bot_core.guardrails import apply_continuity_guardrails
from bot_core.memory_layers import build_memory_snapshot
from bot_core.observability import log_generation_observability
from bot_core.prompts import (
    CLASSIFIER_SYSTEM_PROMPT,
    GAME_MASTER_SYSTEM_PROMPT,
    NORMAL_MODE_SYSTEM_PROMPT,
    NPC_SYSTEM_PROMPT_TEMPLATE,
    build_choice_prompt,
    build_classifier_prompt,
    build_game_master_prompt,
    build_normal_mode_prompt,
    build_npc_prompt,
)
from bot_core.resolution import resolve_action
from bot_core.runtime import bot, dp, pending_responses, logger
from bot_core.text_utils import parse_buttons, safe_reply, safe_send
from bot_core.world_dynamics import advance_world_turn


def register_bot_handlers():
    cached_bot_id: int | None = None

    def get_bound_character(all_chars: list[dict], user_id: int):
        return next((char for char in all_chars if char["tg_id"] == user_id), None)

    async def is_reply_to_bot(message: types.Message) -> bool:
        nonlocal cached_bot_id
        reply = message.reply_to_message
        if not reply or not reply.from_user:
            return False
        if cached_bot_id is None:
            me = await bot.get_me()
            cached_bot_id = me.id
        return reply.from_user.id == cached_bot_id

    async def capture_group_context(message: types.Message):
        if message.chat.type == "private":
            return
        await remember_active_group(message.chat.id, message.chat.title or "Игровая группа")

    async def get_character_prompt_context(char_id: str, char_info: dict | None):
        char_memory = await database.get_char_memory(char_id) if char_id != "Unknown" else {}
        whispers = await database.get_whispers(char_id) if char_id != "Unknown" else []
        return {
            "personal_ctx": char_memory.get("personal_context", ""),
            "char_last_action": char_memory.get("last_action", ""),
            "whispers": whispers,
            "char_info": char_info,
        }

    async def classify_player_message(message_text: str) -> str:
        text_lower = message_text.lower()
        if any(re.search(pattern, text_lower) for pattern in ACTION_PATTERNS):
            return "ACTION"

        answer = await generate_text(
            build_classifier_prompt(message_text),
            system_prompt=CLASSIFIER_SYSTEM_PROMPT,
            temperature=0.1,
        )
        return "ACTION" if answer.strip().upper() == "ACTION" else "CHAT"

    def strip_technical_tags(text: str) -> str:
        return re.sub(r"\[.*?\]", "", text).strip()

    async def queue_action_for_admin(message: types.Message, char_id: str, answer: str, image_path: str | None, fallback_tags: list[str] | None = None):
        message_id = message.message_id
        pending_responses[message_id] = {
            "text": answer,
            "chat_id": message.chat.id,
            "char_id": char_id,
            "image": image_path,
            "player_message": message.text,
            "fallback_tags": fallback_tags or [],
        }
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Отправить", callback_data=f"send_{message_id}"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data=f"cancel_{message_id}"),
                ]
            ]
        )

        preview_text = f"🎲 **ДЕЙСТВИЕ ({char_id}):** {message.text}\n🤖:\n{answer}"
        if image_path:
            caption = preview_text[:1000] + ("..." if len(preview_text) > 1000 else "")
            await bot.send_photo(SETTINGS.admin_id, photo=types.FSInputFile(image_path), caption=caption, reply_markup=keyboard)
        else:
            await safe_send(SETTINGS.admin_id, preview_text, reply_markup=keyboard)

    async def process_quest_message(message: types.Message, all_chars: list[dict], char_info: dict | None, is_mentioned: bool):
        user_id = message.from_user.id
        char_id = char_info["id"] if char_info else "Unknown"
        world_state = await database.get_all_world_states()
        quest_started = world_state.get("quest_started", "0") == "1"

        player_ids = [char["tg_id"] for char in all_chars if char["tg_id"]]
        if user_id not in player_ids and user_id != SETTINGS.admin_id:
            return

        if not quest_started:
            if is_mentioned:
                await message.reply("_Якен ждёт знака от Владыки, чтобы начать историю..._ (Используйте /quest)")
            return

        if message.chat.type != "private":
            await capture_group_context(message)

        if world_state.get("quest_paused", "0") == "1":
            pause_reason = world_state.get("quest_pause_reason", "")
            await message.reply(
                (
                    "_Нить судьбы временно удержана._\n"
                    f"Причина паузы: _{pause_reason or 'Игроки решили остановиться здесь.'}_\n"
                    "Продолжение вернёт Владыка командой `/quest resume` или через админку."
                ),
                parse_mode="Markdown",
            )
            return

        spotlight = world_state.get("active_spotlight", "ALL")
        if spotlight != "ALL" and char_id != spotlight and char_id != "Unknown":
            await database.set_world_state("active_spotlight", "ALL")

        pending_roll_char = world_state.get("pending_roll_char", "")
        if pending_roll_char:
            pending_reason = world_state.get("pending_roll_reason", "")
            pending_char = next((char for char in all_chars if char["id"] == pending_roll_char), None)
            pending_name = pending_char["name"] if pending_char else pending_roll_char
            if char_id == pending_roll_char:
                await message.reply(
                    (
                        "_Судьба ещё не услышала стук твоей кости._\n"
                        f"*{pending_name}*, брось кубик в чате или в приложении.\n"
                        f"Причина: _{pending_reason or 'Сцена ждёт ответа.'}_"
                    ),
                    parse_mode="Markdown",
                )
            else:
                await message.reply(
                    (
                        f"_Якен ждёт бросок от_ *{pending_name}*.\n"
                        f"Пока причина не решена, сцена не пойдёт дальше: _{pending_reason or 'Судьба молчит.'}_"
                    ),
                    parse_mode="Markdown",
                )
            return

        message_type = await classify_player_message(message.text)
        vault_info = await get_context(message.text, char_id=char_id, world_state=world_state)
        session_history = await database.get_recent_events(5)
        prompt_context = await get_character_prompt_context(char_id, char_info)
        director_notes = await analyze_scene_turn(
            char_id=char_id,
            message_text=message.text,
            world_state=world_state,
            session_history=session_history,
            char_info=prompt_context["char_info"],
            personal_ctx=prompt_context["personal_ctx"],
            char_last_action=prompt_context["char_last_action"],
            vault_info=vault_info,
            model=world_state.get("gemini_model", "gemini-2.5-flash"),
        )
        await persist_director_notes(director_notes)
        world_state = await database.get_all_world_states()
        continuity_notes = get_continuity_guard(world_state, prompt_context["char_info"])
        resolution_notes = None

        if "ACTION" in message_type:
            resolution_notes = await resolve_action(
                char_id=char_id,
                message_text=message.text,
                world_state=world_state,
                session_history=session_history,
                char_info=prompt_context["char_info"],
                personal_ctx=prompt_context["personal_ctx"],
                char_last_action=prompt_context["char_last_action"],
                vault_info=vault_info,
                director_notes=director_notes,
                model=world_state.get("gemini_model", "gemini-2.5-flash"),
            )

        prompt = build_game_master_prompt(
            char_id=char_id,
            message_text=message.text,
            world_state=world_state,
            session_history=session_history,
            char_info=prompt_context["char_info"],
            personal_ctx=prompt_context["personal_ctx"],
            char_last_action=prompt_context["char_last_action"],
            whispers=prompt_context["whispers"],
            vault_info=vault_info,
            director_notes=director_notes,
            resolution_notes=resolution_notes,
            continuity_notes=continuity_notes,
        )

        memory_snapshot = build_memory_snapshot(world_state, char_id)
        await log_generation_observability(
            char_id=char_id,
            world_state=world_state,
            vault_info=vault_info,
            memory_snapshot=memory_snapshot,
        )

        answer = await generate_text(prompt, system_prompt=GAME_MASTER_SYSTEM_PROMPT, temperature=0.65)
        answer, guard_issues = apply_continuity_guardrails(
            text=answer,
            world_state=world_state,
            continuity_notes=continuity_notes,
        )
        if guard_issues:
            await database.add_game_event("guardrail", f"{char_id}: {', '.join(guard_issues)}")
        ai_camera = None
        gm_action_mode = world_state.get("gm_action_mode", "auto")
        fallback_tags = None

        if resolution_notes:
            fallback_tags = [
                *resolution_notes.get("mechanical_directives", []),
                *resolution_notes.get("knowledge_directives", []),
            ]

        if "ACTION" in message_type:
            if re.search(r"\[КАМЕРА:\s*(\w+)\]", answer, re.IGNORECASE):
                ai_camera = "PENDING_ACTION"
            image_path = await find_location_image(f"{answer} {message.text}")
            if not image_path:
                image_path = await generate_location_image(f"{answer} {message.text}")
            if gm_action_mode == "review":
                await queue_action_for_admin(
                    message,
                    char_id,
                    answer,
                    image_path,
                    fallback_tags=fallback_tags,
                )
            else:
                clean_answer, ai_camera = await deliver_game_response(
                    text=answer,
                    chat_id=message.chat.id,
                    char_id=char_id,
                    image_path=image_path,
                    fallback_tags=fallback_tags,
                )
                await advance_world_turn(
                    char_id=char_id,
                    player_message=message.text,
                    gm_response=clean_answer,
                    chat_id=message.chat.id,
                )
                world_state = await database.get_all_world_states()
                await refresh_campaign_continuity(
                    char_id=char_id,
                    player_message=message.text,
                    gm_response=clean_answer,
                    world_state=world_state,
                    session_history=await database.get_recent_events(12),
                    model=world_state.get("gemini_model", "gemini-2.5-flash"),
                )
                await maybe_auto_advance_act(message.chat.id)
                await database.add_game_event("director", f"{char_id}: {director_notes.get('beat', '')} | {director_notes.get('scene_phase', '')}")
        else:
            clean_answer, buttons_markup, ai_camera = await prepare_game_response(answer, message.chat.id)
            await safe_reply(message, clean_answer, reply_markup=buttons_markup)
            await advance_world_turn(
                char_id=char_id,
                player_message=message.text,
                gm_response=clean_answer,
                chat_id=message.chat.id,
            )
            world_state = await database.get_all_world_states()
            await refresh_campaign_continuity(
                char_id=char_id,
                player_message=message.text,
                gm_response=clean_answer,
                world_state=world_state,
                session_history=await database.get_recent_events(12),
                model=world_state.get("gemini_model", "gemini-2.5-flash"),
            )
            await maybe_auto_advance_act(message.chat.id)
            await database.add_game_event("chat", f"{char_id}: {clean_answer[:80]}...")
            await database.add_game_event("director", f"{char_id}: {director_notes.get('beat', '')} | {director_notes.get('scene_phase', '')}")

        if char_id != "Unknown":
            await database.update_char_memory(
                char_id,
                last_action=f"{message.text[:100]} -> {answer[:100]}",
                last_location=world_state.get("current_location", ""),
            )
            await maybe_rotate_spotlight(char_id, all_chars, message.chat.id, ai_camera)

    async def process_normal_message(message: types.Message):
        prompt = build_normal_mode_prompt(message.text)
        answer = await generate_text(prompt, system_prompt=NORMAL_MODE_SYSTEM_PROMPT, temperature=0.6)
        await safe_reply(message, answer)

    @dp.message(Command("start"))
    async def start_cmd(message: types.Message):
        user_id = message.from_user.id
        if message.chat.type == "private":
            button_text = "🧙‍♂️ Панель Якен" if user_id == SETTINGS.admin_id else "🎴 Мой Персонаж"
            app_url = f"{SETTINGS.webapp_url}?uid={user_id}"
            markup = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=button_text, web_app=WebAppInfo(url=app_url))]],
                resize_keyboard=True,
            )
            await message.reply(
                "Человек пришел вовремя. Якен будет слушать твои слова и записывать твою историю. Открой книгу судеб ниже.",
                reply_markup=markup,
                parse_mode="Markdown",
            )
            return

        bot_info = await bot.get_me()
        markup = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎭 Открыть книгу судеб", url=f"https://t.me/{bot_info.username}")]
            ]
        )
        await message.reply(
            "Человек обращается к Якену в шумном месте. Книга судеб открывается лишь наедине.\nПерейди в личные сообщения с тенью.",
            reply_markup=markup,
            parse_mode="Markdown",
        )

    @dp.message(Command("help"))
    async def help_cmd(message: types.Message):
        text = (
            "👁 *Команды Якена*\n\n"
            "*Для всех игроков:*\n"
            "🔹 `/start` — Открыть личную книгу судеб\n"
            "🔹 `/help` — Список всех команд\n"
            "🔹 `/guide` или `/гайд` — Подробный гайд по игре\n"
            "🔹 `/join [ID]` — Привязать себя к персонажу\n"
            "   _Пример: `/join Elix`_\n\n"
            "🎲 *Бросок костей:*\n"
            "Напиши в чат: _«Якен, брось кубик»_, _«Якен, roll d20»_, _«Якен, кинь кость»_.\n"
            "Если квест активен, бросок может повлиять на сюжет.\n\n"
            "*Только для ГМ/админа:*\n"
            "🔸 `/mode [normal|quest]` — Режим бота (обычный/игровой)\n"
            "🔸 `/brain [free|paid|status]` — Переключение режима мозга (ключи Free/Paid)\n"
            "🔸 `/quest` — Запустить или продолжить квестовый поток\n"
            "🔸 `/quest pause [причина]` — Пауза квеста\n"
            "🔸 `/quest resume` — Снять паузу\n"
            "🔸 `/quest stop` — Полная остановка и сброс мира\n"
            "🔸 `/pausequest [причина]` — Короткая команда паузы\n"
            "🔸 `/resumequest` — Короткая команда продолжения\n"
            "🔸 `/stopquest` — Короткая команда остановки\n"
            "🔸 `/npc [Имя] [Реплика]` — Речь от лица NPC\n"
            "   _Пример: `/npc Малакор Цена правды — кровь.`_\n\n"
            "_Якен ведёт квест как ГМ. Админка — для наблюдения, паузы и служебного контроля._"
        )
        await message.reply(text, parse_mode="Markdown")

    @dp.message(Command("guide"))
    @dp.message(Command("гайд"))
    async def guide_cmd(message: types.Message):
        guide_text = (
            "📖 *Гайд по кампании «Эхо Драконьей крови»*\n\n"
            "*1) Сеттинг мира*\n"
            "Ты в тёмном Эссосе: заговоры Домов, тени Валирии, долги Безликих и живые последствия выбора.\n"
            "Каждый акт меняет мир: фракции двигаются, NPC запоминают, тайны раскрываются не всем сразу.\n\n"
            "*2) Как начать играть*\n"
            "1. Открой бота командой `/start` в личке.\n"
            "2. Привяжи персонажа: `/join Elix` (или другой ID).\n"
            "3. Дождись, когда ГМ переведёт режим в `quest`.\n"
            "4. Пиши действия и реплики в духе сцены: что делаешь, куда идёшь, с кем говоришь, чем рискуешь.\n\n"
            "*3) Если игрок пока не привязал персонажа*\n"
            "- В группе Якен не будет вести его как героя квеста.\n"
            "- Нужно зайти в личку бота и выполнить `/join [ID]`.\n"
            "- Узнать доступные ID можно командой `/join` без аргументов.\n\n"
            "*4) Как лучше писать ход*\n"
            "- Коротко и конкретно: цель, действие, риск.\n"
            "- Пример: _«Я обхожу двор с тыла и ищу следы телеги у ворот.»_\n"
            "- Если нужен шанс судьбы — попроси бросок кубика в чате.\n\n"
            "*5) Что важно помнить*\n"
            "- Якен в квесте — только ГМ, не отдельный участник партии.\n"
            "- Инвентарь, шёпоты и знания влияют на ход сцены.\n"
            "- Выбор игроков формирует путь внутри акта; последствия не исчезают."
        )
        await message.reply(guide_text, parse_mode="Markdown")

    @dp.message(Command("mode"))
    async def mode_cmd(message: types.Message):
        if message.from_user.id != SETTINGS.admin_id:
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2 or args[1] not in {"normal", "quest"}:
            await message.reply("Использование: /mode normal или /mode quest")
            return

        mode = args[1]
        await database.set_world_state("bot_mode", mode)
        if mode == "normal":
            await database.set_world_state("active_spotlight", "ALL")
        if mode == "quest":
            await message.reply(
                "Режим переключен: **quest**\n\n_Чтобы начать сцену, запусти `/quest`._",
                parse_mode="Markdown",
            )
            return
        await message.reply(f"Режим переключен: **{mode}**", parse_mode="Markdown")

    @dp.message(Command("brain"))
    async def brain_cmd(message: types.Message):
        if message.from_user.id != SETTINGS.admin_id:
            return

        args = message.text.split(maxsplit=1)
        if len(args) < 2:
            world_state = await database.get_all_world_states()
            tier = world_state.get("llm_tier", "free")
            model = world_state.get("gemini_model", database.get_default_gemini_model(tier))
            await message.reply(
                (
                    "🧠 *Режим мозга*\n"
                    f"- Tier: **{tier}**\n"
                    f"- Модель: `{model}`\n\n"
                    "Использование: `/brain free`, `/brain paid`, `/brain status`"
                ),
                parse_mode="Markdown",
            )
            return

        action = args[1].strip().lower()
        if action in {"status", "статус"}:
            world_state = await database.get_all_world_states()
            tier = world_state.get("llm_tier", "free")
            model = world_state.get("gemini_model", database.get_default_gemini_model(tier))
            await message.reply(
                f"🧠 Текущий режим: **{tier}**\nМодель: `{model}`",
                parse_mode="Markdown",
            )
            return

        if action not in {"free", "paid"}:
            await message.reply("Использование: /brain free, /brain paid, /brain status")
            return

        if action == "paid" and not SETTINGS.gemini_paid_key:
            await message.reply(
                "Paid-режим недоступен: в `.env` не задан `GEMINI_PAID_API_KEY`.",
                parse_mode="Markdown",
            )
            return

        await database.set_world_state("llm_tier", action)
        world_state = await database.get_all_world_states()
        current_model = world_state.get("gemini_model", "")

        if action == "paid" and not current_model.startswith("gemini"):
            current_model = database.get_default_gemini_model("paid")
            await database.set_world_state("gemini_model", current_model)
        elif action == "free" and not current_model:
            current_model = database.get_default_gemini_model("free")
            await database.set_world_state("gemini_model", current_model)

        await message.reply(
            f"🧠 Режим мозга переключен: **{action}**\nМодель: `{current_model}`",
            parse_mode="Markdown",
        )

    @dp.message(Command("join"))
    async def join_cmd(message: types.Message):
        args = message.text.split()
        if len(args) < 2:
            chars = await database.get_all_characters()
            char_list = "\n".join([f"- {char['id']} ({char['name']})" for char in chars])
            await message.reply(f"Кого ты выберешь?\nИспользуй команду: /join [ID]\n\nДоступные души:\n{char_list}")
            return

        char_id = args[1]
        char_data = await database.get_character(char_id)
        if not char_data:
            await message.reply("Такой души не существует.")
            return

        await database.update_player_id(char_id, message.from_user.id)
        await message.reply(
            f"Твоя судьба теперь неразрывно связана с персонажем: **{char_data['name']}**.\n_Открой книгу судеб через 'Мой Персонаж'._",
            parse_mode="Markdown",
        )

    @dp.message(Command("npc"))
    async def npc_cmd(message: types.Message):
        if message.from_user.id != SETTINGS.admin_id:
            return

        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            await message.reply("Использование: /npc [Имя_NPC] [Сообщение/Вопрос к NPC]")
            return

        npc_name = args[1]
        npc_query = args[2]
        session_history = await database.get_recent_events(5)
        prompt = build_npc_prompt(npc_name, npc_query, session_history)
        system_prompt = NPC_SYSTEM_PROMPT_TEMPLATE.format(npc_name=npc_name)

        try:
            answer = await generate_text(prompt, system_prompt=system_prompt, temperature=0.7)
            await safe_reply(message, f"🗣 **{npc_name}:**\n\n{answer}")
            await database.add_game_event("npc_dialog", f"{npc_name} сказал: {answer[:100]}...")
        except Exception as error:
            await message.reply(f"NPC молчит. Ошибка: {error}")

    @dp.message(Command("quest"))
    async def quest_cmd(message: types.Message):
        if message.from_user.id != SETTINGS.admin_id:
            await message.reply("Этот путь закрыт. Только Владыка может начинать квесты.")
            return

        await capture_group_context(message)
        args = message.text.split(maxsplit=2)
        action = args[1].lower() if len(args) > 1 else "start"

        if action == "pause":
            reason = args[2] if len(args) > 2 else ""
            result = await pause_quest(
                reason=reason,
                chat_id=message.chat.id if message.chat.type != "private" else None,
                chat_title=message.chat.title if message.chat.type != "private" else None,
                announce=False,
            )
            await safe_reply(message, result["message"])
            return

        if action == "resume":
            result = await resume_quest(
                chat_id=message.chat.id if message.chat.type != "private" else None,
                chat_title=message.chat.title if message.chat.type != "private" else None,
                announce=False,
            )
            await safe_reply(message, result["message"])
            return

        if action == "stop":
            pending_responses.clear()
            await database.reset_game_state()
            await safe_reply(
                message,
                "🕯 *Текущий виток судьбы оборван.*\n\nМир очищен. Следующая команда `/quest` начнёт уже новую игру.",
            )
            return

        if action != "start":
            await message.reply("Использование: /quest, /quest pause [причина], /quest resume, /quest stop")
            return

        world_state = await database.get_all_world_states()
        if world_state.get("quest_started", "0") == "1":
            if world_state.get("quest_paused", "0") == "1":
                result = await resume_quest(
                    chat_id=message.chat.id if message.chat.type != "private" else None,
                    chat_title=message.chat.title if message.chat.type != "private" else None,
                    announce=False,
                )
                await safe_reply(message, result["message"])
                return

            await safe_reply(
                message,
                "⚠️ *Квест уже активен.*\n\nТекущая сцена продолжается. Используй `/quest pause`, `/quest resume` или `/quest stop`.",
            )
            return

        act = world_state.get("current_act", "1") or "1"
        scene = world_state.get("current_scene", "") or "Таверна «Пьяный Кракен»"
        location = world_state.get("current_location", "") or "Волантис"
        await message.reply("Квест запущен. Рассылаю видение игрокам...")
        try:
            await launch_act(act, scene, location)
            logger.info("Scene launch completed and announcement delivered.")
        except Exception as error:
            logger.error(f"Quest launch error: {error}")
            await safe_reply(message, f"Тень сорвалась на старте сцены. Ошибка: {error}")

    @dp.message(Command("pausequest"))
    async def pause_quest_cmd(message: types.Message):
        if message.from_user.id != SETTINGS.admin_id:
            return
        reason = message.text.split(maxsplit=1)[1] if len(message.text.split(maxsplit=1)) > 1 else ""
        await capture_group_context(message)
        result = await pause_quest(
            reason=reason,
            chat_id=message.chat.id if message.chat.type != "private" else None,
            chat_title=message.chat.title if message.chat.type != "private" else None,
            announce=False,
        )
        await safe_reply(message, result["message"])

    @dp.message(Command("resumequest"))
    async def resume_quest_cmd(message: types.Message):
        if message.from_user.id != SETTINGS.admin_id:
            return
        await capture_group_context(message)
        result = await resume_quest(
            chat_id=message.chat.id if message.chat.type != "private" else None,
            chat_title=message.chat.title if message.chat.type != "private" else None,
            announce=False,
        )
        await safe_reply(message, result["message"])

    @dp.message(Command("stopquest"))
    async def stop_quest_cmd(message: types.Message):
        if message.from_user.id != SETTINGS.admin_id:
            return
        pending_responses.clear()
        await database.reset_game_state()
        await safe_reply(
            message,
            "🕯 *Текущий виток судьбы оборван.*\n\nПамять этой игры очищена. Следующий запуск квеста начнёт новую историю.",
        )

    @dp.message(F.web_app_data)
    async def handle_webapp_data(message: types.Message):
        data = message.web_app_data.data
        if not data.startswith("[КУБИК_ИГРОКА]"):
            return

        result = data.replace("[КУБИК_ИГРОКА]", "").strip()
        all_chars = await database.get_all_characters()
        char_name = next((char["name"] for char in all_chars if char["tg_id"] == message.from_user.id), message.from_user.full_name)
        text = f"🎲 **{char_name}** бросает кости судьбы: **{result}**"
        if result == "20":
            text += "\n🔥 **КРИТИЧЕСКИЙ УСПЕХ!** Многоликий благоволит тебе."
        elif result == "1":
            text += "\n💀 **КРИТИЧЕСКИЙ ПРОВАЛ!** Тень сгущается."
        await message.answer(text, parse_mode="Markdown")
        bound_char = next((char for char in all_chars if char["tg_id"] == message.from_user.id), None)
        if bound_char:
            roll_info = await register_story_dice_roll(bound_char["id"], char_name, int(result))
            if roll_info.get("pending_resolved"):
                await continue_after_story_roll(roll_info)

    @dp.message(F.text)
    async def handle_msg(message: types.Message):
        if not message.text:
            return

        if message.text.startswith("/"):
            return

        text_lower = message.text.lower()
        is_mentioned = "якен" in text_lower
        is_admin = message.from_user.id == SETTINGS.admin_id
        reply_to_bot = await is_reply_to_bot(message) if message.chat.type != "private" else False
        should_answer = message.chat.type == "private" or is_mentioned or reply_to_bot

        if should_answer and any(pattern in text_lower for pattern in DICE_PATTERNS):
            all_chars = await database.get_all_characters()
            bound_char = next((char for char in all_chars if char["tg_id"] == message.from_user.id), None)
            char_name = bound_char["name"] if bound_char else message.from_user.full_name
            world_state = await database.get_all_world_states()
            is_in_game = world_state.get("bot_mode") == "quest" and world_state.get("quest_started", "0") == "1" and world_state.get("quest_paused", "0") != "1" and bound_char is not None
            await bot.send_dice(message.chat.id, emoji="🎲")
            await asyncio.sleep(3.5)
            result = random.randint(1, 20)
            response_text = f"🎲 **{char_name}** бросает кости судьбы: **{result}**"
            if result == 20:
                response_text += "\n🔥 **КРИТИЧЕСКИЙ УСПЕХ!** Многоликий благоволит тебе."
            elif result == 1:
                response_text += "\n💀 **КРИТИЧЕСКИЙ ПРОВАЛ!** Тень сгущается."
            if not is_in_game:
                response_text += "\n_Сейчас это внеигровой бросок: судьба отмечает его, но сюжет не меняет._"
            await message.reply(response_text, parse_mode="Markdown")
            roll_info = await register_story_dice_roll(bound_char["id"] if bound_char else None, char_name, result)
            if roll_info.get("pending_resolved"):
                await continue_after_story_roll(roll_info)
            return

        static_answer = get_static_answer(message.text)
        if static_answer and should_answer:
            await message.reply(static_answer)
            return

        if message.chat.type != "private" and not is_mentioned and not reply_to_bot:
            return

        if message.chat.type != "private":
            await capture_group_context(message)

        all_chars = await database.get_all_characters()
        char_info = get_bound_character(all_chars, message.from_user.id)
        world_state = await database.get_all_world_states()
        bot_mode = world_state.get("bot_mode", "normal")

        try:
            if bot_mode == "quest":
                await process_quest_message(message, all_chars, char_info, is_mentioned)
            else:
                await process_normal_message(message)
        except Exception as error:
            logger.error(f"Message handling error: {error}")
            await safe_reply(message, "Тень дрогнула. Человеку нужно мгновение, чтобы собрать мысли.")

    @dp.callback_query(F.data.startswith("send_"))
    async def process_send(callback: types.CallbackQuery):
        world_state = await database.get_all_world_states()
        if world_state.get("quest_paused", "0") == "1":
            await callback.answer("Квест сейчас на паузе. Сначала возобнови его.", show_alert=True)
            return

        message_id = int(callback.data.split("_")[1])
        data = pending_responses.get(message_id)
        if not data:
            return

        clean_text, _ = await deliver_game_response(
            text=data["text"],
            chat_id=data["chat_id"],
            char_id=data["char_id"],
            image_path=data.get("image"),
            fallback_tags=data.get("fallback_tags"),
        )
        await advance_world_turn(
            char_id=data["char_id"],
            player_message=data.get("player_message") or "Действие было подтверждено ГМ.",
            gm_response=clean_text,
            chat_id=data["chat_id"],
        )
        world_state = await database.get_all_world_states()
        await refresh_campaign_continuity(
            char_id=data["char_id"],
            player_message=data.get("player_message") or "Действие было подтверждено ГМ.",
            gm_response=clean_text,
            world_state=world_state,
            session_history=await database.get_recent_events(12),
            model=world_state.get("gemini_model", "gemini-2.5-flash"),
        )
        await maybe_auto_advance_act(data["chat_id"])

        await callback.message.delete()
        del pending_responses[message_id]

    @dp.callback_query(F.data.startswith("choice_"))
    async def process_choice(callback: types.CallbackQuery):
        world_state = await database.get_all_world_states()
        if world_state.get("quest_paused", "0") == "1":
            await callback.answer("Квест стоит на паузе. Выбор подождёт до продолжения.", show_alert=True)
            return

        choice_text = callback.data.replace("choice_", "")
        try:
            await callback.message.delete()
        except Exception:
            await callback.message.edit_reply_markup(reply_markup=None)

        user_id = callback.from_user.id
        chat_id = callback.message.chat.id
        all_chars = await database.get_all_characters()
        char_info = get_bound_character(all_chars, user_id)
        char_id = char_info["id"] if char_info else "Unknown"
        world_state = await database.get_all_world_states()

        try:
            vault_info = await get_context(choice_text, char_id=char_id, world_state=world_state)
            session_history = await database.get_recent_events(5)
            prompt_context = await get_character_prompt_context(char_id, char_info)
            director_notes = await analyze_scene_turn(
                char_id=char_id,
                message_text=f"Игрок выбрал вариант: {choice_text}",
                world_state=world_state,
                session_history=session_history,
                char_info=prompt_context["char_info"],
                personal_ctx=prompt_context["personal_ctx"],
                char_last_action=prompt_context["char_last_action"],
                vault_info=vault_info,
                model=world_state.get("gemini_model", "gemini-2.5-flash"),
            )
            await persist_director_notes(director_notes)
            world_state = await database.get_all_world_states()
            continuity_notes = get_continuity_guard(world_state, prompt_context["char_info"])
            prompt = build_choice_prompt(
                char_id=char_id,
                choice_text=choice_text,
                world_state=world_state,
                session_history=session_history,
                char_info=prompt_context["char_info"],
                personal_ctx=prompt_context["personal_ctx"],
                char_last_action=prompt_context["char_last_action"],
                whispers=prompt_context["whispers"],
                vault_info=vault_info,
                director_notes=director_notes,
                continuity_notes=continuity_notes,
            )
            memory_snapshot = build_memory_snapshot(world_state, char_id)
            await log_generation_observability(
                char_id=char_id,
                world_state=world_state,
                vault_info=vault_info,
                memory_snapshot=memory_snapshot,
            )
            answer = await generate_text(prompt, system_prompt=GAME_MASTER_SYSTEM_PROMPT, temperature=0.65)
            answer, guard_issues = apply_continuity_guardrails(
                text=answer,
                world_state=world_state,
                continuity_notes=continuity_notes,
            )
            if guard_issues:
                await database.add_game_event("guardrail", f"{char_id}: {', '.join(guard_issues)}")
            clean_answer, buttons_markup, _ = await prepare_game_response(answer, chat_id)
            await safe_send(chat_id, clean_answer, reply_markup=buttons_markup)
            await advance_world_turn(
                char_id=char_id,
                player_message=f"Выбор игрока: {choice_text}",
                gm_response=clean_answer,
                chat_id=chat_id,
            )
            world_state = await database.get_all_world_states()
            await refresh_campaign_continuity(
                char_id=char_id,
                player_message=f"Выбор игрока: {choice_text}",
                gm_response=clean_answer,
                world_state=world_state,
                session_history=await database.get_recent_events(12),
                model=world_state.get("gemini_model", "gemini-2.5-flash"),
            )
            await maybe_auto_advance_act(chat_id)
            await database.add_game_event("choice", f"{char_id} выбрал: {choice_text}")
            await database.add_game_event("director", f"{char_id}: {director_notes.get('beat', '')} | {director_notes.get('scene_phase', '')}")
        except Exception as error:
            logger.error(f"Choice handler error: {error}")
            await safe_send(chat_id, "Тень на миг потеряла нить выбора. Попробуй снова.")

    @dp.callback_query(F.data.startswith("cancel_"))
    async def process_cancel(callback: types.CallbackQuery):
        message_id = int(callback.data.split("_")[1])
        pending_responses.pop(message_id, None)
        await callback.message.delete()
