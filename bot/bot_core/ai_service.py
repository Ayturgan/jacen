import os
import random
import re

import google.genai.types as genai_types
import httpx

import database
from bot_core.config import BASE_DIR, PROJECT_ROOT, SETTINGS
from bot_core.runtime import get_gemini_client, hf_client, logger


IMAGE_MODEL_CANDIDATES = [
    "imagen-4.0-generate-001",
    "imagen-3.0-generate-002",
    "imagen-3.0-generate-001",
]
_working_image_model: str | None = None
_image_generation_disabled = False


def _normalize_tier(value: str | None) -> str:
    tier = (value or "free").lower()
    return tier if tier in {"free", "paid"} else "free"


def _default_model_for_tier(tier: str) -> str:
    if tier == "paid":
        return SETTINGS.gemini_paid_model or "gemini-3.1-flash-lite-preview"
    return SETTINGS.gemini_free_model or "gemini-2.5-flash-lite"


def _resolve_effective_model(model: str, world_state: dict | None) -> str:
    tier = _normalize_tier((world_state or {}).get("llm_tier", SETTINGS.default_llm_tier))
    if tier == "paid" and not model.startswith("gemini"):
        forced_model = _default_model_for_tier("paid")
        logger.info(f"LLM tier is paid: forcing Gemini model '{forced_model}' instead of '{model}'.")
        return forced_model
    return model


def _is_not_found_model_error(error: Exception) -> bool:
    message = str(error).lower()
    return "not_found" in message or "is not found" in message or "not supported" in message


async def _fallback_gemini(user_prompt: str, system_prompt: str | None = None, temperature: float = 0.7) -> str:
    client = get_gemini_client("free")
    config = genai_types.GenerateContentConfig(temperature=temperature)
    if system_prompt:
        config.system_instruction = system_prompt
    response = client.models.generate_content(
        model=SETTINGS.gemini_free_model or "gemini-2.5-flash-lite",
        contents=user_prompt,
        config=config,
    )
    return (response.text or "").strip()


async def generate_text(
    user_prompt: str,
    *,
    model: str | None = None,
    system_prompt: str | None = None,
    temperature: float = 0.7,
) -> str:
    world_state: dict | None = None
    if model is None:
        world_state = await database.get_all_world_states()
        tier = _normalize_tier(world_state.get("llm_tier", SETTINGS.default_llm_tier))
        model = world_state.get("gemini_model", _default_model_for_tier(tier))

    if world_state is None:
        world_state = await database.get_all_world_states()

    model = _resolve_effective_model(model, world_state)
    llm_tier = _normalize_tier(world_state.get("llm_tier", SETTINGS.default_llm_tier))
    gemini_client = get_gemini_client(llm_tier)

    if model.startswith("gemini"):
        config = genai_types.GenerateContentConfig(temperature=temperature)
        if system_prompt:
            config.system_instruction = system_prompt
        response = gemini_client.models.generate_content(model=model, contents=user_prompt, config=config)
        return (response.text or "").strip()

    if model.startswith("grq:"):
        groq_model_name = model[4:]
        groq_system_prompt = system_prompt or "Ты — полезный ассистент."
        try:
            async with httpx.AsyncClient(timeout=30.0) as httpx_client:
                response = await httpx_client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {SETTINGS.groq_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": groq_model_name,
                        "messages": [
                            {"role": "system", "content": groq_system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": temperature,
                    },
                )
                response.raise_for_status()
                data = response.json()
                answer = data["choices"][0]["message"]["content"]
                return re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
        except Exception as error:
            logger.error(f"Groq ошибка ({groq_model_name}): {error}. Fallback на Gemini.")
            return await _fallback_gemini(user_prompt, system_prompt=system_prompt, temperature=temperature)

    if model.startswith("ollama/"):
        ollama_model_name = model[7:]
        composed_prompt = f"{system_prompt}\n\n{user_prompt}".strip() if system_prompt else user_prompt
        try:
            async with httpx.AsyncClient(timeout=300.0) as httpx_client:
                response = await httpx_client.post(
                    f"{SETTINGS.ollama_url}/api/generate",
                    json={
                        "model": ollama_model_name,
                        "prompt": composed_prompt,
                        "stream": False,
                        "options": {"temperature": temperature},
                    },
                )
                response.raise_for_status()
                data = response.json()
                answer = data.get("response", "")
                return re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
        except Exception as error:
            logger.error(f"Ollama ошибка ({ollama_model_name}) [{type(error).__name__}]: {error}. Fallback на Gemini.")
            try:
                return await _fallback_gemini(user_prompt, system_prompt=system_prompt, temperature=temperature)
            except Exception as fallback_error:
                logger.error(f"Fallback Gemini тоже провалился: {fallback_error}")
                return "Голоса в голове Смертоликого затихли... (Ошибка AI)"

    if not hf_client:
        logger.warning("HF_TOKEN не задан, fallback на Gemini")
        return await _fallback_gemini(user_prompt, system_prompt=system_prompt, temperature=temperature)

    try:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})
        result = hf_client.chat_completion(
            model=model,
            messages=messages,
            max_tokens=2048,
            temperature=temperature,
        )
        answer = result.choices[0].message.content or ""
        return re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
    except Exception as error:
        logger.error(f"HF ошибка ({model}): {error}. Fallback на Gemini.")
        return await _fallback_gemini(user_prompt, system_prompt=system_prompt, temperature=temperature)


async def find_location_image(text: str):
    search_dirs = [os.path.join(PROJECT_ROOT, "00_Сюжет"), os.path.join(PROJECT_ROOT, "03_Мир")]
    words = re.findall(r"\w+", text.lower())
    for directory in search_dirs:
        if os.path.exists(directory):
            for root, _, files in os.walk(directory):
                for file_name in files:
                    if file_name.lower().endswith((".jpg", ".png", ".jpeg", ".webp")):
                        if any(word in file_name.lower() for word in words if len(word) > 4):
                            return os.path.join(root, file_name)
    return None


async def generate_location_image(prompt: str):
    global _working_image_model, _image_generation_disabled

    if _image_generation_disabled:
        return None

    try:
        world_state = await database.get_all_world_states()
        llm_tier = _normalize_tier(world_state.get("llm_tier", SETTINGS.default_llm_tier))
        gemini_client = get_gemini_client(llm_tier)

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=(
                "Convert this fantasy scene into a short descriptive english prompt for image generation. "
                "Focus on environment, atmosphere, and dark fantasy style. Return ONLY the english prompt text: "
                f"{prompt}"
            ),
        )
        english_prompt = (response.text or "").strip()
        if not english_prompt:
            return None

        ordered_models = []
        if _working_image_model:
            ordered_models.append(_working_image_model)
        ordered_models.extend(model for model in IMAGE_MODEL_CANDIDATES if model not in ordered_models)

        last_non_notfound_error: Exception | None = None
        for image_model in ordered_models:
            try:
                image_response = gemini_client.models.generate_images(
                    model=image_model,
                    prompt=english_prompt,
                    config=genai_types.GenerateImagesConfig(
                        number_of_images=1,
                        output_mime_type="image/jpeg",
                        aspect_ratio="1:1",
                    ),
                )
                for generated_image in image_response.generated_images:
                    path = os.path.join(BASE_DIR, "static", f"gen_img_{random.randint(1000, 99999)}.jpg")
                    if hasattr(generated_image.image, "image_bytes"):
                        with open(path, "wb") as file:
                            file.write(generated_image.image.image_bytes)
                    elif hasattr(generated_image.image, "save"):
                        generated_image.image.save(path)
                    else:
                        with open(path, "wb") as file:
                            file.write(generated_image.image)
                    _working_image_model = image_model
                    return path
            except Exception as error:
                if _is_not_found_model_error(error):
                    continue
                last_non_notfound_error = error

        if last_non_notfound_error:
            logger.warning(f"Image generation temporarily unavailable: {last_non_notfound_error}")
        else:
            logger.warning("Image generation disabled: no supported Imagen model/method available for this API setup.")
            _image_generation_disabled = True
    except Exception as error:
        logger.warning(f"Image prompt preparation failed: {error}")
    return None
