import json
import re
from typing import Any

import database
from bot_core.ai_service import generate_text
from bot_core.prompts import CONTINUITY_SYSTEM_PROMPT, build_continuity_update_prompt
from bot_core.runtime import logger


def _load_json_list(raw_text: str | None) -> list[str]:
    if not raw_text:
        return []
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass
    return []


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


def get_continuity_guard(world_state: dict, char_info: dict | None) -> dict[str, Any]:
    known_titles = [entry.get("title", "") for entry in (char_info or {}).get("knowledge", []) if entry.get("title")]
    summary = world_state.get("campaign_summary", "") or world_state.get("long_term_memory", "") or "Кампания только набирает форму."
    open_loops = _load_json_list(world_state.get("campaign_open_loops"))
    canon_facts = _load_json_list(world_state.get("campaign_canon_facts"))

    return {
        "campaign_summary": summary,
        "open_loops": open_loops[:8],
        "canon_facts": canon_facts[:10],
        "known_titles": known_titles[:10],
        "knowledge_limit": "Персонаж не может знать тайну, которой нет в его личных знаниях, сцене или прямом раскрытии.",
        "guardrail": "Не откатывай последствия, не оживляй исчезнувшие факты без причины и не раскрывай чужие тайны не тому герою.",
    }


async def refresh_campaign_continuity(
    *,
    char_id: str,
    player_message: str,
    gm_response: str,
    world_state: dict,
    session_history: list[str],
    model: str | None = None,
) -> dict[str, Any]:
    prompt = build_continuity_update_prompt(
        char_id=char_id,
        player_message=player_message,
        gm_response=gm_response,
        world_state=world_state,
        session_history=session_history,
    )

    default = {
        "campaign_summary": world_state.get("campaign_summary", "") or world_state.get("long_term_memory", "") or "Кампания только набирает форму.",
        "open_loops": _load_json_list(world_state.get("campaign_open_loops")),
        "canon_facts": _load_json_list(world_state.get("campaign_canon_facts")),
        "continuity_note": "Память кампании удержана в прежнем виде.",
    }

    try:
        raw_response = await generate_text(
            prompt,
            model=model,
            system_prompt=CONTINUITY_SYSTEM_PROMPT,
            temperature=0.2,
        )
        data = _extract_json_block(raw_response) or default
    except Exception as error:
        logger.error(f"Continuity refresh error: {error}")
        data = default

    summary = str(data.get("campaign_summary") or default["campaign_summary"]).strip()
    open_loops = data.get("open_loops") if isinstance(data.get("open_loops"), list) else default["open_loops"]
    canon_facts = data.get("canon_facts") if isinstance(data.get("canon_facts"), list) else default["canon_facts"]
    continuity_note = str(data.get("continuity_note") or "Память кампании обновлена.").strip()

    open_loops = [str(item).strip() for item in open_loops if str(item).strip()][:12]
    canon_facts = [str(item).strip() for item in canon_facts if str(item).strip()][:14]

    await database.set_world_state("campaign_summary", summary)
    await database.set_world_state("campaign_open_loops", json.dumps(open_loops, ensure_ascii=False))
    await database.set_world_state("campaign_canon_facts", json.dumps(canon_facts, ensure_ascii=False))
    await database.set_world_state("continuity_last_updated", continuity_note)
    await database.add_game_event("continuity", continuity_note)

    return {
        "campaign_summary": summary,
        "open_loops": open_loops,
        "canon_facts": canon_facts,
        "continuity_note": continuity_note,
    }
