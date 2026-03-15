import json

import database
from bot_core.ai_service import generate_text
from bot_core.prompts import MEMORY_ARCHIVER_SYSTEM_PROMPT, build_memory_archiver_prompt
from bot_core.runtime import logger


def _safe_int(value: str | None, fallback: int = 0) -> int:
    try:
        return int(str(value or fallback).strip())
    except Exception:
        return fallback


def _extract_butterfly_points(summary_text: str) -> tuple[str, list[str]]:
    if "БАБОЧКА:" not in summary_text:
        return summary_text.strip(), []

    summary, butterfly_block = summary_text.split("БАБОЧКА:", maxsplit=1)
    points = []
    for raw_line in butterfly_block.splitlines():
        line = raw_line.strip().lstrip("-").strip()
        if line:
            points.append(line)
    return summary.strip(), points[:8]


async def run_summarizer_if_needed(
    *,
    trigger: str,
    world_state: dict | None = None,
    force: bool = False,
) -> dict:
    if world_state is None:
        world_state = await database.get_all_world_states()

    current_turn = _safe_int(world_state.get("world_turn_counter", "0"), 0)
    last_turn = _safe_int(world_state.get("summarizer_last_turn", "0"), 0)
    interval = max(4, _safe_int(world_state.get("summarizer_interval_turns", "12"), 12))

    if not force and trigger == "turn" and (current_turn - last_turn) < interval:
        return {"ran": False, "reason": "interval"}

    events = await database.get_recent_events(40)
    if len(events) < 6 and not force:
        return {"ran": False, "reason": "not-enough-events"}

    prompt = build_memory_archiver_prompt(
        old_memory=world_state.get("long_term_memory", "") or world_state.get("campaign_summary", ""),
        events=events,
        butterfly_effect=world_state.get("session_memory_summary", ""),
    )

    try:
        summary_text = await generate_text(
            prompt,
            model=world_state.get("gemini_model", "gemini-2.5-flash"),
            system_prompt=MEMORY_ARCHIVER_SYSTEM_PROMPT,
            temperature=0.25,
        )
        clean_summary, butterfly_points = _extract_butterfly_points(summary_text)

        open_loops_raw = world_state.get("campaign_open_loops", "[]")
        try:
            open_loops = json.loads(open_loops_raw)
            if not isinstance(open_loops, list):
                open_loops = []
        except Exception:
            open_loops = []

        for point in butterfly_points:
            if point not in open_loops:
                open_loops.append(point)

        open_loops = [str(item).strip() for item in open_loops if str(item).strip()][:12]

        await database.set_world_state("long_term_memory", clean_summary)
        await database.set_world_state("session_memory_summary", clean_summary)
        await database.set_world_state("campaign_open_loops", json.dumps(open_loops, ensure_ascii=False))
        await database.set_world_state("summarizer_last_turn", str(current_turn))
        await database.set_world_state("summarizer_last_trigger", trigger)
        await database.add_game_event("summarizer", f"Summarizer trigger={trigger}; turn={current_turn}")

        return {
            "ran": True,
            "summary": clean_summary,
            "open_loops": open_loops,
            "trigger": trigger,
            "turn": current_turn,
        }
    except Exception as error:
        logger.error(f"Summarizer pipeline error ({trigger}): {error}")
        return {"ran": False, "reason": "error", "error": str(error)}