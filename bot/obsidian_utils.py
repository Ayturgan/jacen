import os
import re
import json
import asyncio

from bot_core.config import PROJECT_ROOT, SETTINGS
from bot_core.lore_registry import (
    LoreEntry,
    get_lore_registry,
    get_mandatory_lore_entries,
    get_personal_lore_entries,
    select_scene_lore_candidates,
)
from bot_core.runtime import get_gemini_client

CACHE_FILE = os.path.join(PROJECT_ROOT, "bot", "embeddings.json")
try:
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        vector_db = json.load(f)
except Exception:
    vector_db = {}

def cosine_similarity(a, b):
    dot = sum(x*y for x, y in zip(a, b))
    norm_a = sum(x*x for x in a) ** 0.5
    norm_b = sum(x*x for x in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

def _normalize_tier(value: str | None) -> str:
    tier = (value or "free").lower()
    return tier if tier in {"free", "paid"} else "free"


def embed_text_sync(text: str, tier: str = "free"):
    client = get_gemini_client(_normalize_tier(tier))
    try:
        res = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text[:2500] # Ограничение чтобы не превышать лимиты токенов
        )
        # GenAI SDK 2026 format: res.embeddings[0].values
        return res.embeddings[0].values
    except Exception as e:
        print("Embed Error:", e)
        return []

async def get_embedding(text: str, tier: str = "free"):
    return await asyncio.to_thread(embed_text_sync, text, tier)


def _render_context_entry(title: str, entry: dict, score: float | None = None, max_chars: int = 1200) -> str:
    relevance = f" | Rel: {score:.2f}" if score is not None else ""
    content = (entry.get("content") or "").strip()
    if len(content) > max_chars:
        content = content[:max_chars].rstrip() + "\n..."
    return f"--- {title}: {entry.get('name')} ({entry.get('category', 'unknown')}{relevance}) ---\n{content}\n"

async def get_context(query: str, *, char_id: str | None = None, world_state: dict | None = None):
    """
    RAG policy:
    1) Mandatory canon sources
    2) Scene-aware sources
    3) Personal character sources
    4) Semantic top matches
    """
    world_state = world_state or {}
    tier = _normalize_tier(world_state.get("llm_tier", SETTINGS.default_llm_tier))
    context_parts = []
    registry = await get_lore_registry()
    if not registry:
        return "В базе знаний нет точных данных. Импровизируй в рамках Дарк-Фэнтези."

    docs = []
    cache_updated = False

    for entry in registry:
        fp = entry.path
        cached = vector_db.get(fp)
        if not cached or cached.get("len") != len(entry.content):
            emb = await get_embedding(f"{entry.name}\n\n{entry.content}", tier=tier)
            if emb:
                vector_db[fp] = {
                    "len": len(entry.content),
                    "emb": emb,
                    "name": entry.name,
                    "content": entry.content,
                    "category": entry.category,
                    "canon_level": entry.canon_level,
                    "path": fp,
                }
                cache_updated = True

        if fp in vector_db and "emb" in vector_db[fp]:
            cached_doc = dict(vector_db[fp])
            cached_doc.setdefault("path", fp)
            cached_doc.setdefault("name", entry.name)
            cached_doc.setdefault("content", entry.content)
            cached_doc.setdefault("category", entry.category)
            cached_doc.setdefault("canon_level", entry.canon_level)
            docs.append(cached_doc)

    if cache_updated:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(vector_db, f)

    if not docs:
        return "В базе знаний нет точных данных. Импровизируй в рамках Дарк-Фэнтези."

    q_emb = await get_embedding(query, tier=tier)
    if not q_emb:
        return "В базе знаний нет точных данных. Импровизируй в рамках Дарк-Фэнтези."

    docs_by_path = {doc.get("path"): doc for doc in docs}
    already_added_paths: set[str] = set()

    mandatory_entries = get_mandatory_lore_entries(registry)
    for entry in mandatory_entries[:2]:
        doc = docs_by_path.get(entry.path)
        if not doc:
            continue
        context_parts.append(_render_context_entry("CANON", doc, max_chars=1000))
        already_added_paths.add(entry.path)

    scene_candidates = select_scene_lore_candidates(registry, world_state, query)
    for entry in scene_candidates[:2]:
        if entry.path in already_added_paths:
            continue
        doc = docs_by_path.get(entry.path)
        if not doc:
            continue
        context_parts.append(_render_context_entry("SCENE", doc, max_chars=900))
        already_added_paths.add(entry.path)

    personal_candidates = get_personal_lore_entries(registry, char_id)
    for entry in personal_candidates[:1]:
        if entry.path in already_added_paths:
            continue
        doc = docs_by_path.get(entry.path)
        if not doc:
            continue
        context_parts.append(_render_context_entry("PERSONAL", doc, max_chars=850))
        already_added_paths.add(entry.path)

    scored_files = []
    for d in docs:
        score = cosine_similarity(q_emb, d["emb"])
        if score > 0.42:
            scored_files.append((score, d["name"], d["content"]))

    scored_files.sort(key=lambda x: x[0], reverse=True)

    semantic_count = 0
    for score, name, text in scored_files:
        matching_doc = next((doc for doc in docs if doc.get("name") == name and doc.get("content") == text), None)
        if not matching_doc:
            continue
        path = matching_doc.get("path", "")
        if path in already_added_paths:
            continue
        context_parts.append(_render_context_entry("SEMANTIC", matching_doc, score=score, max_chars=800))
        already_added_paths.add(path)
        semantic_count += 1
        if semantic_count >= 3:
            break

    return "\n".join(context_parts) if context_parts else "В базе знаний нет точных данных. Импровизируй в рамках Дарк-Фэнтези."
