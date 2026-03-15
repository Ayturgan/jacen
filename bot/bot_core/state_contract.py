from bot_core.config import SETTINGS


STATE_DEFAULTS: dict[str, str] = {
    "llm_tier": "free",
    "gemini_model": "",
    "bot_mode": "normal",
    "gm_action_mode": "auto",
    "quest_started": "0",
    "quest_paused": "0",
    "current_act": "1",
    "current_scene": "",
    "current_location": "Волантис",
    "threat_level": "20",
    "dark_points": "0",
    "long_term_memory": "",
    "active_spotlight": "ALL",
    "spotlight_max_turns": "3",
    "scene_goal": "",
    "scene_phase": "setup",
    "dramatic_question": "",
    "pressure_clock": "0",
    "pressure_event": "",
    "reveal_queue": "",
    "npc_agenda": "",
    "scene_exit_conditions": "",
    "director_last_beat": "",
    "director_tension": "low",
    "director_focus": "roleplay",
    "world_turn_counter": "0",
    "faction_states": "{}",
    "npc_states": "{}",
    "world_clocks": "{}",
    "last_world_event": "",
    "campaign_summary": "",
    "campaign_open_loops": "[]",
    "campaign_canon_facts": "[]",
    "continuity_last_updated": "",
    "scene_memory": "[]",
    "session_memory": "[]",
    "session_memory_summary": "",
    "memory_scene_key": "",
    "memory_act_key": "",
    "summarizer_last_turn": "0",
    "summarizer_interval_turns": "12",
    "summarizer_last_trigger": "",
    "observability_enabled": "0",
    "pending_roll_char": "",
    "pending_roll_reason": "",
    "pending_roll_chat_id": "",
    "last_dice_roll": "",
    "director_should_end_scene": "0",
    "act_auto_progress": "1",
    "act_min_world_turns": "26",
    "act_min_hours": "8",
    "campaign_target_act": "5",
    "act_started_at": "",
    "quest_pause_reason": "",
    "quest_pause_summary": "",
    "quest_paused_at": "",
    "active_group_chat_id": "",
}


def _to_bool_str(value: str, default: str = "0") -> str:
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return "1"
    if normalized in {"0", "false", "no", "off"}:
        return "0"
    return default


def _to_int_str(value: str, default: str) -> str:
    try:
        return str(int(str(value).strip()))
    except Exception:
        return default


def _normalize_tier(value: str) -> str:
    tier = str(value or "free").strip().lower()
    return tier if tier in {"free", "paid"} else "free"


def _default_model_for_tier(tier: str) -> str:
    if tier == "paid":
        return SETTINGS.gemini_paid_model or "gemini-3.1-flash-lite-preview"
    return SETTINGS.gemini_free_model or "gemini-2.5-flash-lite"


def normalize_world_state(raw_state: dict[str, str] | None) -> dict[str, str]:
    state = dict(STATE_DEFAULTS)
    if raw_state:
        for key, value in raw_state.items():
            state[key] = str(value)

    state["llm_tier"] = _normalize_tier(state.get("llm_tier", "free"))
    state["bot_mode"] = state.get("bot_mode", "normal") if state.get("bot_mode", "normal") in {"normal", "quest"} else "normal"
    state["gm_action_mode"] = state.get("gm_action_mode", "auto") if state.get("gm_action_mode", "auto") in {"auto", "review"} else "auto"

    state["quest_started"] = _to_bool_str(state.get("quest_started", "0"), "0")
    state["quest_paused"] = _to_bool_str(state.get("quest_paused", "0"), "0")
    state["director_should_end_scene"] = _to_bool_str(state.get("director_should_end_scene", "0"), "0")
    state["act_auto_progress"] = _to_bool_str(state.get("act_auto_progress", "1"), "1")
    state["observability_enabled"] = _to_bool_str(state.get("observability_enabled", "0"), "0")

    state["spotlight_max_turns"] = _to_int_str(state.get("spotlight_max_turns", "3"), "3")
    state["pressure_clock"] = _to_int_str(state.get("pressure_clock", "0"), "0")
    state["dark_points"] = _to_int_str(state.get("dark_points", "0"), "0")
    state["threat_level"] = _to_int_str(state.get("threat_level", "20"), "20")
    state["world_turn_counter"] = _to_int_str(state.get("world_turn_counter", "0"), "0")
    state["act_min_world_turns"] = _to_int_str(state.get("act_min_world_turns", "26"), "26")
    state["act_min_hours"] = _to_int_str(state.get("act_min_hours", "8"), "8")
    state["campaign_target_act"] = _to_int_str(state.get("campaign_target_act", "5"), "5")
    state["summarizer_last_turn"] = _to_int_str(state.get("summarizer_last_turn", "0"), "0")
    state["summarizer_interval_turns"] = _to_int_str(state.get("summarizer_interval_turns", "12"), "12")

    if state.get("scene_phase", "setup") not in {"setup", "exploration", "complication", "conflict", "aftermath", "transition"}:
        state["scene_phase"] = "setup"

    if state.get("director_tension", "low") not in {"low", "medium", "high", "critical"}:
        state["director_tension"] = "low"

    if state.get("director_focus", "roleplay") not in {"roleplay", "discovery", "danger", "choice", "consequence"}:
        state["director_focus"] = "roleplay"

    current_model = str(state.get("gemini_model", "")).strip()
    if not current_model:
        current_model = _default_model_for_tier(state["llm_tier"])
    if state["llm_tier"] == "paid" and not current_model.startswith("gemini"):
        current_model = _default_model_for_tier("paid")
    state["gemini_model"] = current_model

    return state