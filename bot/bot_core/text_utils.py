import re

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot_core.runtime import bot


MAX_TELEGRAM_TEXT = 4000


def clean_ai_markdown(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    text = re.sub(r"\*{3,}", "", text)
    text = re.sub(r"\*\*\s*\*\*", "", text)
    text = re.sub(r"\*\s*\*", "", text)
    text = re.sub(r"^\*\*\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_telegram_text(text: str, limit: int = MAX_TELEGRAM_TEXT) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 10] + "..."


def parse_buttons(text: str):
    button_match = re.search(r"\[КНОПКИ:\s*(.*?)\]", text, flags=re.DOTALL)
    if not button_match:
        return text, None

    raw_options = button_match.group(1)
    options = raw_options.split("|") if "|" in raw_options else raw_options.split("\n")
    keyboard = []
    for option in options:
        option = re.sub(r"^\s*\d+\.\s*", "", option).strip()
        if option:
            keyboard.append([InlineKeyboardButton(text=option, callback_data=f"choice_{option[:20]}")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
    clean_text = text.replace(button_match.group(0), "").strip()
    return clean_text, markup


async def safe_reply(message, text: str, reply_markup=None):
    text = truncate_telegram_text(clean_ai_markdown(text))
    try:
        return await message.reply(text, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception:
        plain = re.sub(r"[*_`]", "", text)
        return await message.reply(plain[:MAX_TELEGRAM_TEXT], reply_markup=reply_markup)


async def safe_send(chat_id: int, text: str, reply_markup=None):
    text = truncate_telegram_text(clean_ai_markdown(text))
    try:
        return await bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=reply_markup)
    except Exception:
        plain = re.sub(r"[*_`]", "", text)
        return await bot.send_message(chat_id, plain[:MAX_TELEGRAM_TEXT], reply_markup=reply_markup)
