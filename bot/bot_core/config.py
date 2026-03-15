import os
from dataclasses import dataclass

from dotenv import load_dotenv


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
load_dotenv(dotenv_path=os.path.join(BASE_DIR, ".env"))


SCENARIO_FILES = [
    "00_Сюжет/Сюжетный канон.md",
    "00_Сюжет/Полный сценарий.md",
]


def get_env_safe(key: str, default: str = "") -> str:
    value = os.getenv(key, default)
    return "".join(value.split()).replace('"', "").replace("'", "") if value else default


def load_scenario() -> str:
    text_parts: list[str] = []
    for relative_path in SCENARIO_FILES:
        path = os.path.join(PROJECT_ROOT, relative_path.replace("/", os.sep))
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as file:
                text_parts.append(file.read())
    return "\n\n".join(text_parts)


@dataclass(frozen=True)
class Settings:
    bot_token: str
    gemini_key: str
    gemini_free_key: str
    gemini_paid_key: str
    admin_id: int
    webapp_url: str
    hf_token: str
    hf_model: str
    ollama_url: str
    ollama_model: str
    groq_key: str
    default_llm_tier: str
    gemini_free_model: str
    gemini_paid_model: str

    @classmethod
    def load(cls) -> "Settings":
        legacy_gemini_key = get_env_safe("GEMINI_API_KEY")
        gemini_free_key = get_env_safe("GEMINI_FREE_API_KEY", legacy_gemini_key)
        gemini_paid_key = get_env_safe("GEMINI_PAID_API_KEY")
        return cls(
            bot_token=get_env_safe("TELEGRAM_BOT_TOKEN"),
            gemini_key=legacy_gemini_key,
            gemini_free_key=gemini_free_key,
            gemini_paid_key=gemini_paid_key,
            admin_id=int(get_env_safe("ADMIN_ID", "0")),
            webapp_url=get_env_safe("WEBAPP_URL", "http://localhost:8000"),
            hf_token=os.getenv("HF_TOKEN", ""),
            hf_model=os.getenv("HF_MODEL", "google/gemma-3-12b-it"),
            ollama_url=get_env_safe("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=get_env_safe("OLLAMA_MODEL", ""),
            groq_key=get_env_safe("GROQ_API_KEY"),
            default_llm_tier=get_env_safe("LLM_TIER", "free").lower(),
            gemini_free_model=get_env_safe("GEMINI_FREE_MODEL", "gemini-2.5-flash-lite"),
            gemini_paid_model=get_env_safe("GEMINI_PAID_MODEL", "gemini-3.1-flash-lite-preview"),
        )


SETTINGS = Settings.load()
SCENARIO_TEXT = load_scenario()
PLAYER_ORDER = ["Elix", "Silas", "Varo", "Lysandra"]
DICE_PATTERNS = [
    "брось кубик",
    "кинь кубик",
    "бросок",
    "кинь d20",
    "roll d20",
    "брось кости",
    "кости",
]
ACTION_PATTERNS = [
    r"\bатак",
    r"\bбью\b",
    r"\bудар",
    r"\bстреля",
    r"\bкрад",
    r"\bпряч",
    r"\bисслед",
    r"\bосматри",
    r"\bищу\b",
    r"\bвзламы",
    r"\bубежда",
    r"\bугрожа",
    r"\bкаст",
    r"\bколд",
    r"\bиспользую",
    r"\bпытаюсь",
    r"\bделаю",
    r"\bиду\b",
    r"\bоткрываю",
]
