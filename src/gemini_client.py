"""Gemini API client for AI-powered project health analysis."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)
import streamlit as st

try:
    if "GEMINI_API_KEY" in st.secrets:
        os.environ.setdefault("GEMINI_API_KEY", st.secrets["GEMINI_API_KEY"])
except Exception:
    pass  # no secrets.toml locally — fine, .env / os.environ will be used instead

# Load .env on import so this module works standalone (not just via Streamlit)
try:
    from dotenv import load_dotenv as _load_dotenv

    _load_dotenv(
        override=False
    )  # env vars already set (e.g. Replit Secrets) take precedence
except ImportError:
    pass

_CLIENT_CACHE: Optional[Any] = None


def _get_client() -> Any:

    global _CLIENT_CACHE
    if _CLIENT_CACHE is not None:
        return _CLIENT_CACHE

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get(
        "AI_INTEGRATIONS_GEMINI_API_KEY"
    )
    base_url = os.environ.get("AI_INTEGRATIONS_GEMINI_BASE_URL")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")

    try:
        import google.generativeai as genai

        if base_url:
            import google.api_core.client_options as client_options_lib

            genai.configure(
                api_key=api_key,
                client_options=client_options_lib.ClientOptions(api_endpoint=base_url),
            )
        else:
            genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.5-flash")
        _CLIENT_CACHE = model
        logger.info("Gemini client initialized (model: gemini-2.5-flash)")
        return model
    except ImportError as exc:
        raise RuntimeError("google-generativeai package not installed") from exc


def call_gemini(prompt: str, retries: int = 3, delay: float = 2.0) -> str:
    """Send a prompt to Gemini and return the text response.

    Retries on transient errors with exponential backoff.
    """
    model = _get_client()

    for attempt in range(1, retries + 1):
        try:
            response = model.generate_content(prompt)
            text = response.text
            logger.debug("Gemini response (attempt %d): %s...", attempt, text[:120])
            return text
        except Exception as exc:
            logger.warning(
                "Gemini call failed (attempt %d/%d): %s", attempt, retries, exc
            )
            if attempt < retries:
                time.sleep(delay * attempt)
            else:
                raise RuntimeError(
                    f"Gemini API call failed after {retries} attempts: {exc}"
                ) from exc

    return ""  # unreachable


def call_gemini_json(prompt: str, retries: int = 3) -> dict[str, Any]:
    """Call Gemini and parse the response as JSON.

    Strips markdown fences if present before parsing.
    """
    text = call_gemini(prompt, retries=retries)

    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text.strip(), flags=re.MULTILINE)
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Attempt to extract first {...} block
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        logger.error("Failed to parse Gemini JSON response: %s", text[:300])
        raise ValueError(f"Gemini returned non-JSON response: {exc}") from exc
