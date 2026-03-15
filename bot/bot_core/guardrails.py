import re


META_PATTERNS = [
    r"\bпромпт\w*\b",
    r"\bмодел\w*\b",
    r"\bsystem\b",
    r"\brag\b",
    r"\bapi\b",
]

ALLOWED_CAMERA = {"Elix", "Silas", "Varo", "Lysandra", "ALL"}


def _sanitize_meta(text: str) -> tuple[str, bool]:
    replaced = text
    changed = False
    for pattern in META_PATTERNS:
        new_text = re.sub(pattern, "тайна", replaced, flags=re.IGNORECASE)
        if new_text != replaced:
            changed = True
            replaced = new_text
    return replaced, changed


def _sanitize_camera_tags(text: str) -> tuple[str, bool]:
    changed = False

    def repl(match: re.Match) -> str:
        nonlocal changed
        camera = (match.group(1) or "").strip()
        if camera in ALLOWED_CAMERA:
            return match.group(0)
        changed = True
        return "[КАМЕРА: ALL]"

    updated = re.sub(r"\[КАМЕРА:\s*([^\]]+)\]", repl, text)
    return updated, changed


def apply_continuity_guardrails(
    *,
    text: str,
    world_state: dict | None = None,
    continuity_notes: dict | None = None,
) -> tuple[str, list[str]]:
    guard_issues: list[str] = []
    checked = text or ""

    checked, meta_changed = _sanitize_meta(checked)
    if meta_changed:
        guard_issues.append("meta-leak-sanitized")

    checked, camera_changed = _sanitize_camera_tags(checked)
    if camera_changed:
        guard_issues.append("camera-tag-normalized")

    pending_roll_char = (world_state or {}).get("pending_roll_char", "")
    if pending_roll_char and "[БРОСОК:" in checked and pending_roll_char not in checked:
        checked = checked.replace("[БРОСОК:", f"[БРОСОК: {pending_roll_char} | ", 1)
        guard_issues.append("pending-roll-char-enforced")

    if continuity_notes and continuity_notes.get("guardrail") and "не откатывай" in continuity_notes.get("guardrail", "").lower():
        if re.search(r"\b(ничего\s+не\s+было|это\s+не\s+происходило)\b", checked, flags=re.IGNORECASE):
            checked = re.sub(
                r"\b(ничего\s+не\s+было|это\s+не\s+происходило)\b",
                "последствия остаются и требуют ответа",
                checked,
                flags=re.IGNORECASE,
            )
            guard_issues.append("continuity-retcon-softened")

    return checked, guard_issues