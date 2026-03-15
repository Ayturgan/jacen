import asyncio
import json
import re
from datetime import datetime, timezone

from aiogram import types

import database
from obsidian_utils import get_context
from bot_core.ai_service import generate_location_image, generate_text
from bot_core.continuity import get_continuity_guard, refresh_campaign_continuity
from bot_core.director import analyze_scene_turn, persist_director_notes
from bot_core.guardrails import apply_continuity_guardrails
from bot_core.memory_layers import build_memory_snapshot
from bot_core.observability import log_generation_observability
from bot_core.prompts import GAME_MASTER_SYSTEM_PROMPT, build_game_master_prompt
from bot_core.runtime import bot, logger
from bot_core.summarizer import run_summarizer_if_needed
from bot_core.text_utils import parse_buttons, safe_send
from bot_core.world_dynamics import advance_world_turn, initialize_world_dynamics


ACT_BLUEPRINTS = {
    "1": {"scene": "Таверна «Пьяный Кракен»", "location": "Волантис"},
    "2": {"scene": "Пыль и кости на старом тракте", "location": "Дорога Костей"},
    "3": {"scene": "Мёртвый Оазис и тени воды", "location": "Мёртвый Оазис"},
    "4": {"scene": "Пепел над чёрной кромкой моря", "location": "Пепельное Море"},
    "5": {"scene": "Шёпоты на борту «Тайэрис»", "location": "Корабль Тайэрис"},
    "6": {"scene": "Эпилог: Цена имён", "location": "Руины Тайэриса"},
}


ACT_OPENINGS = {
    "1": "Волантис дышит жаром, долгами и кровью. На улицах шепчут о драконьей метке, а по набережным уже ходят люди Инквизиции.",
    "2": "Следы из Волантиса выводят героев на дорогу, где у каждой кости есть имя. Охота становится открытой.",
    "3": "Мёртвый Оазис хранит механизмы и тайны, которые лучше не будить. Но именно здесь можно узнать правду о печати.",
    "4": "Пепельное Море отвечает только сильным. Ошибки прошлых актов поднимаются из пепла и требуют цены.",
    "5": "На борту «Тайэрис» сходятся долги, кровь и имя. Всё, что было посеяно раньше, теперь даёт плод.",
    "6": "Эпилог не про победу, а про цену. Мир не забывает, кем герои стали по дороге.",
}


ACT_PROLOGUES = {
    "1": (
        "Волантис живёт на острие торговли, клятв и крови. Ночью на пристанях шепчут о драконьей метке, "
        "а днём улицы слушают тех, у кого длиннее нож. В этом акте герои впервые войдут в чужую игру, "
        "где каждый союз временный, а каждая услуга имеет цену."
    ),
    "2": (
        "Дорога Костей не прощает тех, кто идёт без памяти о прошлом. Старые решения догоняют героев в лицах новых врагов, "
        "а след Инквизиции становится заметнее с каждым днём. В этом акте правда уже не прячется — она требует расплаты."
    ),
    "3": (
        "Мёртвый Оазис встречает тишиной, в которой слышно, как ломаются клятвы. Здесь механизмы древних и воля живых "
        "сталкиваются в одной точке. В этом акте знание даёт силу, но почти всегда отнимает покой."
    ),
    "4": (
        "Пепельное Море поднимает на поверхность всё, что пытались похоронить раньше. Враги меняют маски, но не намерения, "
        "а мир становится жестче к слабым решениям. Этот акт проверяет не удачу, а цену выбранного пути."
    ),
    "5": (
        "На борту «Тайэрис» сходятся долги, имена и кровь прошлых актов. Здесь уже нельзя притворяться, что выборов не было: "
        "каждый шаг имеет наследие. Этот акт — про развязки, которые герои сами приблизили."
    ),
    "6": (
        "Эпилог мира не обнуляет прошлое — он закрепляет его. Кто-то сохранит имя, кто-то потеряет его, но никто не выйдет прежним. "
        "Здесь судьба не задаёт новых вопросов, а собирает ответы за всю кампанию."
    ),
}


ACT_SCENE_OPENERS = {
    "1": "Вечер в «Пьяном Кракене» густой от дыма, соли и чужих долгов. На втором этаже кто‑то спорит шёпотом о метке драконьей крови, а у стойки уже ищут тех, кто готов на грязную работу.",
    "2": "На Дороге Костей ветер несёт пепел и имена мёртвых. Вдалеке движется караван без гербов, и слишком много глаз следит за ним из пыли.",
    "3": "Мёртвый Оазис встречает не тишиной, а звуком старого механизма под камнем. Вода здесь холоднее, чем должна быть, а каждый отражённый огонь кажется чужим.",
    "4": "У Пепельного Моря ночь не темнее дня — просто честнее. Волны бьют о чёрный берег, и среди пены всплывает то, что должно было остаться забытым.",
    "5": "На палубе «Тайэрис» слышно, как скрипит дерево под тяжестью невыплаченных долгов. Фонари качаются на ветру, и каждый шаг здесь — будто подпись под приговором.",
    "6": "В эпилоге мир уже не спорит с героями — он подводит счёт. Старые клятвы всплывают в лицах живых, и тишина перед развязкой звучит громче битвы.",
}


def _load_open_loops(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        return []
    return []


def _build_carryover_block(previous_world_state: dict) -> str:
    campaign_summary = (previous_world_state.get("campaign_summary", "") or previous_world_state.get("long_term_memory", "")).strip()
    last_world_event = previous_world_state.get("last_world_event", "").strip()
    continuity_note = previous_world_state.get("continuity_last_updated", "").strip()
    open_loops = _load_open_loops(previous_world_state.get("campaign_open_loops", "[]"))

    lines = []
    if campaign_summary:
        lines.append(f"- Память прошлого акта: {campaign_summary}")
    if last_world_event:
        lines.append(f"- Последний сдвиг мира: {last_world_event}")
    if continuity_note:
        lines.append(f"- Что изменилось на самом деле: {continuity_note}")
    if open_loops:
        loops_preview = "; ".join(open_loops[:2])
        lines.append(f"Незакрытые нити: {loops_preview}")

    if not lines:
        return ""

    merged = " ".join(line.lstrip("- ").strip() for line in lines)
    merged = re.sub(r"\s+", " ", merged).strip()
    return merged


def _build_intro_roster(active_chars: list[dict]) -> str:
    if not active_chars:
        return "- Пока в кадре тишина: активных героев нет. Привяжите персонажей через `/join [ID]`."
    lines = []
    for char in active_chars[:6]:
        lines.append(f"- {char.get('name', char.get('id'))} уже в этой сцене.")
    return "\n".join(lines)


async def _pick_initial_spotlight(active_chars: list[dict]) -> str:
    active_ids = {char.get("id") for char in active_chars}
    if "Elix" in active_ids and "Silas" in active_ids:
        return "ALL"
    if "Elix" in active_ids:
        return "Elix"
    if active_chars:
        return active_chars[0].get("id", "ALL")
    return "ALL"


def _build_auto_scene_kickoff(
    act: str,
    scene: str,
    location: str,
    initial_spotlight: str,
    active_chars: list[dict],
    previous_world_state: dict,
) -> str:
    pressure_event = (previous_world_state.get("pressure_event", "") or "").strip()
    last_world_event = (previous_world_state.get("last_world_event", "") or "").strip()
    continuity_note = (previous_world_state.get("continuity_last_updated", "") or "").strip()

    context_line = pressure_event or last_world_event or continuity_note
    if not context_line:
        context_line = "Новый акт начинается с события, которое уже нельзя игнорировать."

    if initial_spotlight == "ALL":
        names = [char.get("name", char.get("id", "герой")) for char in active_chars[:3]]
        if names:
            joined = ", ".join(names)
            heroes_line = f"{joined} одновременно замечают один и тот же тревожный знак."
        else:
            heroes_line = "В кадре чувствуется чужое движение, и сцена начинает дышать быстрее."
        return (
            "🎬 *Сцена стартует*\n\n"
            f"{context_line}\n\n"
            f"В {location} ({scene}) {heroes_line}"
        )

    focus_char = next((char for char in active_chars if char.get("id") == initial_spotlight), None)
    focus_name = focus_char.get("name", initial_spotlight) if focus_char else initial_spotlight
    return (
        "🎬 *Сцена стартует*\n\n"
        f"{context_line}\n\n"
        f"Первый удар сцены приходится на {focus_name}: в {location} ({scene}) происходит событие, после которого назад дороги уже нет."
    )


def _build_first_turn_hooks(active_chars: list[dict], scene: str, location: str) -> str:
    if not active_chars:
        return ""

    default_risk = "если промедлишь — инициативу перехватит чужая сторона"
    default_reward = "если рискнёшь — заберёшь рычаг влияния в этой сцене"

    hooks_by_id = {
        "Elix": (
            "печать может выдать твою природу не тем людям",
            "получишь доступ к ключу о драконьей метке раньше остальных",
        ),
        "Silas": (
            "старые клятвы ордена столкнут тебя с выгодой группы",
            "сможешь навязать правила боя и удержать порядок",
        ),
        "Varo": (
            "если цель сорвётся — в городе вспомнят твои прошлые долги",
            "перехватишь улику или должника до того, как их зачистят",
        ),
        "Lysandra": (
            "ошибка в расчёте раскроет твои методы и лишит тебя преимущества",
            "вытащишь скрытую закономерность и купишь группе время",
        ),
    }

    lines = ["🎯 *Первый ход — личные крючки*:"]
    for char in active_chars[:6]:
        char_id = str(char.get("id", "")).strip()
        char_name = char.get("name", char_id or "Герой")
        char_items = char.get("items") or []
        risk, reward = hooks_by_id.get(char_id, (default_risk, default_reward))

        if char_items:
            item_hint = str(char_items[0]).strip()
            reward = f"через «{item_hint}» {reward}"

        lines.append(f"- **{char_name}**: риск — {risk}; шанс — {reward}.")

    lines.append(f"Сделайте первый ход прямо сейчас: что вы предпринимаете в {location}, в сцене «{scene}»?")
    return "\n".join(lines)


def _resolve_character_id(target: str, all_chars: list[dict]) -> str | None:
    normalized = target.strip().lower()
    for char in all_chars:
        if normalized == char["id"].lower() or normalized == char["name"].lower():
            return char["id"]
    for char in all_chars:
        if normalized in char["id"].lower() or normalized in char["name"].lower():
            return char["id"]
    return None


async def _apply_stat_tags(text: str):
    stat_pattern = re.compile(r"\[ИЗМЕНИТЬ:\s*(\w+),\s*(\w+),\s*([+-]?\d+)\]", re.IGNORECASE)
    for stat_match in stat_pattern.finditer(text):
        target_char_id, stat, value = stat_match.groups()
        char_data = await database.get_character(target_char_id)
        if not char_data or stat not in {"hp", "stress"}:
            continue

        prev_value = int(char_data[stat])
        next_value = max(0, char_data[stat] + int(value))
        if stat == "hp":
            next_value = min(char_data.get("max_hp", next_value), next_value)
        await database.update_stat(target_char_id, stat, next_value)
        if next_value != prev_value:
            await database.add_game_event(
                "stat_change",
                f"{target_char_id}: {stat} {prev_value} -> {next_value}",
            )

    return stat_pattern.sub("", text)


async def _apply_world_tags(text: str):
    world_pattern = re.compile(r"\[МИР:\s*(pressure_clock|threat_level|dark_points),\s*([+-]?\d+)\]", re.IGNORECASE)
    caps = {
        "pressure_clock": (0, 12),
        "threat_level": (0, 100),
        "dark_points": (0, 999),
    }

    for world_match in world_pattern.finditer(text):
        key, value = world_match.groups()
        key = key.lower()
        current_raw = await database.get_world_state(key, "0")
        try:
            current_value = int(current_raw)
        except ValueError:
            current_value = 0

        minimum, maximum = caps[key]
        next_value = max(minimum, min(maximum, current_value + int(value)))
        await database.set_world_state(key, str(next_value))

    return world_pattern.sub("", text)


async def _apply_knowledge_tags(text: str, all_chars: list[dict]):
    knowledge_pattern = re.compile(r"\[ЗНАНИЕ:\s*(.*?)\]", re.IGNORECASE | re.DOTALL)

    for match in knowledge_pattern.finditer(text):
        payload = match.group(1).strip()
        parts = [part.strip() for part in payload.split("|", 3)]
        if len(parts) < 3:
            continue

        target_raw, title, content = parts[:3]
        whisper_text = parts[3].strip() if len(parts) == 4 else ""
        target_char_id = _resolve_character_id(target_raw, all_chars)
        if not target_char_id or not title or not content:
            continue

        was_added = await database.add_knowledge(target_char_id, title, content)
        if not was_added:
            continue

        await database.add_game_event("knowledge", f"{target_char_id} узнал: {title}")
        if whisper_text:
            await database.save_whisper(target_char_id, whisper_text)
            target_char = next((char for char in all_chars if char["id"] == target_char_id), None)
            if target_char and target_char.get("tg_id"):
                await bot.send_message(
                    target_char["tg_id"],
                    f"👁 **Шепот Судьбы:**\n_{whisper_text}_",
                    parse_mode="Markdown",
                )

    return knowledge_pattern.sub("", text)


async def _apply_roll_tags(text: str, chat_id: int, all_chars: list[dict]):
    roll_pattern = re.compile(r"\[БРОСОК:\s*(.*?)\]", re.IGNORECASE | re.DOTALL)

    for match in roll_pattern.finditer(text):
        payload = match.group(1).strip()
        parts = [part.strip() for part in payload.split("|", 1)]
        if not parts or not parts[0]:
            continue

        target_char_id = _resolve_character_id(parts[0], all_chars)
        reason = parts[1].strip() if len(parts) > 1 else "Судьба требует ответа прямо сейчас."
        if not target_char_id:
            continue

        await database.set_world_state("pending_roll_char", target_char_id)
        await database.set_world_state("pending_roll_reason", reason)
        await database.set_world_state("pending_roll_chat_id", str(chat_id))
        await database.add_game_event("pending_roll", f"Ожидается бросок {target_char_id}: {reason}")

        target_char = next((char for char in all_chars if char["id"] == target_char_id), None)
        target_name = target_char["name"] if target_char else target_char_id
        announcement = (
            "🎲 *Зов Судьбы*\n\n"
            f"_Теперь кость должен бросить_ *{target_name}*.\n"
            f"Причина: _{reason}_\n\n"
            "Можно бросить кости в чате или в приложении. Пока результат не явлен, сцена ждёт."
        )
        await safe_send(chat_id, announcement)
        if target_char and target_char.get("tg_id") and int(target_char["tg_id"]) != int(chat_id):
            await bot.send_message(target_char["tg_id"], announcement, parse_mode="Markdown")

    return roll_pattern.sub("", text)


async def _apply_item_tags(text: str, all_chars: list[dict]):
    item_pattern = re.compile(r"\[ПРЕДМЕТ:\s*(.*?)\]", re.IGNORECASE | re.DOTALL)

    for match in item_pattern.finditer(text):
        payload = match.group(1).strip()
        parts = [part.strip() for part in payload.split("|", 2)]
        if len(parts) < 3:
            continue

        target_raw, action_raw, item_name = parts
        target_char_id = _resolve_character_id(target_raw, all_chars)
        if not target_char_id or not item_name:
            continue

        action = action_raw.lower()
        if action in {"+", "add", "give", "получить", "добавить"}:
            added = await database.add_item(target_char_id, item_name)
            if added:
                await database.add_game_event("item_add", f"{target_char_id} получил предмет: {item_name}")
        elif action in {"-", "remove", "take", "убрать", "забрать"}:
            await database.remove_item(target_char_id, item_name)
            await database.add_game_event("item_remove", f"{target_char_id} потерял предмет: {item_name}")

    return item_pattern.sub("", text)


async def _apply_name_tags(text: str, all_chars: list[dict]):
    name_pattern = re.compile(r"\[ИМЯ:\s*(.*?)\]", re.IGNORECASE | re.DOTALL)

    for match in name_pattern.finditer(text):
        payload = match.group(1).strip()
        parts = [part.strip() for part in payload.split("|", 2)]
        if len(parts) < 2:
            continue

        target_raw, new_name = parts[:2]
        reason = parts[2].strip() if len(parts) > 2 else ""
        target_char_id = _resolve_character_id(target_raw, all_chars)
        if not target_char_id:
            continue

        clean_name = re.sub(r"\s+", " ", re.sub(r"[\[\]]", "", new_name)).strip()
        if len(clean_name) < 2:
            continue
        if len(clean_name) > 48:
            clean_name = clean_name[:48].rstrip()

        target_char = next((char for char in all_chars if char["id"] == target_char_id), None)
        old_name = target_char.get("name", target_char_id) if target_char else target_char_id
        if clean_name == old_name:
            continue

        await database.update_name(target_char_id, clean_name)
        await database.add_game_event("rename", f"{target_char_id}: {old_name} → {clean_name}. {reason}".strip())

        if target_char and target_char.get("tg_id"):
            rename_msg = (
                "🜂 *Истинное имя раскрыто*\n\n"
                f"Теперь судьба зовёт тебя так: *{clean_name}*."
            )
            if reason:
                rename_msg += f"\n_{reason}_"
            await bot.send_message(target_char["tg_id"], rename_msg, parse_mode="Markdown")

    return name_pattern.sub("", text)


async def register_story_dice_roll(char_id: str | None, char_name: str, result: int) -> bool:
    if not char_id or char_id == "Unknown":
        return {"story_roll": False, "continued": False}

    world_state = await database.get_all_world_states()
    if world_state.get("bot_mode") != "quest" or world_state.get("quest_started", "0") != "1" or world_state.get("quest_paused", "0") == "1":
        return {"story_roll": False, "continued": False}

    current_scene = world_state.get("current_scene", "")
    current_location = world_state.get("current_location", "")
    spotlight = world_state.get("active_spotlight", "ALL")
    pending_roll_char = world_state.get("pending_roll_char", "")
    pending_roll_reason = world_state.get("pending_roll_reason", "")
    story_tag = "в фокусе сцены" if spotlight in {"ALL", char_id} else "вне фокуса сцены"
    event_text = f"Бросок судьбы {char_name} ({char_id}): {result}. Локация: {current_location}. Сцена: {current_scene}. Статус: {story_tag}."

    await database.add_game_event("dice_roll", event_text)
    await database.update_char_memory(char_id, last_action=f"Бросок судьбы: {result}")
    await database.set_world_state("last_dice_roll", f"{char_id}:{result}")

    roll_info = {
        "story_roll": True,
        "continued": False,
        "pending_resolved": False,
        "chat_id": 0,
        "char_id": char_id,
        "char_name": char_name,
        "result": result,
        "reason": pending_roll_reason,
    }

    if pending_roll_char == char_id:
        pending_chat_raw = world_state.get("pending_roll_chat_id", "")
        try:
            pending_chat_id = int(pending_chat_raw) if pending_chat_raw else 0
        except ValueError:
            pending_chat_id = 0

        if result == 20:
            outcome = "🔥 *Критический успех*"
        elif result == 1:
            outcome = "💀 *Роковой провал*"
        elif result >= 15:
            outcome = "✅ *Уверенный успех*"
        elif result >= 10:
            outcome = "⚖️ *Смешанный исход*"
        else:
            outcome = "⚠️ *Провал с ценой*"

        resolution_text = (
            "🎲 *Судьба ответила*\n\n"
            f"*{char_name}* бросает кость: *{result}*.\n"
            f"{outcome}\n"
            f"Причина броска: _{pending_roll_reason or 'Не указана'}_"
        )
        await database.add_game_event("pending_roll_resolved", f"{char_id} закрыл обязательный бросок: {result}")
        await database.set_world_state("pending_roll_char", "")
        await database.set_world_state("pending_roll_reason", "")
        await database.set_world_state("pending_roll_chat_id", "")
        roll_info["pending_resolved"] = True
        roll_info["chat_id"] = pending_chat_id
        if pending_chat_id:
            await safe_send(pending_chat_id, resolution_text)

    return roll_info


def _build_pause_summary(world_state: dict) -> str:
    parts = []
    if world_state.get("current_act"):
        parts.append(f"Акт {world_state.get('current_act')}")
    if world_state.get("current_scene"):
        parts.append(f"сцена «{world_state.get('current_scene')}»")
    if world_state.get("current_location"):
        parts.append(f"локация: {world_state.get('current_location')}")

    summary = ", ".join(parts) if parts else "Текущая сцена без явной подписи"
    goal = world_state.get("scene_goal", "").strip()
    question = world_state.get("dramatic_question", "").strip()
    last_event = world_state.get("last_world_event", "").strip()
    campaign_summary = world_state.get("campaign_summary", "").strip()

    lines = [summary]
    if goal:
        lines.append(f"Цель: {goal}")
    if question:
        lines.append(f"Вопрос сцены: {question}")
    if last_event:
        lines.append(f"Последний сдвиг мира: {last_event}")
    if campaign_summary:
        lines.append(f"Память кампании: {campaign_summary}")
    return "\n".join(lines)


async def remember_active_group(chat_id: int | None, title: str | None = None):
    if not chat_id or chat_id > 0:
        return
    await database.set_world_state("active_group_chat_id", str(chat_id))
    if title:
        await database.upsert_group(chat_id, title)


async def _send_quest_state_message(message_text: str, preferred_chat_id: int | None = None):
    sent = False
    if preferred_chat_id:
        try:
            await safe_send(preferred_chat_id, message_text)
            sent = True
        except Exception as error:
            logger.warning(f"Не удалось отправить состояние квеста в основной чат: {error}")

    if sent:
        return

    all_chars = await database.get_all_characters()
    for char in all_chars:
        tg_id = char.get("tg_id")
        if not tg_id:
            continue
        try:
            await bot.send_message(tg_id, message_text, parse_mode="Markdown")
        except Exception as error:
            logger.warning(f"Не удалось отправить сообщение состояния {char.get('id')}: {error}")


async def pause_quest(reason: str = "", chat_id: int | None = None, chat_title: str | None = None, announce: bool = True) -> dict:
    world_state = await database.get_all_world_states()
    if world_state.get("quest_started", "0") != "1":
        return {"ok": False, "message": "Квест ещё не начат."}
    if world_state.get("quest_paused", "0") == "1":
        return {"ok": False, "message": "Квест уже стоит на паузе."}

    await remember_active_group(chat_id, chat_title)
    world_state = await database.get_all_world_states()
    pause_summary = _build_pause_summary(world_state)
    pause_reason = reason.strip() or "Игроки решили остановиться на этом месте."
    paused_at = datetime.now(timezone.utc).isoformat()

    await database.set_world_state("quest_paused", "1")
    await database.set_world_state("quest_pause_reason", pause_reason)
    await database.set_world_state("quest_pause_summary", pause_summary)
    await database.set_world_state("quest_paused_at", paused_at)
    await database.add_game_event("quest_pause", f"Квест поставлен на паузу. Причина: {pause_reason}")

    announcement = (
        "⏸ *Квест поставлен на паузу*\n\n"
        f"Причина: _{pause_reason}_\n\n"
        "Якен запомнил, где оборвалась нить. Продолжить можно позже командой `/quest resume` или из админки."
    )
    target_chat_id = chat_id
    if target_chat_id is None:
        active_chat = await database.get_world_state("active_group_chat_id", "")
        try:
            target_chat_id = int(active_chat) if active_chat else None
        except ValueError:
            target_chat_id = None
    if announce:
        await _send_quest_state_message(announcement, preferred_chat_id=target_chat_id)
    return {"ok": True, "message": announcement, "summary": pause_summary}


async def resume_quest(chat_id: int | None = None, chat_title: str | None = None, announce: bool = True) -> dict:
    world_state = await database.get_all_world_states()
    if world_state.get("quest_started", "0") != "1":
        return {"ok": False, "message": "Квест ещё не начат."}
    if world_state.get("quest_paused", "0") != "1":
        return {"ok": False, "message": "Квест и так уже активен."}

    await remember_active_group(chat_id, chat_title)
    pause_reason = world_state.get("quest_pause_reason", "").strip()
    pause_summary = world_state.get("quest_pause_summary", "").strip() or _build_pause_summary(world_state)

    await database.set_world_state("quest_paused", "0")
    await database.set_world_state("quest_pause_reason", "")
    await database.set_world_state("quest_paused_at", "")
    await database.add_game_event("quest_resume", "Квест снят с паузы и продолжен.")

    recap = (
        "▶️ *Квест продолжается*\n\n"
        f"_{pause_reason or 'Нить судьбы снова натянулась.'}_\n\n"
        f"*Где остановились:*\n{pause_summary}\n\n"
        "Якен помнит место разрыва. Можно продолжать сцену с текущего кадра."
    )
    target_chat_id = chat_id
    if target_chat_id is None:
        active_chat = await database.get_world_state("active_group_chat_id", "")
        try:
            target_chat_id = int(active_chat) if active_chat else None
        except ValueError:
            target_chat_id = None
    if announce:
        await _send_quest_state_message(recap, preferred_chat_id=target_chat_id)
    return {"ok": True, "message": recap, "summary": pause_summary}


async def continue_after_story_roll(roll_info: dict):
    if not roll_info.get("story_roll") or not roll_info.get("pending_resolved"):
        return False

    chat_id = roll_info.get("chat_id")
    if not chat_id:
        active_chat = await database.get_world_state("active_group_chat_id", "")
        try:
            chat_id = int(active_chat) if active_chat else 0
        except ValueError:
            chat_id = 0
    if not chat_id:
        return False

    char_id = roll_info.get("char_id")
    char_info = await database.get_character(char_id)
    if not char_info:
        return False

    char_memory = await database.get_char_memory(char_id)
    whispers = await database.get_whispers(char_id)
    world_state = await database.get_all_world_states()
    if world_state.get("quest_paused", "0") == "1":
        return False

    reason = roll_info.get("reason") or "Судьба потребовала немедленного исхода."
    result = int(roll_info.get("result") or 0)
    if result == 20:
        outcome = "критический успех"
    elif result == 1:
        outcome = "роковой провал"
    elif result >= 15:
        outcome = "уверенный успех"
    elif result >= 10:
        outcome = "смешанный исход"
    else:
        outcome = "провал с ценой"

    message_text = (
        f"Служебное событие сцены: обязательный бросок судьбы уже совершен. "
        f"Герой {char_info['name']} ({char_id}) бросил {result} по причине '{reason}'. "
        f"Исход броска: {outcome}. Продолжи сцену немедленно, покажи прямое последствие результата и новый кадр после него."
    )
    vault_info = await get_context(reason, char_id=char_id, world_state=world_state)
    session_history = await database.get_recent_events(8)
    director_notes = await analyze_scene_turn(
        char_id=char_id,
        message_text=message_text,
        world_state=world_state,
        session_history=session_history,
        char_info=char_info,
        personal_ctx=char_memory.get("personal_context", ""),
        char_last_action=char_memory.get("last_action", ""),
        vault_info=vault_info,
        model=world_state.get("gemini_model", "gemini-2.5-flash"),
    )
    await persist_director_notes(director_notes)
    world_state = await database.get_all_world_states()
    continuity_notes = get_continuity_guard(world_state, char_info)
    prompt = build_game_master_prompt(
        char_id=char_id,
        message_text=message_text,
        world_state=world_state,
        session_history=session_history,
        char_info=char_info,
        personal_ctx=char_memory.get("personal_context", ""),
        char_last_action=char_memory.get("last_action", ""),
        whispers=whispers,
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
    answer = await generate_text(prompt, system_prompt=GAME_MASTER_SYSTEM_PROMPT, temperature=0.55)
    answer, guard_issues = apply_continuity_guardrails(
        text=answer,
        world_state=world_state,
        continuity_notes=continuity_notes,
    )
    if guard_issues:
        await database.add_game_event("guardrail", f"{char_id}: {', '.join(guard_issues)}")

    fallback_tags: list[str] = []
    if result == 20:
        fallback_tags.append("[МИР: pressure_clock, -1]")
    elif result == 1:
        fallback_tags.extend([f"[ИЗМЕНИТЬ: {char_id}, stress, +2]", "[МИР: pressure_clock, +2]"])
    elif result >= 15:
        fallback_tags.append("[МИР: pressure_clock, -1]")
    elif result >= 10:
        fallback_tags.append(f"[ИЗМЕНИТЬ: {char_id}, stress, +1]")
    else:
        fallback_tags.extend([f"[ИЗМЕНИТЬ: {char_id}, stress, +1]", "[МИР: pressure_clock, +1]"])

    clean_answer, ai_camera = await deliver_game_response(
        text=answer,
        chat_id=chat_id,
        char_id=char_id,
        fallback_tags=fallback_tags,
    )
    await advance_world_turn(
        char_id=char_id,
        player_message=message_text,
        gm_response=clean_answer,
        chat_id=chat_id,
    )
    world_state = await database.get_all_world_states()
    await refresh_campaign_continuity(
        char_id=char_id,
        player_message=message_text,
        gm_response=clean_answer,
        world_state=world_state,
        session_history=await database.get_recent_events(12),
        model=world_state.get("gemini_model", "gemini-2.5-flash"),
    )
    await maybe_auto_advance_act(chat_id)
    await database.add_game_event("roll_followup", f"{char_id}: {clean_answer[:120]}")
    await database.add_game_event("director", f"{char_id}: {director_notes.get('beat', '')} | {director_notes.get('scene_phase', '')}")
    if char_id != "Unknown":
        await database.update_char_memory(
            char_id,
            last_action=f"Обязательный бросок {result} -> {clean_answer[:100]}",
            last_location=world_state.get("current_location", ""),
        )
        await maybe_rotate_spotlight(char_id, await database.get_all_characters(), chat_id, ai_camera)
    roll_info["continued"] = True
    return True


def _merge_fallback_tags(text: str, fallback_tags: list[str] | None = None) -> str:
    if not fallback_tags:
        return text

    missing_tags = [tag for tag in fallback_tags if tag and tag not in text]
    if not missing_tags:
        return text

    return f"{text.rstrip()}\n" + "\n".join(missing_tags)


def _compact_game_text(text: str, max_chars: int = 900, max_sentences: int = 6) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return clean

    sentences = re.split(r"(?<=[.!?…])\s+", clean)
    limited = " ".join(sentences[:max_sentences]).strip()
    if len(limited) > max_chars:
        limited = limited[:max_chars].rstrip()
        last_dot = max(limited.rfind("."), limited.rfind("!"), limited.rfind("?"), limited.rfind("…"))
        if last_dot > 120:
            limited = limited[: last_dot + 1]
    return limited


async def prepare_game_response(text: str, chat_id: int, fallback_tags: list[str] | None = None):
    all_chars = await database.get_all_characters()
    world_state = await database.get_all_world_states()

    text = _merge_fallback_tags(text, fallback_tags)
    text = await _apply_stat_tags(text)
    text = await _apply_world_tags(text)
    text = await _apply_item_tags(text, all_chars)
    text = await _apply_name_tags(text, all_chars)
    text = await _apply_knowledge_tags(text, all_chars)
    text = await _apply_roll_tags(text, chat_id, all_chars)
    text, ai_camera = await apply_ai_camera(
        text,
        chat_id,
        all_chars,
        world_state.get("active_spotlight", "ALL"),
    )
    text, buttons_markup = parse_buttons(text)
    clean_text = re.sub(r"\[.*?\]", "", text).strip()
    clean_text = _compact_game_text(clean_text)
    return clean_text, buttons_markup, ai_camera


async def apply_ai_camera(text: str, chat_id: int, all_chars: list, current_spotlight: str):
    camera_match = re.search(r"\[КАМЕРА:\s*(\w+)\]", text, re.IGNORECASE)
    ai_forced_camera = None
    if camera_match:
        value = camera_match.group(1).upper()
        if value == "ALL":
            ai_forced_camera = "ALL"
        else:
            found = next(
                (
                    char
                    for char in all_chars
                    if value.lower() in char["id"].lower() or value.lower() in char["name"].lower()
                ),
                None,
            )
            if found:
                ai_forced_camera = found["id"]

        text = text.replace(camera_match.group(0), "")

        if ai_forced_camera and ai_forced_camera != current_spotlight:
            await database.set_world_state("active_spotlight", ai_forced_camera)
            if ai_forced_camera != "ALL":
                await database.reset_spotlight_turns(ai_forced_camera)

            if ai_forced_camera == "ALL":
                await safe_send(chat_id, "🎬 *Камера отъезжает назад...*\n\n_Теперь нити судеб героев сплетаются воедино._")
            else:
                next_char = next((char for char in all_chars if char["id"] == ai_forced_camera), None)
                next_name = next_char["name"] if next_char else ai_forced_camera
                await safe_send(
                    chat_id,
                    (
                        "🎬 *Сцена меняется по воле судьбы...*\n\n"
                        f"_Нить переходит к_ *{next_name}*.\n"
                        f"_{next_name}, Якен ждёт твоего слова._"
                    ),
                )
    return text.strip(), ai_forced_camera


async def check_triggers(act: str):
    if act == "2":
        await database.add_knowledge(
            "Varo",
            "Метка Безликих",
            "Твоя цена за свободу - смерть Эликса Веллара. Исполни, или умрут все, кого ты знал.",
        )
        await database.add_knowledge(
            "Silas",
            "Шепот Прошлого",
            "Тебе снятся убитые тобой люди. Завеса рушится, ты начинаешь вспоминать резню.",
        )

        chars = await database.get_all_characters()
        for char in chars:
            if char["id"] == "Varo" and char["tg_id"]:
                await database.save_whisper("Varo", "Слепая птица принесла известие. Контракт вступил в силу...")
                await bot.send_message(
                    char["tg_id"],
                    "👁 **Шепот Судьбы:**\n_Слепая птица принесла известие. Контракт вступил в силу..._",
                    parse_mode="Markdown",
                )
            elif char["id"] == "Silas" and char["tg_id"]:
                await database.save_whisper("Silas", "Кровь на твоих руках почему-то не смывается. Твои братья-инквизиторы всё еще горят в твоих снах.")
                await bot.send_message(
                    char["tg_id"],
                    "👁 **Шепот Судьбы:**\n_Кровь на твоих руках почему-то не смывается. Твои братья-инквизиторы всё еще горят в твоих снах._",
                    parse_mode="Markdown",
                )

    elif act == "3":
        await database.add_knowledge(
            "Lysandra",
            "Секрет Кулона",
            "Это не магия. Это механизм сдерживания. И он на пределе. У тебя есть знания, чтобы его отключить.",
        )
        chars = await database.get_all_characters()
        for char in chars:
            if char["id"] == "Lysandra" and char["tg_id"]:
                await database.save_whisper("Lysandra", "Приборы зашкаливают. Кулон Эликса вот-вот расплавится. Если он взорвется, обратного пути для него не будет.")
                await bot.send_message(
                    char["tg_id"],
                    "👁 **Шепот Судьбы:**\n_Приборы зашкаливают. Кулон Эликса вот-вот расплавится. Если он взорвется, обратного пути для него не будет._",
                    parse_mode="Markdown",
                )


async def broadcast_scene_message(message_text: str, image_path: str | None = None):
    async def send_scene_payload(target_chat_id: int):
        if image_path:
            if len(message_text) > 1000:
                await bot.send_photo(target_chat_id, photo=types.FSInputFile(image_path))
                await safe_send(target_chat_id, message_text)
                return
            try:
                await bot.send_photo(
                    target_chat_id,
                    photo=types.FSInputFile(image_path),
                    caption=message_text,
                    parse_mode="Markdown",
                )
            except Exception:
                try:
                    await bot.send_photo(target_chat_id, photo=types.FSInputFile(image_path), caption=message_text)
                except Exception:
                    await bot.send_photo(target_chat_id, photo=types.FSInputFile(image_path))
                    await safe_send(target_chat_id, message_text)
            return

        await safe_send(target_chat_id, message_text)

    active_group_raw = await database.get_world_state("active_group_chat_id", "")
    try:
        active_group_chat_id = int(active_group_raw) if active_group_raw else 0
    except ValueError:
        active_group_chat_id = 0

    if active_group_chat_id:
        try:
            await send_scene_payload(active_group_chat_id)
        except Exception as error:
            logger.error(f"Failed to send scene to active group {active_group_chat_id}: {error}")

    all_chars = await database.get_all_characters()
    for char in all_chars:
        if not char.get("tg_id"):
            continue
        try:
            await send_scene_payload(char["tg_id"])
        except Exception as error:
            logger.error(f"Failed to send to {char.get('name')}: {error}")


async def maybe_rotate_spotlight(char_id: str, all_chars: list, chat_id: int, ai_camera):
    world_state = await database.get_all_world_states()
    spotlight = world_state.get("active_spotlight", "ALL")
    if ai_camera or spotlight == "ALL" or char_id == "Unknown":
        return

    turns = await database.increment_spotlight_turns(char_id)
    max_turns = int(world_state.get("spotlight_max_turns", "3"))
    max_turns = max(1, min(max_turns, 6))
    if turns < max_turns:
        return

    await database.reset_spotlight_turns(char_id)
    active_chars = [char["id"] for char in all_chars if char["tg_id"] and char["tg_id"] != 0]
    if len(active_chars) <= 1:
        return

    await database.set_world_state("active_spotlight", "ALL")
    await safe_send(
        chat_id,
        (
            "🎬 *Камера отходит в общий план...*\n\n"
            "_Нити героев снова видны одновременно. Любой игрок может делать ход._"
        ),
    )


async def launch_act(act: str, scene: str, location: str):
    previous_world_state = await database.get_all_world_states()
    await run_summarizer_if_needed(
        trigger="act-transition",
        world_state=previous_world_state,
        force=True,
    )

    await database.set_world_state("bot_mode", "quest")
    await database.set_world_state("quest_started", "1")
    await database.set_world_state("quest_paused", "0")
    await database.set_world_state("quest_pause_reason", "")
    await database.set_world_state("quest_pause_summary", "")
    await database.set_world_state("quest_paused_at", "")
    await database.set_world_state("current_act", act)
    await database.set_world_state("current_scene", scene)
    await database.set_world_state("current_location", location)
    await database.set_world_state("act_started_at", datetime.now(timezone.utc).isoformat())
    await database.set_world_state("scene_goal", f"Понять, что поставлено на кону в сцене '{scene}'.")
    await database.set_world_state("scene_phase", "setup")
    await database.set_world_state("dramatic_question", "Кто первым изменит ход судьбы в этой сцене?")
    await database.set_world_state("pressure_clock", "0")
    await database.set_world_state("pressure_event", "Пока буря только собирается.")
    await database.set_world_state("director_last_beat", "Открытие сцены")
    await database.set_world_state("director_tension", "low")
    await database.set_world_state("director_focus", "roleplay")
    await initialize_world_dynamics()

    all_chars = await database.get_all_characters()
    active_chars = [char for char in all_chars if char.get("tg_id")]
    initial_spotlight = await _pick_initial_spotlight(active_chars)
    await database.set_world_state("active_spotlight", initial_spotlight)
    if initial_spotlight != "ALL":
        await database.reset_spotlight_turns(initial_spotlight)

    world_intro = ACT_OPENINGS.get(str(act), "Мир двигается дальше и требует новых решений.")
    scene_opener = ACT_SCENE_OPENERS.get(str(act), "Сцена медленно собирается вокруг героев.")
    if initial_spotlight == "ALL":
        focus_intro = "Нити всех героев сходятся в одном кадре, и каждый шаг одного может изменить судьбу остальных."
    else:
        focus_char = next((char for char in active_chars if char.get("id") == initial_spotlight), None)
        focus_name = focus_char.get("name", initial_spotlight) if focus_char else initial_spotlight
        focus_intro = f"Взгляд сцены первым цепляется за {focus_name}, но тени остальных уже рядом."

    act_prologue = ACT_PROLOGUES.get(str(act), world_intro)
    carryover_block = _build_carryover_block(previous_world_state)

    kickoff_text = _build_auto_scene_kickoff(
        str(act),
        scene,
        location,
        initial_spotlight,
        active_chars,
        previous_world_state,
    )
    hooks_text = _build_first_turn_hooks(active_chars, scene, location)

    message_text = f"📜 **Акт {act}**"
    if scene:
        message_text += f"\n🎭 Сцена: {scene}"
    if location:
        message_text += f"\n🗺 Локация: {location}"
    message_text += f"\n\n{act_prologue}\n\n"
    if carryover_block:
        message_text += f"Эхо прошлого акта: {carryover_block}\n\n"
    message_text += f"{scene_opener}\n\n{focus_intro}\n\n{kickoff_text}"
    if hooks_text:
        message_text += f"\n\n{hooks_text}"

    await database.add_game_event("act_change", f"Переход: Акт {act}. Сцена: {scene}")
    image_path = None
    try:
        image_path = await generate_location_image(message_text)
    except Exception as error:
        logger.error(f"Scene image generation failed: {error}")

    await broadcast_scene_message(message_text, image_path=image_path)

    if active_chars:
        await database.add_game_event("scene_kickoff", f"Автостарт сцены акта {act}: spotlight={initial_spotlight}")

    asyncio.create_task(check_triggers(act))
    return message_text, image_path


def _safe_int(value: str, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return fallback


def _hours_since_iso(timestamp: str) -> float:
    if not timestamp:
        return 0.0
    try:
        started_at = datetime.fromisoformat(timestamp)
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - started_at).total_seconds() / 3600.0)
    except Exception:
        return 0.0


async def maybe_auto_advance_act(chat_id: int | None = None) -> bool:
    world_state = await database.get_all_world_states()

    if world_state.get("bot_mode") != "quest" or world_state.get("quest_started", "0") != "1":
        return False
    if world_state.get("quest_paused", "0") == "1" or world_state.get("pending_roll_char", ""):
        return False
    if world_state.get("act_auto_progress", "1") != "1":
        return False
    if world_state.get("director_should_end_scene", "0") != "1":
        return False

    current_act = _safe_int(world_state.get("current_act", "1"), 1)
    target_act = _safe_int(world_state.get("campaign_target_act", "5"), 5)
    target_act = max(1, min(target_act, 6))
    if current_act >= target_act:
        return False

    min_turns = max(8, _safe_int(world_state.get("act_min_world_turns", "26"), 26))
    min_hours = max(1, _safe_int(world_state.get("act_min_hours", "8"), 8))
    turns_in_act = _safe_int(world_state.get("world_turn_counter", "0"), 0)
    hours_in_act = _hours_since_iso(world_state.get("act_started_at", ""))
    if turns_in_act < min_turns or hours_in_act < float(min_hours):
        return False

    next_act = str(current_act + 1)
    next_blueprint = ACT_BLUEPRINTS.get(next_act, {})
    next_scene = next_blueprint.get("scene") or f"Новая сцена акта {next_act}"
    next_location = next_blueprint.get("location") or world_state.get("current_location", "Волантис")

    await database.add_game_event(
        "act_auto",
        (
            f"Автопереход к акту {next_act}. Причина: сцена завершена режиссурой; "
            f"ходов в акте={turns_in_act}, часов в акте={hours_in_act:.1f}."
        ),
    )
    await launch_act(next_act, next_scene, next_location)

    summary_text = (
        "🧭 *История сдвигается к новой вехе*\n\n"
        f"Сцена созрела для перехода. Начинается *Акт {next_act}*.\n"
        "Ваши решения сохранены, их последствия продолжают работать в новом акте."
    )
    target_chat_id = chat_id
    if not target_chat_id:
        active_group_raw = world_state.get("active_group_chat_id", "")
        try:
            target_chat_id = int(active_group_raw) if active_group_raw else None
        except ValueError:
            target_chat_id = None

    if target_chat_id:
        await safe_send(target_chat_id, summary_text)
    return True


async def deliver_game_response(*, text: str, chat_id: int, char_id: str, image_path: str | None = None, fallback_tags: list[str] | None = None):
    clean_text, buttons_markup, ai_camera = await prepare_game_response(text, chat_id, fallback_tags=fallback_tags)
    await database.add_game_event("action", f"{char_id}: {clean_text[:100]}")

    if image_path:
        if len(clean_text) > 1000:
            await bot.send_photo(chat_id, photo=types.FSInputFile(image_path))
            await safe_send(chat_id, clean_text, reply_markup=buttons_markup)
        else:
            try:
                await bot.send_photo(
                    chat_id,
                    photo=types.FSInputFile(image_path),
                    caption=clean_text,
                    parse_mode="Markdown",
                    reply_markup=buttons_markup,
                )
            except Exception:
                await bot.send_photo(chat_id, photo=types.FSInputFile(image_path), caption=clean_text, reply_markup=buttons_markup)
    else:
        await safe_send(chat_id, clean_text, reply_markup=buttons_markup)

    return clean_text, ai_camera
