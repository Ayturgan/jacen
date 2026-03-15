import logging

from aiogram import Bot, Dispatcher
from fastapi import FastAPI
from google import genai
from huggingface_hub import InferenceClient

from bot_core.config import SETTINGS


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_gemini_clients: dict[str, genai.Client] = {}


def _resolve_gemini_api_key(tier: str = "free") -> tuple[str, str]:
    normalized_tier = "paid" if tier == "paid" else "free"
    if normalized_tier == "paid":
        if SETTINGS.gemini_paid_key:
            return SETTINGS.gemini_paid_key, "paid"
        if SETTINGS.gemini_free_key:
            logger.warning("GEMINI_PAID_API_KEY не задан. Paid-тир временно откатывается на free-ключ.")
            return SETTINGS.gemini_free_key, "free"
    if SETTINGS.gemini_free_key:
        return SETTINGS.gemini_free_key, "free"
    if SETTINGS.gemini_key:
        return SETTINGS.gemini_key, "free"
    return "", "free"


def get_gemini_client(tier: str = "free") -> genai.Client:
    api_key, actual_tier = _resolve_gemini_api_key(tier)
    cache_key = f"{actual_tier}:{api_key[:12]}"
    if cache_key not in _gemini_clients:
        _gemini_clients[cache_key] = genai.Client(api_key=api_key)
    return _gemini_clients[cache_key]


client = get_gemini_client("free")
hf_client = (
    InferenceClient(token=SETTINGS.hf_token)
    if SETTINGS.hf_token and SETTINGS.hf_token != "YOUR_HF_TOKEN_HERE"
    else None
)
bot = Bot(token=SETTINGS.bot_token)
dp = Dispatcher()
app = FastAPI()
pending_responses: dict[int, dict] = {}
