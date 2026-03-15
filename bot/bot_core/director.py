import json
import re
from typing import Any

import database
from bot_core.ai_service import generate_text
from bot_core.prompts import DIRECTOR_SYSTEM_PROMPT, build_director_prompt
from bot_core.runtime import logger


DIRECTOR_DEFAULTS = {
    "intent": "reflection",
    "scene_phase": "setup",
    "tension": "low",
    "focus": "roleplay",
    "beat": "Открытый ход",
    "scene_goal": "Понять, чего хотят герои и что угрожает им прямо сейчас.",
    "dramatic_question": "Что изменится после следующего выбора?",
    "pressure_clock": 0,
    "pressure_delta": 0,
    "pressure_event": "Пока тьма лишь наблюдает.",
    "reveal": "",
    "npc_agenda": "",
    "consequence_hint": "Мир должен отвечать правдиво и ощутимо.",
    "offer_choices": False,
    "camera_target": "keep",
    "should_end_scene": False,
    "exit_conditions": "Когда цель сцены выполнена или угроза вынуждает сменить фокус.",
    "action_mode": "auto-resolve",
}


def _extract_json_block(raw_text: str) -> dict[str, Any] | None:
    raw_text = raw_text.strip()
    try:
        parsed = json.loads(raw_text)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass

    match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def _coerce_director_notes(data: dict[str, Any] | None, world_state: dict) -> dict[str, Any]:
    notes = dict(DIRECTOR_DEFAULTS)
    if data:
        notes.update({key: value for key, value in data.items() if value is not None})

    try:
        existing_clock = int(world_state.get("pressure_clock", "0"))
    except ValueError:
        existing_clock = 0

    pressure_delta = notes.get("pressure_delta", 0)
    try:
        pressure_delta = int(pressure_delta)
    except Exception:
        pressure_delta = 0

    pressure_clock = notes.get("pressure_clock", existing_clock + pressure_delta)
    try:
        pressure_clock = max(0, int(pressure_clock))
    except Exception:
        pressure_clock = max(0, existing_clock + pressure_delta)

    notes["pressure_delta"] = pressure_delta
    notes["pressure_clock"] = pressure_clock
    notes["offer_choices"] = bool(notes.get("offer_choices", False))
    notes["should_end_scene"] = bool(notes.get("should_end_scene", False))

    camera_target = str(notes.get("camera_target", "keep") or "keep")
    if camera_target not in {"keep", "ALL", "Elix", "Silas", "Varo", "Lysandra"}:
        camera_target = "keep"
    notes["camera_target"] = camera_target

    if notes["scene_phase"] not in {"setup", "exploration", "complication", "conflict", "aftermath", "transition"}:
        notes["scene_phase"] = world_state.get("scene_phase", "setup") or "setup"

    if notes["tension"] not in {"low", "medium", "high", "critical"}:
        notes["tension"] = world_state.get("director_tension", "low") or "low"

    if notes["focus"] not in {"roleplay", "discovery", "danger", "choice", "consequence"}:
        notes["focus"] = world_state.get("director_focus", "roleplay") or "roleplay"

    return notes


async def analyze_scene_turn(
    *,
    char_id: str,
    message_text: str,
    world_state: dict,
    session_history: list[str],
    char_info: dict | None,
    personal_ctx: str,
    char_last_action: str,
    vault_info: str,
    model: str | None = None,
) -> dict[str, Any]:
    prompt = build_director_prompt(
        char_id=char_id,
        message_text=message_text,
        world_state=world_state,
        session_history=session_history,
        char_info=char_info,
        personal_ctx=personal_ctx,
        char_last_action=char_last_action,
        vault_info=vault_info,
    )

    try:
        raw_response = await generate_text(
            prompt,
            model=model,
            system_prompt=DIRECTOR_SYSTEM_PROMPT,
            temperature=0.25,
        )
        parsed = _extract_json_block(raw_response)
        return _coerce_director_notes(parsed, world_state)
    except Exception as error:
        logger.error(f"Director analysis error: {error}")
        return _coerce_director_notes(None, world_state)


async def persist_director_notes(notes: dict[str, Any]):
    await database.set_world_state("scene_goal", str(notes.get("scene_goal", "")))
    await database.set_world_state("scene_phase", str(notes.get("scene_phase", "setup")))
    await database.set_world_state("dramatic_question", str(notes.get("dramatic_question", "")))
    await database.set_world_state("pressure_clock", str(notes.get("pressure_clock", 0)))
    await database.set_world_state("pressure_event", str(notes.get("pressure_event", "")))
    await database.set_world_state("reveal_queue", str(notes.get("reveal", "")))
    await database.set_world_state("npc_agenda", str(notes.get("npc_agenda", "")))
    await database.set_world_state("scene_exit_conditions", str(notes.get("exit_conditions", "")))
    await database.set_world_state("director_last_beat", str(notes.get("beat", "")))
    await database.set_world_state("director_tension", str(notes.get("tension", "low")))
    await database.set_world_state("director_focus", str(notes.get("focus", "roleplay")))
    await database.set_world_state("director_should_end_scene", "1" if notes.get("should_end_scene") else "0")


def format_director_status(notes: dict[str, Any]) -> str:
    return (
        f"Фаза: {notes.get('scene_phase', 'setup')} | "
        f"Напряжение: {notes.get('tension', 'low')} | "
        f"Бит: {notes.get('beat', '')} | "
        f"Давление: {notes.get('pressure_clock', 0)}"
    )
