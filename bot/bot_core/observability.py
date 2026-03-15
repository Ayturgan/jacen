import re

import database


def extract_rag_sources(vault_info: str) -> list[str]:
    if not vault_info:
        return []
    sources: list[str] = []
    for line in vault_info.splitlines():
        match = re.match(r"---\s*(CANON|SCENE|PERSONAL|SEMANTIC):\s*(.*?)\s*\(", line.strip())
        if not match:
            continue
        source_type = match.group(1)
        source_name = match.group(2)
        sources.append(f"{source_type}:{source_name}")
    return sources[:6]


async def log_generation_observability(
    *,
    char_id: str,
    world_state: dict,
    vault_info: str,
    memory_snapshot: dict | None = None,
):
    if world_state.get("observability_enabled", "1") != "1":
        return

    sources = extract_rag_sources(vault_info)
    scene_memory_len = len((memory_snapshot or {}).get("scene_memory", []))
    session_memory_len = len((memory_snapshot or {}).get("session_memory", []))
    open_loops_len = len((memory_snapshot or {}).get("open_loops", []))

    trace_text = (
        f"char={char_id}; tier={world_state.get('llm_tier', 'free')}; "
        f"model={world_state.get('gemini_model', '')}; "
        f"sources={', '.join(sources) if sources else 'none'}; "
        f"scene_mem={scene_memory_len}; session_mem={session_memory_len}; loops={open_loops_len}"
    )
    await database.add_game_event("trace", trace_text)