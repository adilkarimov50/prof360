"""Клиент LLM с поддержкой провайдеров: локальный Ollama или внешний Google Gemini.

ВАЖНО: при использовании внешнего провайдера (Gemini) персональные данные должны
быть предварительно токенизированы (см. app.ai.guard.tokenize_pii). Сам клиент
данные не обезличивает — это ответственность вызывающего кода.

Multimodal-вызовы (extract_text_multimodal, analyze_multimodal) отправляют
оригинальный файл во внешний Gemini без локального обезличивания.
"""
import base64
import json
import re
from collections.abc import Iterator

import httpx

from app.core.config import settings


def provider() -> str:
    return (settings.ai_provider or "ollama").lower()


def is_available() -> bool:
    """Доступен ли активный провайдер генерации."""
    p = provider()
    if p == "gemini":
        return bool(settings.gemini_api_key)
    # ollama
    if not settings.ollama_enabled:
        return False
    try:
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def info() -> dict:
    """Сведения об активном провайдере для UI/диагностики."""
    p = provider()
    return {
        "provider": p,
        "model": settings.gemini_model if p == "gemini" else settings.ollama_model,
        "available": is_available(),
    }


def _max_tokens(max_tokens: int | None) -> int:
    return max_tokens or settings.ai_max_output_tokens


def _generate_ollama(prompt: str, system: str | None, temperature: float,
                     max_tokens: int | None) -> str | None:
    if not settings.ollama_enabled:
        return None
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": _max_tokens(max_tokens)},
    }
    if system:
        payload["system"] = system
    try:
        r = httpx.post(f"{settings.ollama_base_url}/api/generate", json=payload, timeout=180.0)
        r.raise_for_status()
        return r.json().get("response", "").strip()
    except Exception:
        return None


def _gemini_contents(prompt: str, history: list[dict] | None) -> list[dict]:
    """Собирает поле contents для Gemini из истории (role/content) и текущего запроса."""
    contents: list[dict] = []
    for turn in history or []:
        role = "model" if turn.get("role") in ("assistant", "model") else "user"
        text = (turn.get("content") or "").strip()
        if text:
            contents.append({"role": role, "parts": [{"text": text}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})
    return contents


def _generate_gemini(prompt: str, system: str | None, temperature: float,
                     max_tokens: int | None, history: list[dict] | None = None) -> str | None:
    if not settings.gemini_api_key:
        return None
    url = (f"{settings.gemini_base_url}/models/{settings.gemini_model}:generateContent"
           f"?key={settings.gemini_api_key}")
    body: dict = {
        "contents": _gemini_contents(prompt, history),
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": _max_tokens(max_tokens),
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    try:
        r = httpx.post(url, json=body, timeout=180.0)
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts).strip()
        return text or None
    except Exception:
        return None


def generate(prompt: str, system: str | None = None, temperature: float = 0.2,
             max_tokens: int | None = None) -> str | None:
    """Генерация текста активным провайдером. None при недоступности.

    Внешний провайдер используется только если ai_allow_external=True.
    """
    p = provider()
    if p == "gemini":
        if not settings.ai_allow_external:
            return None
        return _generate_gemini(prompt, system, temperature, max_tokens)
    return _generate_ollama(prompt, system, temperature, max_tokens)


def generate_chat(prompt: str, *, system: str | None = None, history: list[dict] | None = None,
                  temperature: float = 0.4, max_tokens: int | None = None) -> str | None:
    """Многоходовая генерация с историей диалога (для ИИ-консультанта «как GPT»).

    history — список реплик вида {"role": "user"|"assistant", "content": "..."}.
    Внешний провайдер используется только если ai_allow_external=True.
    """
    p = provider()
    if p == "gemini":
        if not settings.ai_allow_external:
            return None
        return _generate_gemini(prompt, system, temperature, max_tokens, history)
    # Ollama: историю сворачиваем в текст промпта
    if history:
        convo = "\n".join(
            f"{'Пользователь' if t.get('role') != 'assistant' else 'Консультант'}: {t.get('content','')}"
            for t in history if t.get("content")
        )
        prompt = f"Предыдущий диалог:\n{convo}\n\nТекущий вопрос: {prompt}"
    return _generate_ollama(prompt, system, temperature, max_tokens)


def _stream_gemini(prompt: str, system: str | None, temperature: float,
                   max_tokens: int | None, history: list[dict] | None) -> Iterator[str]:
    if not settings.gemini_api_key:
        return
    url = (f"{settings.gemini_base_url}/models/{settings.gemini_model}:streamGenerateContent"
           f"?alt=sse&key={settings.gemini_api_key}")
    body: dict = {
        "contents": _gemini_contents(prompt, history),
        "generationConfig": {"temperature": temperature, "maxOutputTokens": _max_tokens(max_tokens)},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    with httpx.stream("POST", url, json=body, timeout=180.0) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line or not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if not payload or payload == "[DONE]":
                continue
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            candidates = data.get("candidates") or []
            if not candidates:
                continue
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            if text:
                yield text


def _stream_ollama(prompt: str, system: str | None, temperature: float,
                   max_tokens: int | None) -> Iterator[str]:
    if not settings.ollama_enabled:
        return
    payload: dict = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": True,
        "options": {"temperature": temperature, "num_predict": _max_tokens(max_tokens)},
    }
    if system:
        payload["system"] = system
    with httpx.stream("POST", f"{settings.ollama_base_url}/api/generate",
                      json=payload, timeout=180.0) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            chunk = data.get("response", "")
            if chunk:
                yield chunk


def stream_chat(prompt: str, *, system: str | None = None, history: list[dict] | None = None,
                temperature: float = 0.45, max_tokens: int | None = None) -> Iterator[str]:
    """Потоковая генерация (дельты текста). При ошибке/недоступности — фолбэк одним куском.

    Внешний провайдер используется только если ai_allow_external=True.
    """
    p = provider()
    try:
        if p == "gemini":
            if not settings.ai_allow_external:
                return
            got = False
            for chunk in _stream_gemini(prompt, system, temperature, max_tokens, history):
                got = True
                yield chunk
            if got:
                return
            # стрим ничего не дал — пробуем обычную генерацию
            full = _generate_gemini(prompt, system, temperature, max_tokens, history)
            if full:
                yield full
            return
        # ollama
        got = False
        if history:
            convo = "\n".join(
                f"{'Пользователь' if t.get('role') != 'assistant' else 'Консультант'}: {t.get('content','')}"
                for t in history if t.get("content")
            )
            prompt = f"Предыдущий диалог:\n{convo}\n\nТекущий вопрос: {prompt}"
        for chunk in _stream_ollama(prompt, system, temperature, max_tokens):
            got = True
            yield chunk
        if not got:
            full = _generate_ollama(prompt, system, temperature, max_tokens)
            if full:
                yield full
    except Exception:
        # сетевой/прочий сбой во время стрима — отдаём, что есть, через обычный вызов
        full = generate(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
        if full:
            yield full


def generate_with_tools(
    prompt: str,
    *,
    tools: list[dict],
    system: str | None = None,
    history: list[dict] | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> dict | None:
    """Function-calling через Gemini. Возвращает {text} или {name, args} для вызова инструмента."""
    p = provider()
    if p != "gemini" or not settings.gemini_api_key or not settings.ai_allow_external:
        return None
    url = (f"{settings.gemini_base_url}/models/{settings.gemini_model}:generateContent"
           f"?key={settings.gemini_api_key}")
    declarations = [{"functionDeclarations": tools}]
    body: dict = {
        "contents": _gemini_contents(prompt, history),
        "tools": declarations,
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": _max_tokens(max_tokens),
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    try:
        r = httpx.post(url, json=body, timeout=180.0)
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            fc = part.get("functionCall")
            if fc:
                args = fc.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                return {"name": fc.get("name"), "args": args}
        text = "".join(p.get("text", "") for p in parts).strip()
        return {"text": text} if text else None
    except Exception:
        return None


MULTIMODAL_MIMES = frozenset({
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/jpg",
})


def _gemini_multimodal_generate(
    *,
    prompt: str,
    file_bytes: bytes | None = None,
    mime_type: str | None = None,
    system: str | None = None,
    temperature: float = 0.15,
    max_tokens: int | None = None,
) -> str | None:
    """Gemini generateContent с опциональным inline_data (PDF/изображение)."""
    if not settings.gemini_api_key or not settings.ai_allow_external:
        return None
    parts: list[dict] = []
    if file_bytes and mime_type:
        mt = "image/jpeg" if mime_type == "image/jpg" else mime_type
        parts.append({
            "inline_data": {
                "mime_type": mt,
                "data": base64.b64encode(file_bytes).decode("ascii"),
            },
        })
    parts.append({"text": prompt})
    url = (f"{settings.gemini_base_url}/models/{settings.gemini_model}:generateContent"
           f"?key={settings.gemini_api_key}")
    body: dict = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": _max_tokens(max_tokens),
        },
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    try:
        r = httpx.post(url, json=body, timeout=300.0)
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        resp_parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in resp_parts).strip()
        return text or None
    except Exception:
        return None


def extract_text_multimodal(file_bytes: bytes, mime_type: str) -> str | None:
    """OCR/извлечение текста из PDF или изображения через Gemini multimodal."""
    if provider() != "gemini":
        return None
    mt = mime_type.lower()
    if mt not in MULTIMODAL_MIMES:
        return None
    system = (
        "Ты специалист по распознаванию официальных документов на русском и казахском языках. "
        "Извлекай весь текст документа максимально полно, сохраняя структуру (заголовки, пункты, таблицы). "
        "Не добавляй комментариев — только распознанный текст."
    )
    prompt = (
        "Распознай и верни полный текст этого документа. "
        "Если текст на казахском — сохрани оригинал. Для смешанных документов сохрани оба языка."
    )
    return _gemini_multimodal_generate(
        prompt=prompt,
        file_bytes=file_bytes,
        mime_type=mt,
        system=system,
        temperature=0.1,
        max_tokens=8192,
    )


def analyze_multimodal(
    prompt: str,
    *,
    file_bytes: bytes | None = None,
    mime_type: str | None = None,
    system: str | None = None,
    temperature: float = 0.15,
    max_tokens: int | None = None,
) -> str | None:
    """Структурированный анализ: текст + опционально оригинал документа."""
    if provider() != "gemini":
        return generate(prompt, system=system, temperature=temperature, max_tokens=max_tokens)
    return _gemini_multimodal_generate(
        prompt=prompt,
        file_bytes=file_bytes,
        mime_type=mime_type,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens or 4096,
    )


def parse_json_from_llm(text: str | None) -> dict | None:
    """Извлекает JSON-объект из ответа LLM (в т.ч. из ```json блоков)."""
    if not text:
        return None
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(cleaned[start:end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None
