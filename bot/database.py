import aiosqlite
import os

from bot_core.config import SETTINGS
from bot_core.state_contract import normalize_world_state

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "characters.db")

STARTING_ITEMS = {
    "Elix": [
        "Обсидиановый кулон-печать",
    ],
    "Silas": [
        "Клинок ордена Инквизиторов",
    ],
    "Varo": [
        "Браавосская рапира",
        "Набор отмычек",
        "Отравленные иглы",
    ],
    "Lysandra": [
        "Эфирный хронометр",
        "Полевой алхимический набор",
    ],
}


def get_default_llm_tier() -> str:
    tier = (SETTINGS.default_llm_tier or "free").lower()
    return tier if tier in {"free", "paid"} else "free"


def get_default_gemini_model(tier: str) -> str:
    if tier == "paid":
        return SETTINGS.gemini_paid_model or "gemini-3.1-flash-lite-preview"
    return SETTINGS.gemini_free_model or "gemini-2.5-flash-lite"


async def ensure_starting_items():
    async with aiosqlite.connect(DB_PATH) as db:
        for char_id, items in STARTING_ITEMS.items():
            for item_name in items:
                cursor = await db.execute(
                    "SELECT 1 FROM items WHERE char_id = ? AND name = ? LIMIT 1",
                    (char_id, item_name),
                )
                if await cursor.fetchone():
                    continue
                await db.execute("INSERT INTO items (char_id, name) VALUES (?, ?)", (char_id, item_name))
        await db.commit()

async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    default_tier = get_default_llm_tier()
    default_model = get_default_gemini_model(default_tier)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS characters (
            id TEXT PRIMARY KEY, name TEXT, hp INTEGER, max_hp INTEGER, 
            stress INTEGER, status TEXT, tg_id INTEGER DEFAULT 0, avatar_url TEXT DEFAULT '')''')
        
        try: await db.execute("ALTER TABLE characters ADD COLUMN tg_id INTEGER DEFAULT 0")
        except: pass
        try: await db.execute("ALTER TABLE characters ADD COLUMN avatar_url TEXT DEFAULT ''")
        except: pass
            
        await db.execute('''CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, char_id TEXT, 
            name TEXT, description TEXT)''')
            
        await db.execute('''CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT, char_id TEXT, 
            title TEXT, content TEXT)''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY, title TEXT, status TEXT DEFAULT 'active')''')
        
        await db.execute('''CREATE TABLE IF NOT EXISTS game_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            event_type TEXT,
            description TEXT
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS world_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS whispers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            char_id TEXT,
            text TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS char_memory (
            char_id TEXT PRIMARY KEY,
            personal_context TEXT DEFAULT '',
            last_location TEXT DEFAULT '',
            last_action TEXT DEFAULT '',
            turns_in_spotlight INTEGER DEFAULT 0
        )''')
        
        cursor = await db.execute("SELECT count(*) FROM characters")
        if (await cursor.fetchone())[0] == 0:
            await reset_game_state()
        
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('llm_tier', ?)", (default_tier,))
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('gemini_model', ?)", (default_model,))
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('current_location', 'Волантис')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('threat_level', '20')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('dark_points', '0')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('observability_enabled', '0')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('long_term_memory', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('active_spotlight', 'ALL')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('spotlight_max_turns', '3')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('bot_mode', 'normal')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('quest_started', '0')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('gm_action_mode', 'auto')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('quest_paused', '0')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('quest_pause_reason', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('quest_pause_summary', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('quest_paused_at', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('active_group_chat_id', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('scene_goal', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('scene_phase', 'setup')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('dramatic_question', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('pressure_clock', '0')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('pressure_event', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('reveal_queue', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('npc_agenda', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('scene_exit_conditions', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('director_last_beat', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('director_tension', 'low')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('director_focus', 'exploration')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('world_turn_counter', '0')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('faction_states', '{}')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('npc_states', '{}')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('world_clocks', '{}')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('last_world_event', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('campaign_summary', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('campaign_open_loops', '[]')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('campaign_canon_facts', '[]')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('continuity_last_updated', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('pending_roll_char', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('pending_roll_reason', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('pending_roll_chat_id', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('last_dice_roll', '')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('director_should_end_scene', '0')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('act_auto_progress', '1')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('act_min_world_turns', '26')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('act_min_hours', '8')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('campaign_target_act', '5')")
        await db.execute("INSERT OR IGNORE INTO world_state (key, value) VALUES ('act_started_at', '')")
        
        # Инициализация памяти для каждого персонажа
        for cid in ['Elix', 'Silas', 'Varo', 'Lysandra']:
            await db.execute("INSERT OR IGNORE INTO char_memory (char_id) VALUES (?)", (cid,))
        
        await db.commit()
    await ensure_starting_items()
    await ensure_state_contract()

async def reset_game_state():
    default_tier = get_default_llm_tier()
    default_model = get_default_gemini_model(default_tier)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM game_log")
        await db.execute("DELETE FROM world_state")
        await db.execute("DELETE FROM items")
        await db.execute("DELETE FROM knowledge")
        chars = [
            ("Elix", "Эликс Веллар", 100, 100, 0, "Спокоен", "/static/elix.jpg"),
            ("Silas", "Сайлас", 120, 120, 10, "Бдителен", "/static/silas.jpg"),
            ("Varo", "Варо Антарион", 80, 80, 0, "Скрытен", "/static/varo.jpg"),
            ("Lysandra", "Лисандра", 70, 70, 5, "Сосредоточена", "/static/lysandra.jpg")
        ]
        for cid, name, hp, mhp, str, st, av in chars:
            await db.execute('''
                INSERT INTO characters (id, name, hp, max_hp, stress, status, avatar_url) 
                VALUES (?,?,?,?,?,?,?) 
                ON CONFLICT(id) DO UPDATE SET hp=excluded.hp, max_hp=excluded.max_hp, stress=excluded.stress, status=excluded.status, avatar_url=excluded.avatar_url, name=excluded.name
            ''', (cid, name, hp, mhp, str, st, av))
        
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('global_threat', '0')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('current_act', '1')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('llm_tier', ?)", (default_tier,))
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('gemini_model', ?)", (default_model,))
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('current_location', 'Волантис')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('threat_level', '20')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('dark_points', '0')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('observability_enabled', '0')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('long_term_memory', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('active_spotlight', 'ALL')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('spotlight_max_turns', '3')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('bot_mode', 'normal')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('quest_started', '0')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('gm_action_mode', 'auto')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('quest_paused', '0')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('quest_pause_reason', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('quest_pause_summary', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('quest_paused_at', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('active_group_chat_id', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('scene_goal', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('scene_phase', 'setup')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('dramatic_question', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('pressure_clock', '0')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('pressure_event', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('reveal_queue', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('npc_agenda', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('scene_exit_conditions', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('director_last_beat', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('director_tension', 'low')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('director_focus', 'exploration')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('world_turn_counter', '0')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('faction_states', '{}')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('npc_states', '{}')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('world_clocks', '{}')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('last_world_event', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('campaign_summary', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('campaign_open_loops', '[]')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('campaign_canon_facts', '[]')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('continuity_last_updated', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('pending_roll_char', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('pending_roll_reason', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('pending_roll_chat_id', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('last_dice_roll', '')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('director_should_end_scene', '0')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('act_auto_progress', '1')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('act_min_world_turns', '26')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('act_min_hours', '8')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('campaign_target_act', '5')")
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES ('act_started_at', '')")
        await db.execute("DELETE FROM char_memory")
        for cid in ['Elix', 'Silas', 'Varo', 'Lysandra']:
            await db.execute("INSERT OR IGNORE INTO char_memory (char_id) VALUES (?)", (cid,))
        await db.commit()
    await ensure_starting_items()
    await ensure_state_contract()


async def ensure_state_contract():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT key, value FROM world_state")
        raw_state = {row[0]: row[1] for row in await cursor.fetchall()}
        normalized = normalize_world_state(raw_state)

        for key, value in normalized.items():
            if raw_state.get(key) != value:
                await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES (?, ?)", (key, value))

        await db.commit()

async def update_name(char_id: str, new_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE characters SET name = ? WHERE id = ?", (new_name, char_id))
        await db.commit()

async def get_world_state(key: str, default: str = ""):
    async with aiosqlite.connect(DB_PATH) as db:
        c = await db.execute("SELECT value FROM world_state WHERE key = ?", (key,))
        row = await c.fetchone()
        return row[0] if row else default

async def set_world_state(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO world_state (key, value) VALUES (?, ?)", (key, value))
        await db.commit()

async def get_all_world_states():
    async with aiosqlite.connect(DB_PATH) as db:
        c = await db.execute("SELECT key, value FROM world_state")
        return {row[0]: row[1] for row in await c.fetchall()}

async def add_game_event(event_type: str, description: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO game_log (event_type, description) VALUES (?, ?)", (event_type, description))
        await db.commit()

async def get_recent_events(limit: int = 15):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT description FROM game_log ORDER BY id DESC LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        events = [r['description'] for r in rows]
        events.reverse()
        return events


async def get_recent_key_events(limit: int = 25):
    key_types = ["rename", "stat_change", "item_add", "item_remove", "knowledge", "act_auto", "act_change"]
    placeholders = ",".join("?" for _ in key_types)
    query = (
        f"SELECT timestamp, event_type, description "
        f"FROM game_log WHERE event_type IN ({placeholders}) "
        f"ORDER BY id DESC LIMIT ?"
    )

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(query, (*key_types, limit))
        rows = await cursor.fetchall()
        events = [dict(r) for r in rows]
        events.reverse()
        return events

async def get_character(char_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM characters WHERE id = ?", (char_id,))
        row = await c.fetchone()
        if not row: return None
        char = dict(row)
        items = await db.execute("SELECT name FROM items WHERE char_id = ?", (char_id,))
        char["items"] = [r[0] for r in await items.fetchall()]
        knowledge = await db.execute("SELECT title, content FROM knowledge WHERE char_id = ?", (char_id,))
        char["knowledge"] = [dict(k) for k in await knowledge.fetchall()]
        return char

async def get_all_characters():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM characters")
        rows = await c.fetchall()
        chars = []
        for r in rows:
            char = dict(r)
            items = await db.execute("SELECT name FROM items WHERE char_id = ?", (char["id"],))
            char["items"] = [i[0] for i in await items.fetchall()]
            knowledge = await db.execute("SELECT title, content FROM knowledge WHERE char_id = ?", (char["id"],))
            char["knowledge"] = [dict(k) for k in await knowledge.fetchall()]
            chars.append(char)
        return chars

async def update_player_id(char_id: str, tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE characters SET tg_id = ? WHERE id = ?", (tg_id, char_id))
        await db.commit()

async def get_groups():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM groups")
        return [dict(r) for r in await c.fetchall()]

async def upsert_group(chat_id: int, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO groups (id, title, status) VALUES (?, ?, 'OK')", (chat_id, title))
        await db.commit()

async def add_item(char_id: str, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        existing = await db.execute(
            "SELECT 1 FROM items WHERE char_id = ? AND name = ? LIMIT 1",
            (char_id, name),
        )
        if await existing.fetchone():
            return False
        await db.execute("INSERT INTO items (char_id, name) VALUES (?, ?)", (char_id, name))
        await db.commit()
        return True

async def remove_item(char_id: str, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM items WHERE char_id = ? AND name = ?", (char_id, name))
        await db.commit()

async def add_knowledge(char_id: str, title: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        existing = await db.execute(
            "SELECT 1 FROM knowledge WHERE char_id = ? AND title = ? LIMIT 1",
            (char_id, title),
        )
        if await existing.fetchone():
            return False

        await db.execute("INSERT INTO knowledge (char_id, title, content) VALUES (?, ?, ?)", (char_id, title, content))
        await db.commit()
        return True

async def update_stat(char_id: str, stat: str, value: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE characters SET {stat} = ? WHERE id = ?", (value, char_id))
        await db.commit()

async def save_whisper(char_id: str, text: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO whispers (char_id, text) VALUES (?, ?)", (char_id, text))
        await db.commit()

async def get_whispers(char_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT text, timestamp FROM whispers WHERE char_id = ? ORDER BY id DESC", (char_id,))
        return [dict(r) for r in await c.fetchall()]

async def get_char_memory(char_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM char_memory WHERE char_id = ?", (char_id,))
        row = await c.fetchone()
        return dict(row) if row else {"char_id": char_id, "personal_context": "", "last_location": "", "last_action": "", "turns_in_spotlight": 0}

async def update_char_memory(char_id: str, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        for key, val in kwargs.items():
            await db.execute(f"UPDATE char_memory SET {key} = ? WHERE char_id = ?", (val, char_id))
        await db.commit()

async def increment_spotlight_turns(char_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE char_memory SET turns_in_spotlight = turns_in_spotlight + 1 WHERE char_id = ?", (char_id,))
        await db.commit()
        c = await db.execute("SELECT turns_in_spotlight FROM char_memory WHERE char_id = ?", (char_id,))
        row = await c.fetchone()
        return row[0] if row else 0

async def reset_spotlight_turns(char_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE char_memory SET turns_in_spotlight = 0 WHERE char_id = ?", (char_id,))
        await db.commit()

async def get_all_char_memories():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        c = await db.execute("SELECT * FROM char_memory")
        return [dict(r) for r in await c.fetchall()]
