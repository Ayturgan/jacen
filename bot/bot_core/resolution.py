import json
import re
from typing import Any

from bot_core.ai_service import generate_text
from bot_core.prompts import RESOLUTION_SYSTEM_PROMPT, build_resolution_prompt
from bot_core.runtime import logger


RESOLUTION_DEFAULTS = {
    "action_kind": "utility",
    "risk": "medium",
    "difficulty": "standard",
    "position": "risky",
    "stakes": "Сцена должна ответить честным последствием.",
    "outcome": "partial",
    "cost": "Успех требует цены или открывает новую угрозу.",
    "hard_truth": "Мир не должен уступать без причины.",
    "suggested_consequence": "Покажи ощутимый результат и след от него.",
    "mechanical_hint": "При необходимости используй [ИЗМЕНИТЬ] для hp или stress.",
    "mechanical_directives": [],
    "knowledge_directives": [],
    "follow_up": "Дай сцене новый вектор после исхода.",
    "should_offer_choice": False,
}


ACTION_PROFILES = {
    "social": {
        "stakes": "Доверие, уступка, правда или изменение позиции собеседника.",
        "success": "Собеседник сдвигается, но запоминает цену разговора.",
        "partial": "Ты получаешь уступку, но открываешь слабость, долг или зависимость.",
        "failure": "Собеседник закрывается, злится или перехватывает инициативу.",
        "mechanical": "Чаще всего бей по stress, давлению сцены или будущим обязательствам.",
    },
    "investigation": {
        "stakes": "Улика, скрытая правда, слабое место или понимание опасности.",
        "success": "Дай конкретную находку, зацепку или знание.",
        "partial": "Находка есть, но она шумная, неполная или опасная.",
        "failure": "Улика ускользает, след запутывается или поиск что-то активирует.",
        "mechanical": "Часто уместны [ЗНАНИЕ], рост давления и иногда stress.",
    },
    "stealth": {
        "stakes": "Остаться незамеченным, сохранить позицию и темп.",
        "success": "Герой проходит дальше и удерживает инициативу.",
        "partial": "Герой проходит, но оставляет след, шум или теряет время.",
        "failure": "Тревога растёт, позиция рушится, враг получает угол атаки.",
        "mechanical": "Часто растёт давление сцены, stress, иногда начинается бой.",
    },
    "combat": {
        "stakes": "Ранение, захват позиции, темп боя и выживание.",
        "success": "Герой наносит урон, отбрасывает врага или перехватывает темп.",
        "partial": "Удар проходит, но герой получает ответный вред или теряет позицию.",
        "failure": "Атака захлебнулась, враг давит, герой получает вред или зажимается.",
        "mechanical": "Чаще всего используй [ИЗМЕНИТЬ] для hp/stress и давление сцены.",
    },
    "mystic": {
        "stakes": "Сила, знание, цена магии и отклик тьмы.",
        "success": "Сила отвечает, но должна оставить след в мире.",
        "partial": "Магия срабатывает, но с побочным эффектом, болью или меткой.",
        "failure": "Мир сопротивляется, магия кусает героя или выпускает не ту силу.",
        "mechanical": "Обычно затрагиваются stress, знания, давление и тёмные последствия.",
    },
    "travel": {
        "stakes": "Время, ресурс, скрытая угроза и безопасный путь.",
        "success": "Путь найден, темп удержан, угроза предсказана.",
        "partial": "Путь открыт, но с потерей времени, сил или прикрытия.",
        "failure": "Герой блуждает, натыкается на опасность или приходит поздно.",
        "mechanical": "Обычно растут давление, усталость и новые осложнения.",
    },
    "utility": {
        "stakes": "Локальная цель и мелкое преимущество.",
        "success": "Герой получает желаемое без лишней тяжести.",
        "partial": "Цель достигнута не полностью или с ценой.",
        "failure": "Мир отвечает отказом, задержкой или неудобством.",
        "mechanical": "Используй мягкие последствия и не перегружай сцену.",
    },
}


OUTCOME_RULES = {
    "critical": "Критический успех должен дать сильный прорыв, позицию или редкое преимущество без обнуления всей угрозы сцены.",
    "success": "Обычный успех даёт результат, но мир всё равно продолжает жить и отвечать дальше.",
    "partial": "Частичный успех — базовый исход опасной сцены: цель достигнута, но обязательно есть цена, след или новая проблема.",
    "failure": "Провал должен менять положение героя: потеря темпа, удар по hp/stress, тревога, разоблачение или срыв плана.",
}


GENERIC_SENTENCES = {
    "Сцена должна ответить честным последствием.",
    "Успех требует цены или открывает новую угрозу.",
    "Мир не должен уступать без причины.",
    "Покажи ощутимый результат и след от него.",
    "При необходимости используй [ИЗМЕНИТЬ] для hp или stress.",
    "Дай сцене новый вектор после исхода.",
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


def _coerce_resolution(data: dict[str, Any] | None) -> dict[str, Any]:
    notes = dict(RESOLUTION_DEFAULTS)
    if data:
        notes.update({key: value for key, value in data.items() if value is not None})

    if notes["action_kind"] not in {"social", "investigation", "stealth", "combat", "mystic", "travel", "utility"}:
        notes["action_kind"] = RESOLUTION_DEFAULTS["action_kind"]
    if notes["risk"] not in {"low", "medium", "high", "extreme"}:
        notes["risk"] = RESOLUTION_DEFAULTS["risk"]
    if notes["difficulty"] not in {"trivial", "standard", "hard", "deadly"}:
        notes["difficulty"] = RESOLUTION_DEFAULTS["difficulty"]
    if notes["position"] not in {"controlled", "risky", "desperate"}:
        notes["position"] = RESOLUTION_DEFAULTS["position"]
    if notes["outcome"] not in {"failure", "partial", "success", "critical"}:
        notes["outcome"] = RESOLUTION_DEFAULTS["outcome"]

    if not isinstance(notes.get("mechanical_directives"), list):
        notes["mechanical_directives"] = []
    else:
        notes["mechanical_directives"] = [str(item).strip() for item in notes["mechanical_directives"] if str(item).strip()]

    if not isinstance(notes.get("knowledge_directives"), list):
        notes["knowledge_directives"] = []
    else:
        notes["knowledge_directives"] = [str(item).strip() for item in notes["knowledge_directives"] if str(item).strip()]

    notes["should_offer_choice"] = bool(notes.get("should_offer_choice", False))
    return notes


def _infer_action_kind(message_text: str, fallback: str) -> str:
    text = message_text.lower()
    heuristics = [
        ("combat", ["атак", "удар", "реж", "стреля", "бью", "дерусь"]),
        ("stealth", ["крад", "тихо", "пряч", "скрыт", "незамет"]),
        ("investigation", ["ищу", "осматри", "исслед", "изуч", "улика", "проверя"]),
        ("social", ["убежда", "уговар", "угрожа", "спраш", "допраш", "говорю"]),
        ("mystic", ["маг", "ритуал", "заклин", "колд", "печать", "шепот"]),
        ("travel", ["иду", "плыву", "еду", "путь", "дорог", "маршрут"]),
    ]
    for action_kind, patterns in heuristics:
        if any(pattern in text for pattern in patterns):
            return action_kind
    return fallback


def _pick_mechanical_hint(action_kind: str, outcome: str, risk: str) -> str:
    if action_kind == "combat":
        if outcome == "failure":
            return "Добавь [ИЗМЕНИТЬ: char, hp, -10] или stress, если герой получает прямой урон или ломается под натиском."
        if outcome == "partial":
            return "Часто уместен размен: герой добивается своего, но платит [ИЗМЕНИТЬ: char, hp, -5] или [ИЗМЕНИТЬ: char, stress, +1]."
        return "При успехе можно обойтись без тега урона, но покажи сдвиг позиции врага или преимущества героя."
    if action_kind == "stealth":
        return "Главная цена — тревога, след, потеря позиции или рост давления; hp трогай редко, stress умеренно."
    if action_kind == "investigation":
        return "На успехе и частичном успехе часто уместен [ЗНАНИЕ]; ценой могут стать шум, стресс или новая угроза."
    if action_kind == "social":
        return "Обычно бей по stress, обязательствам, вине или политической цене, а не по hp."
    if action_kind == "mystic":
        return "Мистика любит цену: stress, метка, отклик тьмы, побочный эффект или опасное знание."
    if action_kind == "travel":
        return "Цена путешествия — время, истощение, невыгодный маршрут или встреча с новой угрозой."
    if risk in {"high", "extreme"}:
        return "Высокий риск требует заметной цены: stress, потеря позиции, шум или серьёзное осложнение."
    return ACTION_PROFILES[action_kind]["mechanical"]


def _build_mechanical_directives(char_id: str, action_kind: str, outcome: str, risk: str) -> list[str]:
    directives: list[str] = []

    if action_kind == "combat":
        if outcome == "failure":
            directives.append(f"[ИЗМЕНИТЬ: {char_id}, hp, -10]")
            if risk in {"high", "extreme"}:
                directives.append(f"[МИР: pressure_clock, +1]")
        elif outcome == "partial":
            directives.append(f"[ИЗМЕНИТЬ: {char_id}, hp, -5]")
            directives.append(f"[ИЗМЕНИТЬ: {char_id}, stress, +1]")
        elif outcome == "critical":
            directives.append("[МИР: pressure_clock, -1]")

    elif action_kind == "stealth":
        if outcome == "failure":
            directives.append(f"[МИР: pressure_clock, +2]")
            directives.append(f"[ИЗМЕНИТЬ: {char_id}, stress, +1]")
        elif outcome == "partial":
            directives.append(f"[МИР: pressure_clock, +1]")
        elif outcome == "critical":
            directives.append("[МИР: pressure_clock, -1]")

    elif action_kind == "investigation":
        if outcome == "failure":
            directives.append(f"[МИР: pressure_clock, +1]")
        elif outcome == "partial":
            directives.append(f"[ИЗМЕНИТЬ: {char_id}, stress, +1]")
        elif outcome == "critical":
            directives.append("[МИР: pressure_clock, -1]")

    elif action_kind == "social":
        if outcome == "failure":
            directives.append(f"[ИЗМЕНИТЬ: {char_id}, stress, +1]")
            directives.append("[МИР: pressure_clock, +1]")
        elif outcome == "partial":
            directives.append(f"[ИЗМЕНИТЬ: {char_id}, stress, +1]")

    elif action_kind == "mystic":
        if outcome == "failure":
            directives.append(f"[ИЗМЕНИТЬ: {char_id}, stress, +2]")
            directives.append("[МИР: dark_points, +1]")
        elif outcome == "partial":
            directives.append(f"[ИЗМЕНИТЬ: {char_id}, stress, +1]")
            directives.append("[МИР: dark_points, +1]")
        elif outcome == "critical":
            directives.append("[МИР: dark_points, +1]")

    elif action_kind == "travel":
        if outcome == "failure":
            directives.append(f"[ИЗМЕНИТЬ: {char_id}, stress, +1]")
            directives.append("[МИР: threat_level, +5]")
        elif outcome == "partial":
            directives.append("[МИР: pressure_clock, +1]")

    elif risk in {"high", "extreme"} and outcome in {"failure", "partial"}:
        directives.append(f"[ИЗМЕНИТЬ: {char_id}, stress, +1]")

    seen: set[str] = set()
    unique_directives: list[str] = []
    for directive in directives:
        if directive not in seen:
            unique_directives.append(directive)
            seen.add(directive)
    return unique_directives


def _build_knowledge_directives(char_id: str, action_kind: str, outcome: str, notes: dict[str, Any]) -> list[str]:
    if action_kind not in {"investigation", "mystic"}:
        return []
    if outcome not in {"success", "critical", "partial"}:
        return []

    title_map = {
        ("investigation", "critical"): "Прорыв в расследовании",
        ("investigation", "success"): "Новая улика",
        ("investigation", "partial"): "Осколок истины",
        ("mystic", "critical"): "Откровение Тьмы",
        ("mystic", "success"): "Мистическое озарение",
        ("mystic", "partial"): "Опасное касание тайны",
    }
    whisper_map = {
        "investigation": "Нить истины больно натянулась. Герой понял больше, чем хотел.",
        "mystic": "Мрак ответил слишком близко. Истина вошла под кожу вместе с холодом.",
    }

    title = title_map.get((action_kind, outcome), "Новое знание")
    stakes = str(notes.get("stakes", "")).strip()
    consequence = str(notes.get("suggested_consequence", "")).strip()
    content_parts = [part for part in [stakes, consequence] if part]
    if not content_parts:
        return []

    content = " ".join(content_parts)
    content = re.sub(r"\s+", " ", content).strip()
    content = content.replace("|", ",")[:280]
    whisper = whisper_map[action_kind].replace("|", ",")
    title = title.replace("|", ",")
    if not content:
        return []

    return [f"[ЗНАНИЕ: {char_id} | {title} | {content} | {whisper}]"]


def _enrich_resolution(notes: dict[str, Any], message_text: str, director_notes: dict | None = None) -> dict[str, Any]:
    notes = dict(notes)
    notes["action_kind"] = _infer_action_kind(message_text, notes.get("action_kind", "utility"))
    profile = ACTION_PROFILES[notes["action_kind"]]
    outcome = notes.get("outcome", "partial")

    if not notes.get("stakes") or notes["stakes"] in GENERIC_SENTENCES:
        notes["stakes"] = profile["stakes"]

    if not notes.get("cost") or notes["cost"] in GENERIC_SENTENCES:
        notes["cost"] = profile.get(outcome, profile["partial"])

    if not notes.get("hard_truth") or notes["hard_truth"] in GENERIC_SENTENCES:
        notes["hard_truth"] = OUTCOME_RULES[outcome]

    if not notes.get("suggested_consequence") or notes["suggested_consequence"] in GENERIC_SENTENCES:
        consequence_seed = profile.get(outcome, profile["partial"])
        director_hint = director_notes.get("consequence_hint", "") if director_notes else ""
        notes["suggested_consequence"] = f"{consequence_seed} {director_hint}".strip()

    if not notes.get("mechanical_hint") or notes["mechanical_hint"] in GENERIC_SENTENCES:
        notes["mechanical_hint"] = _pick_mechanical_hint(notes["action_kind"], outcome, notes.get("risk", "medium"))

    if not notes.get("mechanical_directives"):
        notes["mechanical_directives"] = _build_mechanical_directives(
            notes.get("char_id", "Unknown"),
            notes["action_kind"],
            outcome,
            notes.get("risk", "medium"),
        )

    if not notes.get("knowledge_directives"):
        notes["knowledge_directives"] = _build_knowledge_directives(
            notes.get("char_id", "Unknown"),
            notes["action_kind"],
            outcome,
            notes,
        )

    if not notes.get("follow_up") or notes["follow_up"] in GENERIC_SENTENCES:
        notes["follow_up"] = {
            "critical": "Дай герою окно преимущества и переведи сцену к новому сильному выбору.",
            "success": "Закрепи результат и покажи, какая новая дверь теперь открылась.",
            "partial": "Немедленно покажи цену и заставь героя решать, как жить с новым осложнением.",
            "failure": "Передай инициативу миру, врагу или угрозе и заставь сцену кусаться сильнее.",
        }[outcome]

    if notes["action_kind"] in {"stealth", "social", "mystic"} and outcome in {"partial", "failure"}:
        notes["should_offer_choice"] = True

    notes["resolution_profile"] = f"{notes['action_kind']}::{outcome}"
    return notes


async def resolve_action(
    *,
    char_id: str,
    message_text: str,
    world_state: dict,
    session_history: list[str],
    char_info: dict | None,
    personal_ctx: str,
    char_last_action: str,
    vault_info: str,
    director_notes: dict | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    resolution_context = {
        "char_id": char_id,
    }
    prompt = build_resolution_prompt(
        char_id=char_id,
        message_text=message_text,
        world_state=world_state,
        session_history=session_history,
        char_info=char_info,
        personal_ctx=personal_ctx,
        char_last_action=char_last_action,
        vault_info=vault_info,
        director_notes=director_notes,
    )

    try:
        raw_response = await generate_text(
            prompt,
            model=model,
            system_prompt=RESOLUTION_SYSTEM_PROMPT,
            temperature=0.2,
        )
        result = _coerce_resolution(_extract_json_block(raw_response))
        result.update(resolution_context)
        return _enrich_resolution(result, message_text, director_notes)
    except Exception as error:
        logger.error(f"Resolution engine error: {error}")
        fallback = _coerce_resolution(None)
        fallback.update(resolution_context)
        return _enrich_resolution(fallback, message_text, director_notes)
