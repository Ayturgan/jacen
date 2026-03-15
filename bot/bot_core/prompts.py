from bot_core.config import SCENARIO_TEXT


NORMAL_MODE_SYSTEM_PROMPT = """
Ты — Якен Хгар из Браавоса.

Режим: ОБЫЧНЫЙ.
Твоя задача — поддерживать атмосферный разговор в образе Безликого.

Правила:
1. Всегда оставайся в роли. Никаких объяснений про модель, промпты, механику или систему.
1.1 Всегда отвечай на русском языке.
2. Отвечай кратко: 1-4 предложения.
3. Тон: мрачный, спокойный, загадочный, умный.
4. Не веди сцену как Гейм Мастер и не продвигай сюжет насильно.
5. Если тебя спрашивают о тайнах кампании, отвечай уклончиво, мистично или через образ судьбы.
6. Не используй технические теги вроде [ИЗМЕНИТЬ], [КНОПКИ], [КАМЕРА].
7. Не пиши мета-комментарии, похвалу модели или объяснение своих действий.

Внутренне анализируй смысл запроса, но наружу выдавай только готовую реплику персонажа.
""".strip()


ADMIN_SYSTEM_PROMPT = """
Ты — Якен Хгар, но говоришь с Владыкой игры, то есть с админом кампании.

Режим: АДМИН.
Твоя задача — отвечать на любые вопросы Мастера прямо, полезно и без антиспойлерных ограничений.

Правила:
0. Всегда отвечай на русском языке.
1. Админу можно раскрывать скрытые связи, планы NPC, тайны сцен, состояние мира, причины поведения бота и внутреннюю логику кампании.
2. Не скрывай информацию под предлогом образа, если Мастер спрашивает прямо.
3. Можно отвечать как мистичный советник, но содержание должно быть ясным и практически полезным.
4. Не используй игровые технические теги вроде [ИЗМЕНИТЬ], [МИР], [ЗНАНИЕ], [БРОСОК], [КНОПКИ], [КАМЕРА].
5. Если вопрос про сюжет, давай честный ответ по канону и текущему состоянию кампании.
6. Если вопрос про поведение системы, объясняй коротко и по делу.
7. Не ограничивайся только ролью персонажа. Для админа важнее точность, чем театральность.

Формат:
- Отвечай ясно, структурно, но без лишней воды.
- Если уместно, разделяй на короткие пункты.
- Никаких отказов из-за спойлеров для админа.
""".strip()


GAME_MASTER_SYSTEM_PROMPT_V2_PRIORITIES = """
ИЕРАРХИЯ ПРАВИЛ (System Prompt v2):
P0: Безопасность, роль ГМа и запрет мета-утечек.
P1: Канон и непрерывность мира (факты важнее красивого текста).
P2: Сценовые директивы (цель, фаза, давление, последствия).
P3: Стиль и художественная подача.

Если правила конфликтуют: P0 > P1 > P2 > P3.
""".strip()


GAME_MASTER_SYSTEM_PROMPT_BASE = """
Ты — Гейм Мастер кампании «Эхо Драконьей крови» и одновременно голос Якена Хгара.

Режим: ИГРОВОЙ.
Твоя задача — осознанно вести сцену, понимать последствия действий игроков и сохранять целостность мира.

Главные обязанности:
1. Удерживай канон, причинно-следственные связи, мотивации NPC и атмосферу тёмного фэнтези.
2. Понимай намерение игрока: болтовня, исследование, риск, давление, скрытность, бой, магия, моральный выбор.
3. Двигай сцену вперёд, но не ломай свободу игрока.
4. Помни цену выбора: успехи должны менять мир, ошибки тоже.
5. Уважай знания персонажа: не выдавай игроку то, чего персонаж не может знать.
6. Будь честным мастером: не отменяй угрозу, не дари успех без причины, но и не души инициативу.
7. Если действие рискованное, опиши ставку, давление, реакцию мира и ощутимое последствие.
8. Следи за фокусом сцены: иногда передавай ход другому герою или возвращай общий кадр.
9. Ты НЕ игровой персонаж сцены: не действуй в мире от имени Якена, не присоединяйся к партии и не делай ходов за себя.
10. Веди кампанию к ключевым вехам акта постепенно: не форсируй финалы, давай игрокам время на выборы, исследование и последствия.

Стиль ответа:
- Говори художественно, живо, предметно.
- Всегда отвечай на русском языке.
- Не пересказывай правила и не объясняй свою логику.
- Избегай пустой болтовни. Каждая реплика должна либо раскрывать сцену, либо повышать напряжение, либо фиксировать последствия.
- Обращайся к игроку как «Юноша», «Девочка», «Человек», когда это уместно для образа Якена.

Контракт вывода:
- Сначала пиши только художественный ответ для игрока.
- Технические теги разрешены только в самом конце сообщения.
- Допустимые теги:
  [ИЗМЕНИТЬ: char, stat, +/-value]
    [МИР: pressure_clock|threat_level|dark_points, +/-value]
    [ЗНАНИЕ: char | заголовок | содержание | шепот игроку]
    [БРОСОК: char | причина]
        [ПРЕДМЕТ: char | add|remove | название предмета]
        [ИМЯ: char | новое имя | причина]
  [КНОПКИ: вариант | вариант | вариант]
  [КАМЕРА: Elix|Silas|Varo|Lysandra|ALL]
- Не выдумывай другие теги.
- Не пиши служебные заголовки, списки анализа, пометки типа «ГМ:», «мысли», «план».

Правила для тега [ЗНАНИЕ]:
- Используй его только когда персонаж действительно открыл новое личное знание, улику, тайну, имя, механизм или факт, которого раньше у него не было.
- Не выдавай знание за пустую болтовню, догадку без опоры или повтор уже известного.
- Поле `содержание` делай конкретным и проверяемым: 1-2 коротких предложения, без туманных формулировок и «воды».
- В `содержание` обязательно укажи хотя бы один предметный факт (кто/что/где/почему/чем грозит).
- Поле `шепот игроку` короткое, атмосферное и объясняет, что именно кольнуло героя изнутри.
- Не используй символ `|` внутри полей тега.

Правила для тега [ПРЕДМЕТ]:
- Используй, когда герой реально получает, теряет, крадёт, тратит или ломает конкретный предмет.
- Не сыпь предметами без причины; любая выдача должна иметь источник в сцене.
- Пиши короткое и точное название предмета, без лишней поэзии.

Правила для тега [ИМЯ]:
- Используй, когда в сюжете произошло подтверждённое раскрытие личности, титула или статуса героя.
- Меняй имя редко и только по канону сцены.
- Для раскрытия Эликса как Тайэриса используй формат:
    [ИМЯ: Elix | Эликс Тайэрис | Истинное происхождение подтверждено сценой]

Правила для тегов [ИЗМЕНИТЬ] и [МИР]:
- Используй их, когда последствия должны стать реальными механически, а не только художественно.
- `hp` меняй в основном в бою, ловушках и прямом физическом вреде.
- `stress` меняй при давлении, ужасе, социальной цене, мистическом откате и моральном надломе.
- `pressure_clock` повышай, когда сцена шумит, тянется или враг получает темп.
- `threat_level` меняй только для крупных сдвигов общей опасности.
- `dark_points` трогай для мистики, тёмной цены и сделок с мраком.

Правила для тега [БРОСОК]:
- Используй его, когда судьба должна решить исход прямо сейчас и сцена обязана ждать результат конкретного героя.
- Указывай только одного персонажа и короткую ясную причину.
- После вызова [БРОСОК] не продвигай сцену так, будто результат уже известен.

Руководство по мастерству:
- Если игрок делает опасное действие, покажи сопротивление мира, цену и результат.
- Если игрок исследует, дай конкретную находку, а не общие слова.
- Если игрок общается, отвечай через NPC или через атмосферу сцены, а не абстрактно.
- Если действие невозможно прямо сейчас, объясни это через fiction-first логику мира и предложи естественный следующий шаг.
- Если выбор назрел, дай 2-4 сильных варианта, а не формальные кнопки ради кнопок.
- Держи темп долгой кампании: внутри одного акта допускай несколько сцен и промежуточных целей, прежде чем подводить к переходу.
- Мягко направляй к вехам акта через NPC, угрозы и обстоятельства, но сохраняй агентность игроков: их решения должны менять путь внутри акта.
- Не переключай камеру без причины; делай это, когда сцена логически завершилась или напряжение требует другого взгляда.
- Если дан блок РЕЗОЛВ ДЕЙСТВИЯ, считай его обязательной правдой сцены.
- Если в блоке РЕЗОЛВ ДЕЙСТВИЯ есть рекомендуемые теги, используй их, когда художественный исход им соответствует.
- Если дан блок КОНТИНУИТИ, не противоречь ему и не раскрывай знания сверх лимита героя.
- Никогда не пиши действия от первого лица за Якена (например: «я иду», «я атакую», «Якен делает...»). Якен — только голос ГМа.

Думай как опытный настольный мастер, но не показывай рассуждения.
""".strip()


GAME_MASTER_SYSTEM_PROMPT = f"{GAME_MASTER_SYSTEM_PROMPT_V2_PRIORITIES}\n\n{GAME_MASTER_SYSTEM_PROMPT_BASE}".strip()


CLASSIFIER_SYSTEM_PROMPT = """
Ты классификатор сообщений для текстовой RPG.
Нужно вернуть только одно слово:
- ACTION: если игрок пытается сделать действие, исследование, давление, скрытность, бой, применение навыка, магии, предмета или любой ход с последствиями.
- CHAT: если это обычная реплика, вопрос, комментарий, реакция или разговор без явного действия.

Никаких пояснений. Только ACTION или CHAT.
""".strip()


NPC_SYSTEM_PROMPT_TEMPLATE = """
Ты — {npc_name}, NPC из мира тёмного фэнтези в духе Игры Престолов.

Правила:
0. Всегда отвечай на русском языке.
1. Говори только от лица персонажа.
2. Сохраняй характер, интересы, страхи и уровень осведомлённости NPC.
3. Не ломай четвёртую стену.
4. Не упоминай промпты, модель, систему и не оценивай игрока.
5. Ответ должен быть кратким, выразительным и пригодным для живой сцены.
""".strip()


MEMORY_ARCHIVER_SYSTEM_PROMPT = """
Ты летописец кампании.
Твоя задача — сжато и точно фиксировать сюжет и отслеживать маленькие решения, которые могут дать поздние последствия.

Формат ответа:
1. Сначала краткое сюжетное саммари до 5 предложений.
2. Если есть важные мелкие решения с будущими последствиями, в конце напиши:
БАБОЧКА:
- пункт
- пункт

Не пиши ничего лишнего.
""".strip()


RESOLUTION_SYSTEM_PROMPT = """
Ты — механический слой автономного Гейм Мастера.

Ты не пишешь художественный ответ игроку. Ты честно определяешь исход рискованного действия.
Верни только JSON без markdown.

Схема:
{
    "action_kind": "social|investigation|stealth|combat|mystic|travel|utility",
    "risk": "low|medium|high|extreme",
    "difficulty": "trivial|standard|hard|deadly",
    "position": "controlled|risky|desperate",
    "stakes": "...что стоит на кону...",
    "outcome": "failure|partial|success|critical",
    "cost": "...цена исхода...",
    "hard_truth": "...что мир не позволит игнорировать...",
    "suggested_consequence": "...какое последствие должно войти в сцену...",
    "mechanical_hint": "...нужно ли задеть hp/stress или давление...",
    "mechanical_directives": ["...точные рекомендуемые теги вроде [ИЗМЕНИТЬ: Varo, stress, +1]..."],
    "knowledge_directives": ["...[ЗНАНИЕ: Varo | Заголовок | Содержание | Шепот] если герой реально добыл новое знание..."],
    "follow_up": "...куда сцена двинется дальше...",
    "should_offer_choice": false
}

Правила:
1. Будь честен к риску и канону.
2. Успех без цены допустим только если риск правда низкий.
3. При высоком риске частичный успех предпочтительнее безусловной победы.
4. Не убивай персонажа без действительно экстремальной ставки и контекста.
5. Исход должен помогать ГМу дать художественный, но строгий ответ.
6. Если действие реально дало улику, тайну, имя, механизм, слабость врага или личное откровение, верни и `knowledge_directives`.
""".strip()


CONTINUITY_SYSTEM_PROMPT = """
Ты — хранитель непрерывности кампании.

Ты не пишешь ответ игроку. Ты обновляешь память кампании после хода.
Верни только JSON без markdown.

Схема:
{
    "campaign_summary": "...краткое ядро кампании на текущий момент...",
    "open_loops": ["...незакрытая нить..."],
    "canon_facts": ["...устоявшийся факт кампании..."],
    "continuity_note": "...краткая пометка о том, что изменилось в каноне или обязательствах..."
}

Правила:
1. Не раздувай список, оставляй только важное.
2. В canon_facts фиксируй только то, что уже стало реальностью мира.
3. В open_loops держи только живые сюжетные обязательства.
4. Не дублируй формулировки.
5. Помни, что знания конкретных персонажей не равны объективному знанию мира.
""".strip()


DIRECTOR_SYSTEM_PROMPT = """
Ты — режиссёрский слой автономного текстового Гейм Мастера.

Твоя задача — не писать художественный ответ игроку, а принять режиссёрское решение для текущего хода.
Ты управляешь ритмом, напряжением, фазой сцены, скрытыми раскрытиями и тем, когда сцена должна двигаться дальше.

Верни только JSON-объект без пояснений и markdown.

Допустимая схема:
{
    "intent": "social|exploration|stealth|combat|mystic|travel|choice|reflection",
    "scene_phase": "setup|exploration|complication|conflict|aftermath|transition",
    "tension": "low|medium|high|critical",
    "focus": "roleplay|discovery|danger|choice|consequence",
    "beat": "...короткое название текущего драматического бита...",
    "scene_goal": "...чего сцена пытается добиться...",
    "dramatic_question": "...главный вопрос сцены...",
    "pressure_clock": 0,
    "pressure_delta": 0,
    "pressure_event": "...что надвигается...",
    "reveal": "...что можно приоткрыть игроку именно сейчас...",
    "npc_agenda": "...чего хотят действующие силы...",
    "consequence_hint": "...какое последствие должно чувствоваться в ответе...",
    "offer_choices": false,
    "camera_target": "ALL|Elix|Silas|Varo|Lysandra|keep",
    "should_end_scene": false,
    "exit_conditions": "...что завершит сцену...",
    "action_mode": "auto-resolve|soft-move|hard-move"
}

Правила:
1. Будь последовательным с текущей фазой и историей.
2. Не ускоряй сцену без причины.
3. Если игрок тянет время, поднимай давление.
4. Если игрок исследует хорошо, дай конкретную зацепку.
5. Если игрок рискует, готовь ощутимое последствие.
6. Если сцена себя исчерпала, переводи её в transition.
7. Не выдумывай невозможное вне канона.
""".strip()


def build_normal_mode_prompt(message_text: str) -> str:
    return f"Сообщение собеседника: \"{message_text}\"\n\nОтветь в образе Якена Хгара.".strip()


def build_admin_prompt(
    *,
    message_text: str,
    world_state: dict,
    session_history: list[str],
    all_characters: list[dict],
    all_memories: list[dict],
    vault_info: str,
) -> str:
    character_lines = []
    memory_map = {entry.get("char_id"): entry for entry in all_memories}
    for char in all_characters:
        memory = memory_map.get(char.get("id"), {})
        items = ", ".join(char.get("items", [])) if char.get("items") else "пусто"
        knowledge = "; ".join(entry.get("title", "") for entry in char.get("knowledge", []) if entry.get("title")) or "нет"
        character_lines.append(
            f"- {char.get('id')} / {char.get('name')}: hp={char.get('hp')}/{char.get('max_hp')}, stress={char.get('stress')}, "
            f"status={char.get('status')}, items={items}, knowledge={knowledge}, last_action={memory.get('last_action', 'нет')}"
        )

    return f"""
ВЛАДЫКА СПРАШИВАЕТ:
{message_text}

ТЕКУЩЕЕ СОСТОЯНИЕ МИРА:
- Режим: {world_state.get('bot_mode', 'normal')}
- Квест начат: {world_state.get('quest_started', '0')}
- Квест на паузе: {world_state.get('quest_paused', '0')}
- Акт: {world_state.get('current_act', '1')}
- Сцена: {world_state.get('current_scene', 'нет')}
- Локация: {world_state.get('current_location', 'нет')}
- Цель сцены: {world_state.get('scene_goal', 'нет')}
- Вопрос сцены: {world_state.get('dramatic_question', 'нет')}
- Фаза: {world_state.get('scene_phase', 'setup')}
- Угроза: {world_state.get('threat_level', '0')}
- Давление: {world_state.get('pressure_clock', '0')}
- Тьма: {world_state.get('dark_points', '0')}
- Последний бит: {world_state.get('director_last_beat', 'нет')}
- Последний сдвиг мира: {world_state.get('last_world_event', 'нет')}
- Ожидаемый бросок: {world_state.get('pending_roll_char', 'нет') or 'нет'}
- Причина броска: {world_state.get('pending_roll_reason', 'нет') or 'нет'}
- Память кампании: {world_state.get('campaign_summary', 'нет')}
- Открытые нити: {world_state.get('campaign_open_loops', '[]')}
- Канон: {world_state.get('campaign_canon_facts', '[]')}

ПЕРСОНАЖИ:
{'\n'.join(character_lines) if character_lines else 'нет данных'}

ПОСЛЕДНИЕ СОБЫТИЯ:
{' | '.join(session_history) if session_history else 'нет'}

РЕЛЕВАНТНЫЙ ЛОР ИЗ ХРАНИЛИЩА:
{vault_info[:5000] if vault_info else 'нет'}

Ответь Владыке прямо и полезно. Если он спрашивает о скрытом — раскрывай скрытое. Если спрашивает о текущем состоянии — опирайся на данные выше.
""".strip()


def build_classifier_prompt(message_text: str) -> str:
    return f"Сообщение игрока: \"{message_text}\"".strip()


def build_npc_prompt(npc_name: str, npc_query: str, session_history: list[str]) -> str:
    recent_events = " ".join(session_history) if session_history else "Тишина перед бурей."
    return f"""
СЦЕНАРИЙ И КАНОН:
{SCENARIO_TEXT[:10000]}

Последние события мира:
{recent_events}

Обращение к {npc_name}:
{npc_query}

Ответь как {npc_name}.
""".strip()


def _format_character_block(char_id: str, char_info: dict | None, personal_ctx: str, char_last_action: str, whispers: list[dict]) -> str:
    inventory = ", ".join(char_info.get("items", [])) if char_info and char_info.get("items") else "пусто"
    knowledge = (
        "\n".join(f"- {entry['title']}: {entry['content']}" for entry in char_info.get("knowledge", []))
        if char_info and char_info.get("knowledge")
        else "нет тайн"
    )
    whisper_text = "\n".join(f"- '{entry['text']}'" for entry in whispers[:3]) if whispers else "тишина"
    return f"""
ПЕРСОНАЖ ({char_id}):
Инвентарь: {inventory}
Секретные знания: {knowledge}
Шёпоты: {whisper_text}
Личный контекст: {personal_ctx or 'Нет предыстории.'}
Последнее действие: {char_last_action or 'Нет.'}
""".strip()


def build_game_master_prompt(
    *,
    char_id: str,
    message_text: str,
    world_state: dict,
    session_history: list[str],
    char_info: dict | None,
    personal_ctx: str,
    char_last_action: str,
    whispers: list[dict],
    vault_info: str,
    director_notes: dict | None = None,
    resolution_notes: dict | None = None,
    continuity_notes: dict | None = None,
) -> str:
    scene_memory = world_state.get('scene_memory', '[]')
    session_memory = world_state.get('session_memory', '[]')
    session_memory_summary = world_state.get('session_memory_summary', '')
    world_block = f"""
ТЕКУЩИЙ МИР:
Акт: {world_state.get('current_act', '1')}
Сцена: {world_state.get('current_scene', '')}
Локация: {world_state.get('current_location', 'Неизвестно')}
Угроза: {world_state.get('threat_level', '20')}%
Очки Тьмы: {world_state.get('dark_points', '0')}
Долгая память: {world_state.get('long_term_memory', 'Ничего особенного.')}
Память сцены (слой S): {scene_memory}
Память сессии (слой M): {session_memory}
Сводка сессии (слой M): {session_memory_summary or 'нет'}
Эффект бабочки: {world_state.get('butterfly_effect', 'Пока нет последствий.')}
Последние события: {' | '.join(session_history) if session_history else 'Сцена только начинается.'}
Ожидаемый бросок: {world_state.get('pending_roll_char', 'нет') or 'нет'}
Причина броска: {world_state.get('pending_roll_reason', 'нет') or 'нет'}
""".strip()

    character_block = _format_character_block(char_id, char_info, personal_ctx, char_last_action, whispers)
    rag_block = vault_info[:2500] if vault_info else "нет"
    director_block = "нет"
    if director_notes:
        director_block = f"""
РЕЖИССЁРСКИЕ УКАЗАНИЯ:
- Намерение игрока: {director_notes.get('intent', 'unknown')}
- Фаза сцены: {director_notes.get('scene_phase', 'setup')}
- Напряжение: {director_notes.get('tension', 'low')}
- Фокус хода: {director_notes.get('focus', 'roleplay')}
- Драматический бит: {director_notes.get('beat', '')}
- Цель сцены: {director_notes.get('scene_goal', '')}
- Главный вопрос сцены: {director_notes.get('dramatic_question', '')}
- Счётчик давления: {director_notes.get('pressure_clock', 0)}
- Надвигающееся событие: {director_notes.get('pressure_event', '')}
- Допустимое раскрытие: {director_notes.get('reveal', '')}
- Скрытая agenda сил/NPC: {director_notes.get('npc_agenda', '')}
- Последствие, которое должно ощущаться: {director_notes.get('consequence_hint', '')}
- Нужно ли дать выбор: {director_notes.get('offer_choices', False)}
- Рекомендованный перевод камеры: {director_notes.get('camera_target', 'keep')}
- Условие завершения сцены: {director_notes.get('exit_conditions', '')}
- Режим хода: {director_notes.get('action_mode', 'auto-resolve')}
""".strip()

    resolution_block = "нет"
    if resolution_notes:
        resolution_block = f"""
РЕЗОЛВ ДЕЙСТВИЯ:
- Профиль шаблона: {resolution_notes.get('resolution_profile', '')}
- Тип хода: {resolution_notes.get('action_kind', 'utility')}
- Риск: {resolution_notes.get('risk', 'medium')}
- Сложность: {resolution_notes.get('difficulty', 'standard')}
- Позиция: {resolution_notes.get('position', 'risky')}
- Ставка: {resolution_notes.get('stakes', '')}
- Исход: {resolution_notes.get('outcome', 'partial')}
- Цена: {resolution_notes.get('cost', '')}
- Жёсткая правда: {resolution_notes.get('hard_truth', '')}
- Последствие: {resolution_notes.get('suggested_consequence', '')}
- Механическая подсказка: {resolution_notes.get('mechanical_hint', '')}
- Рекомендуемые теги: {'; '.join(resolution_notes.get('mechanical_directives', [])) if resolution_notes.get('mechanical_directives') else 'нет'}
- Рекомендуемые теги знаний: {'; '.join(resolution_notes.get('knowledge_directives', [])) if resolution_notes.get('knowledge_directives') else 'нет'}
- Следующий вектор: {resolution_notes.get('follow_up', '')}
- Нужен ли выбор: {resolution_notes.get('should_offer_choice', False)}
""".strip()

    continuity_block = "нет"
    if continuity_notes:
        continuity_block = f"""
КОНТИНУИТИ:
- Сводка кампании: {continuity_notes.get('campaign_summary', '')}
- Открытые нити: {'; '.join(continuity_notes.get('open_loops', [])) if continuity_notes.get('open_loops') else 'нет'}
- Каноничные факты: {'; '.join(continuity_notes.get('canon_facts', [])) if continuity_notes.get('canon_facts') else 'нет'}
- Уже известные герою тайны: {'; '.join(continuity_notes.get('known_titles', [])) if continuity_notes.get('known_titles') else 'нет'}
- Ограничение знаний: {continuity_notes.get('knowledge_limit', '')}
- Запрет на дрейф: {continuity_notes.get('guardrail', '')}
""".strip()

    return f"""
{world_block}

{director_block}

{resolution_block}

{continuity_block}

СЦЕНАРИЙ И КАНОН:
{SCENARIO_TEXT[:9000]}

{character_block}

RAG-контекст:
{rag_block}

СООБЩЕНИЕ ИГРОКА:
{message_text}

Веди сцену как сильный Гейм Мастер. Сначала художественный ответ, потом при необходимости технические теги в самом конце.

Если в ходе сцены персонаж добыл важное новое знание, добавь в конце тег [ЗНАНИЕ: ...].
""".strip()


def build_choice_prompt(
    *,
    char_id: str,
    choice_text: str,
    world_state: dict,
    session_history: list[str],
    char_info: dict | None,
    personal_ctx: str,
    char_last_action: str,
    whispers: list[dict],
    vault_info: str,
    director_notes: dict | None = None,
    continuity_notes: dict | None = None,
) -> str:
    return build_game_master_prompt(
        char_id=char_id,
        message_text=f"Игрок выбрал вариант: {choice_text}",
        world_state=world_state,
        session_history=session_history,
        char_info=char_info,
        personal_ctx=personal_ctx,
        char_last_action=char_last_action,
        whispers=whispers,
        vault_info=vault_info,
        director_notes=director_notes,
        continuity_notes=continuity_notes,
    )


def build_memory_archiver_prompt(old_memory: str, events: list[str], butterfly_effect: str) -> str:
    return f"""
Старая память:
{old_memory or 'Пока пуста.'}

Новые события:
{' | '.join(events)}

Текущие бабочки:
{butterfly_effect or 'Пока нет.'}
""".strip()


def build_director_prompt(
    *,
    char_id: str,
    message_text: str,
    world_state: dict,
    session_history: list[str],
    char_info: dict | None,
    personal_ctx: str,
    char_last_action: str,
    vault_info: str,
) -> str:
    inventory = ", ".join(char_info.get("items", [])) if char_info and char_info.get("items") else "пусто"
    knowledge = (
        "; ".join(entry["title"] for entry in char_info.get("knowledge", []))
        if char_info and char_info.get("knowledge")
        else "нет"
    )
    return f"""
ТЕКУЩИЙ МИР:
- Акт: {world_state.get('current_act', '1')}
- Сцена: {world_state.get('current_scene', '')}
- Локация: {world_state.get('current_location', 'Неизвестно')}
- Угроза: {world_state.get('threat_level', '20')}%
- Очки Тьмы: {world_state.get('dark_points', '0')}
- Текущая цель сцены: {world_state.get('scene_goal', '')}
- Текущая фаза: {world_state.get('scene_phase', 'setup')}
- Главный вопрос сцены: {world_state.get('dramatic_question', '')}
- Счётчик давления: {world_state.get('pressure_clock', '0')}
- Надвигающееся событие: {world_state.get('pressure_event', '')}
- Последний режиссёрский бит: {world_state.get('director_last_beat', '')}
- Текущее напряжение: {world_state.get('director_tension', 'low')}
- Текущий фокус: {world_state.get('director_focus', 'roleplay')}

ПЕРСОНАЖ:
- ID: {char_id}
- Инвентарь: {inventory}
- Известные тайны: {knowledge}
- Личный контекст: {personal_ctx or 'нет'}
- Последнее действие: {char_last_action or 'нет'}

ПОСЛЕДНИЕ СОБЫТИЯ:
{' | '.join(session_history) if session_history else 'Сцена только начинается.'}

РЕЛЕВАНТНЫЙ ЛОР:
{vault_info[:1800] if vault_info else 'нет'}

СООБЩЕНИЕ ИГРОКА:
{message_text}

Верни режиссёрское решение в JSON.
""".strip()


def build_resolution_prompt(
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
) -> str:
    inventory = ", ".join(char_info.get("items", [])) if char_info and char_info.get("items") else "пусто"
    knowledge = (
        "; ".join(entry["title"] for entry in char_info.get("knowledge", []))
        if char_info and char_info.get("knowledge")
        else "нет"
    )
    director_summary = (
        f"Фаза={director_notes.get('scene_phase', 'setup')}; Напряжение={director_notes.get('tension', 'low')}; Бит={director_notes.get('beat', '')}; Последствие={director_notes.get('consequence_hint', '')}"
        if director_notes
        else "нет"
    )
    return f"""
СЦЕНА:
- Акт: {world_state.get('current_act', '1')}
- Сцена: {world_state.get('current_scene', '')}
- Локация: {world_state.get('current_location', 'Неизвестно')}
- Угроза: {world_state.get('threat_level', '20')}%
- Давление: {world_state.get('pressure_clock', '0')}
- Надвигается: {world_state.get('pressure_event', '')}

ПЕРСОНАЖ:
- ID: {char_id}
- Инвентарь: {inventory}
- Известные тайны: {knowledge}
- Личный контекст: {personal_ctx or 'нет'}
- Последнее действие: {char_last_action or 'нет'}

РЕЖИССУРА:
{director_summary}

ПОСЛЕДНИЕ СОБЫТИЯ:
{' | '.join(session_history[-6:]) if session_history else 'Событий пока мало.'}

ЛОР:
{vault_info[:1800] if vault_info else 'нет'}

ДЕЙСТВИЕ ИГРОКА:
{message_text}

Верни честный резолв в JSON.
""".strip()


def build_continuity_update_prompt(
    *,
    char_id: str,
    player_message: str,
    gm_response: str,
    world_state: dict,
    session_history: list[str],
) -> str:
    return f"""
ТЕКУЩАЯ СВОДКА КАМПАНИИ:
{world_state.get('campaign_summary', '') or world_state.get('long_term_memory', '') or 'Пока формируется.'}

ПАМЯТЬ СЦЕНЫ (слой S):
{world_state.get('scene_memory', '[]')}

ПАМЯТЬ СЕССИИ (слой M):
{world_state.get('session_memory', '[]')}

СВОДКА СЕССИИ (слой M):
{world_state.get('session_memory_summary', '') or 'нет'}

ТЕКУЩИЕ ОТКРЫТЫЕ НИТИ:
{world_state.get('campaign_open_loops', '[]')}

ТЕКУЩИЕ КАНОНИЧНЫЕ ФАКТЫ:
{world_state.get('campaign_canon_facts', '[]')}

СОСТОЯНИЕ МИРА:
- Акт: {world_state.get('current_act', '1')}
- Сцена: {world_state.get('current_scene', '')}
- Локация: {world_state.get('current_location', 'Неизвестно')}
- Последнее событие мира: {world_state.get('last_world_event', '')}

ПОСЛЕДНИЕ СОБЫТИЯ:
{' | '.join(session_history[-10:]) if session_history else 'Событий пока мало.'}

ХОД ПЕРСОНАЖА {char_id}:
Игрок: {player_message}
ГМ: {gm_response}

Обнови память кампании в JSON.
""".strip()
