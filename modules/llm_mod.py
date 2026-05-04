"""
modules/llm_mod.py - Optional LLM helper for conversational replies and action plans.
Supports Groq out-of-the-box and OpenAI-compatible local/remote endpoints.
"""

import json
import os
import requests


class LLMModule:
    def __init__(self):
        self.provider = (os.getenv("NOVA_LLM_PROVIDER", "auto").strip().lower() or "auto")
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant").strip()

        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

        self.llama_base = os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:11434/v1").strip()
        self.llama_key = os.getenv("LLAMA_API_KEY", "").strip()
        self.llama_model = os.getenv("LLAMA_MODEL", "llama3.1:8b").strip()

        self.enabled = self._is_enabled()
        if self.enabled:
            chosen = self._choose_target()
            print(f"[LLM] Enabled via {chosen['name']} model: {chosen['model']}")
        else:
            print("[LLM] Disabled (configure GROQ_API_KEY or LLAMA_BASE_URL/OPENAI_API_KEY)")

    def _is_enabled(self) -> bool:
        if self.provider == "groq":
            return bool(self.groq_key)
        if self.provider == "openai":
            return bool(self.openai_key)
        if self.provider == "llama":
            return bool(self.llama_base)
        return bool(self.groq_key or self.openai_key or self.llama_base)

    def _choose_target(self) -> dict:
        if self.provider == "groq":
            return {"name": "groq", "base": "https://api.groq.com/openai/v1/chat/completions", "key": self.groq_key, "model": self.groq_model}
        if self.provider == "openai":
            return {"name": "openai", "base": "https://api.openai.com/v1/chat/completions", "key": self.openai_key, "model": self.openai_model}
        if self.provider == "llama":
            return {"name": "llama", "base": self.llama_base.rstrip("/") + "/chat/completions", "key": self.llama_key, "model": self.llama_model}
        if self.groq_key:
            return {"name": "groq", "base": "https://api.groq.com/openai/v1/chat/completions", "key": self.groq_key, "model": self.groq_model}
        if self.openai_key:
            return {"name": "openai", "base": "https://api.openai.com/v1/chat/completions", "key": self.openai_key, "model": self.openai_model}
        return {"name": "llama", "base": self.llama_base.rstrip("/") + "/chat/completions", "key": self.llama_key, "model": self.llama_model}

    def _chat(self, messages: list, temperature: float = 0.2, max_tokens: int = 120) -> str | None:
        if not self.enabled:
            return None
        target = self._choose_target()
        headers = {"Content-Type": "application/json"}
        if target["key"]:
            headers["Authorization"] = f"Bearer {target['key']}"
        payload = {
            "model": target["model"],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        try:
            res = requests.post(target["base"], json=payload, headers=headers, timeout=25)
            res.raise_for_status()
            data = res.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"[LLM] call failed ({target['name']}): {e}")
            return None

    def reply(self, user_text: str) -> str | None:
        return self._chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Nova, a concise and natural Hindi-English voice assistant. "
                        "Reply in 1-2 short spoken sentences. "
                        "If request is ambiguous, ask one clear follow-up question."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
            temperature=0.3,
            max_tokens=90,
        )

    def plan_command(self, user_text: str) -> dict | None:
        """
        Convert natural-language command into safe structured action.
        Returns dict: intent, action, spoken, confidence.
        """
        raw = self._chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an action planner for a Windows desktop voice assistant.\n"
                        "Return ONLY valid JSON with keys: intent, action, spoken, confidence.\n"
                        "Allowed intents: desktop_open_app, desktop_open_website, desktop_search_web, general.\n"
                        "action must be an object.\n"
                        "For desktop_open_app use action.app.\n"
                        "For desktop_open_website use action.url.\n"
                        "For desktop_search_web use action.query.\n"
                        "If not clearly actionable, use intent=general and confidence <= 0.5.\n"
                        "spoken must be short natural voice response."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
            temperature=0.1,
            max_tokens=160,
        )
        if not raw:
            return None
        try:
            # Some models wrap JSON in markdown fences.
            cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(cleaned)
            if not isinstance(data, dict):
                return None
            return {
                "intent": str(data.get("intent", "general")),
                "action": data.get("action") if isinstance(data.get("action"), dict) else {},
                "spoken": str(data.get("spoken", "Okay.")),
                "confidence": float(data.get("confidence", 0.0)),
            }
        except Exception:
            return None
