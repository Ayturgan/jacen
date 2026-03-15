import json

import database


def _safe_json_list(raw_value: str | None) -> list:
    if not raw_value:
        return []
    try:
        parsed = json.loads(raw_value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _clip(text: str, limit: int = 220) -> str:
    normalized = " ".join((text or "").split()).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def build_memory_snapshot(world_state: dict, char_id: str) -> dict[str, str | int | list]:
    scene_memory = _safe_json_list(world_state.get("scene_memory", "[]"))
    session_memory = _safe_json_list(world_state.get("session_memory", "[]"))
    return {
        "char_id": char_id,
        "scene_memory": scene_memory[-8:],
        "session_memory": session_memory[-20:],
        "campaign_summary": world_state.get("campaign_summary", "") or world_state.get("long_term_memory", ""),
        "open_loops": _safe_json_list(world_state.get("campaign_open_loops", "[]"))[:12],
        "canon_facts": _safe_json_list(world_state.get("campaign_canon_facts", "[]"))[:14],
        "memory_scene_key": world_state.get("memory_scene_key", ""),
        "memory_act_key": world_state.get("memory_act_key", ""),
    }


async def update_memory_layers(
    *,
    char_id: str,
    player_message: str,
    gm_response: str,
    world_state: dict,
    turn_counter: int,
):
    current_act = str(world_state.get("current_act", "1"))
    current_scene = str(world_state.get("current_scene", ""))
    scene_key = f"{current_act}:{current_scene}"

    previous_scene_key = world_state.get("memory_scene_key", "")
    previous_act_key = world_state.get("memory_act_key", "")

    scene_memory = _safe_json_list(world_state.get("scene_memory", "[]"))
    session_memory = _safe_json_list(world_state.get("session_memory", "[]"))

    if previous_scene_key and previous_scene_key != scene_key:
        scene_memory = []

    if previous_act_key and previous_act_key != current_act:
        session_memory = []

    event_entry = {
        "turn": turn_counter,
        "char": char_id,
        "player": _clip(player_message, 180),
        "gm": _clip(gm_response, 220),
    }

    scene_memory.append(event_entry)
    session_memory.append(event_entry)

    await database.set_world_state("scene_memory", json.dumps(scene_memory[-12:], ensure_ascii=False))
    await database.set_world_state("session_memory", json.dumps(session_memory[-40:], ensure_ascii=False))
    await database.set_world_state("memory_scene_key", scene_key)
    await database.set_world_state("memory_act_key", current_act)