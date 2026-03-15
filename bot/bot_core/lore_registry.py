import os
import re
from dataclasses import dataclass

from bot_core.config import PROJECT_ROOT


LORE_DIRS = [
    ("00_Сюжет", "plot"),
    ("01_Герои", "heroes"),
    ("02_NPC", "npc"),
    ("03_Мир", "world"),
    ("04_Архив_ГМ", "archive"),
]

MANDATORY_CANON_FILES = {
    "Сюжетный канон.md",
    "Полный сценарий.md",
}

HERO_FILE_HINTS = {
    "Elix": ["Эликс", "Тайэрис", "Elix"],
    "Silas": ["Сайлас", "Silas"],
    "Varo": ["Варо", "Varo"],
    "Lysandra": ["Лисандра", "Lysandra"],
}


@dataclass(frozen=True)
class LoreEntry:
    path: str
    name: str
    category: str
    content: str
    canon_level: str


_registry_cache: list[LoreEntry] = []
_registry_signature: tuple[tuple[str, int], ...] = ()


def _compute_signature() -> tuple[tuple[str, int], ...]:
    signatures: list[tuple[str, int]] = []
    for rel_dir, _ in LORE_DIRS:
        abs_dir = os.path.join(PROJECT_ROOT, rel_dir)
        if not os.path.exists(abs_dir):
            continue
        for root, _, files in os.walk(abs_dir):
            for file_name in files:
                if not file_name.endswith(".md"):
                    continue
                full_path = os.path.join(root, file_name)
                try:
                    stat = os.stat(full_path)
                    signatures.append((full_path, int(stat.st_mtime)))
                except OSError:
                    continue
    signatures.sort(key=lambda item: item[0])
    return tuple(signatures)


def _canon_level(name: str, category: str) -> str:
    if name in MANDATORY_CANON_FILES:
        return "canon"
    if category in {"plot", "heroes", "world"}:
        return "canon"
    if category == "archive":
        return "gm_only"
    return "rumor"


def _load_registry_sync() -> list[LoreEntry]:
    entries: list[LoreEntry] = []
    for rel_dir, category in LORE_DIRS:
        abs_dir = os.path.join(PROJECT_ROOT, rel_dir)
        if not os.path.exists(abs_dir):
            continue
        for root, _, files in os.walk(abs_dir):
            for file_name in files:
                if not file_name.endswith(".md"):
                    continue
                full_path = os.path.join(root, file_name)
                try:
                    with open(full_path, "r", encoding="utf-8") as file:
                        content = file.read()
                except Exception:
                    continue
                entries.append(
                    LoreEntry(
                        path=full_path,
                        name=file_name,
                        category=category,
                        content=content,
                        canon_level=_canon_level(file_name, category),
                    )
                )
    return entries


async def get_lore_registry(force_reload: bool = False) -> list[LoreEntry]:
    global _registry_cache, _registry_signature
    signature = _compute_signature()
    if force_reload or not _registry_cache or signature != _registry_signature:
        _registry_cache = _load_registry_sync()
        _registry_signature = signature
    return _registry_cache


def get_mandatory_lore_entries(registry: list[LoreEntry]) -> list[LoreEntry]:
    mandatory = [entry for entry in registry if entry.name in MANDATORY_CANON_FILES]
    mandatory.sort(key=lambda entry: 0 if entry.name == "Сюжетный канон.md" else 1)
    return mandatory


def get_personal_lore_entries(registry: list[LoreEntry], char_id: str | None) -> list[LoreEntry]:
    if not char_id:
        return []
    hints = HERO_FILE_HINTS.get(char_id, [char_id])
    selected: list[LoreEntry] = []
    for entry in registry:
        if entry.category not in {"heroes", "archive"}:
            continue
        lowered_name = entry.name.lower()
        if any(hint.lower() in lowered_name for hint in hints):
            selected.append(entry)
    return selected


def select_scene_lore_candidates(registry: list[LoreEntry], world_state: dict | None, query: str) -> list[LoreEntry]:
    world_state = world_state or {}
    act = str(world_state.get("current_act", "")).strip()
    scene = str(world_state.get("current_scene", "")).strip()
    location = str(world_state.get("current_location", "")).strip()

    query_tokens = re.findall(r"\w+", query.lower())
    scene_tokens = re.findall(r"\w+", f"{scene} {location}".lower())
    act_tokens = [act] if act else []

    def _score(entry: LoreEntry) -> int:
        text = f"{entry.name} {entry.content[:2000]}".lower()
        score = 0
        if entry.category in {"plot", "world", "npc"}:
            score += 2
        for token in scene_tokens:
            if len(token) > 3 and token in text:
                score += 3
        for token in query_tokens:
            if len(token) > 4 and token in text:
                score += 2
        for token in act_tokens:
            if token and token in text:
                score += 1
        return score

    ranked = sorted(registry, key=_score, reverse=True)
    return [entry for entry in ranked if _score(entry) > 0][:5]