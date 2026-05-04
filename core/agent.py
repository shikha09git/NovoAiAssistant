"""
core/agent.py - nova Agent Brain (free mode)
Handles: STT -> local intent parser -> module dispatch -> TTS -> memory
"""

import re
import time
import subprocess
import os
import threading
import speech_recognition as sr
import pyttsx3
from dotenv import load_dotenv
from core.memory import Memory
from modules.email_mod import EmailModule
from modules.whatsapp_mod import WhatsAppModule
from modules.call_mod import CallModule
from modules.booking_mod import BookingModule
from modules.reminder_mod import ReminderModule
from modules.llm_mod import LLMModule
from modules.desktop_mod import DesktopModule

WAKE_WORDS = ["hey nova", "nova", "ok nova"]
COMMAND_HINTS = [
    "reminder", "yaad", "email", "whatsapp", "call", "phone", "book", "booking",
    "रिमाइंडर", "याद", "कॉल", "बुक", "टिकट",
    "english", "hindi", "inglish", "इंग्लिश", "हिंदी", "language", "bhasha",
    "open", "chrome", "gmail", "compose", "reply", "desktop", "computer", "pc",
    "ओपन", "खोल", "गूगल", "क्रोम", "यस", "हाँ", "नहीं"
]


class JarvisAgent:
    def __init__(self):
        load_dotenv()
        self.memory = Memory()
        self.always_listen = str(os.getenv("NOVA_ALWAYS_LISTEN", "0")).strip().lower() in ("1", "true", "yes", "on")
        self.english_only = str(os.getenv("NOVA_ENGLISH_ONLY", "1")).strip().lower() in ("1", "true", "yes", "on")
        self.stt_language = os.getenv("NOVA_STT_LANGUAGE", "en-IN" if self.english_only else "hi-IN").strip() or "en-IN"
        self.tts_force_sapi = str(os.getenv("NOVA_TTS_FORCE_SAPI", "0")).strip().lower() in ("1", "true", "yes", "on")
        self.tts_prefer_windows = str(os.getenv("NOVA_TTS_PREFER_WINDOWS", "1")).strip().lower() in ("1", "true", "yes", "on")
        self.recognizer = sr.Recognizer()
        self.mic = sr.Microphone()
        self.tts = None
        self.tts_lock = threading.Lock()
        try:
            self.tts = pyttsx3.init()
            self._setup_tts()
        except Exception as e:
            print(f"[TTS Init Error]: {e}")
        self.listening = False

        self.email = EmailModule()
        self.whatsapp = WhatsAppModule()
        self.call = CallModule()
        self.booking = BookingModule()
        self.reminder = ReminderModule()
        self.llm = LLMModule()
        self.desktop = DesktopModule()
        self.pending_plan = None
        self.pending_email_compose = None

    def _setup_tts(self):
        if not self.tts:
            return
        voices = self.tts.getProperty("voices")
        for v in voices:
            if "indian" in v.name.lower() or "ravi" in v.name.lower():
                self.tts.setProperty("voice", v.id)
                break
        self.tts.setProperty("rate", 170)
        self.tts.setProperty("volume", 0.95)

    def speak(self, text: str):
        print(f"[nova]: {text}")
        if self.tts_force_sapi or (os.name == "nt" and self.tts_prefer_windows):
            if self._speak_windows_fallback(text):
                return
        if self.tts:
            try:
                with self.tts_lock:
                    self.tts.say(text)
                    self.tts.runAndWait()
                return
            except Exception as e:
                print(f"[TTS Speak Error]: {e}")
        self._speak_windows_fallback(text)

    def _speak_windows_fallback(self, text: str) -> bool:
        # Last-resort TTS via Windows SAPI through PowerShell.
        safe = (text or "").replace("'", " ").replace('"', " ")
        ps = (
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.Rate=0; $s.Volume=100; "
            "$s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female,[System.Speech.Synthesis.VoiceAge]::Adult); "
            f"$s.Speak('{safe}')"
        )
        try:
            p = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
            return p.returncode == 0
        except Exception as e:
            print(f"[TTS Fallback Error]: {e}")
            return False

    def listen_once(self, timeout=8) -> str | None:
        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("[Listening...]")
            try:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=15)
                text = self.recognizer.recognize_google(audio, language=self.stt_language)
                print(f"[User]: {text}")
                return text.lower()
            except (sr.WaitTimeoutError, sr.UnknownValueError):
                return None
            except sr.RequestError as e:
                print(f"[STT Error]: {e}")
                return None

    def listen_loop(self):
        self.listening = True
        while self.listening:
            text = self.listen_once(timeout=30)
            if text:
                if self.pending_email_compose:
                    self._handle_email_compose_input(text)
                    continue

                if self.pending_plan:
                    if self._is_confirmation(text):
                        plan = self.pending_plan
                        self.pending_plan = None
                        self.execute_plan(plan, speak_out=True)
                        continue
                    if self._is_rejection(text):
                        self.pending_plan = None
                        self.speak("Okay, cancelled.")
                        continue
                    # Treat non-yes/no as command refinement instead of cancelling.
                    self.process_text(text, speak_out=True, require_confirmation=True)
                    continue

                print(f"[WakeCheck] heard='{text}'")
                triggered = self._is_wake_trigger(text)
                hinted_command = self._looks_like_command(text)
                print(f"[WakeCheck] triggered={triggered}")
                if self.always_listen or triggered or hinted_command or self._in_conversation:
                    command = self._strip_wake_words(text)
                    if command:
                        self.handle_command(command)
                    else:
                        self.speak("Yes, tell me.")
            time.sleep(0.1)

    def _extract_email(self, text: str) -> str:
        spoken = (text or "").lower().strip()
        spoken = spoken.replace(" at ", "@").replace(" dot ", ".").replace(" underscore ", "_").replace(" dash ", "-")
        spoken = spoken.replace(" ", "")
        m = re.search(r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", spoken)
        return m.group(1).strip() if m else ""

    def _start_email_compose_flow(self):
        self.pending_email_compose = {"to": "", "subject": "", "body": "", "stage": "to"}
        self.speak("Sure. Tell me the recipient email address.")

    def _handle_email_compose_input(self, text: str):
        draft = self.pending_email_compose or {}
        stage = draft.get("stage", "to")
        cleaned = self._strip_wake_words(text).strip() or text.strip()

        if stage == "to":
            to_email = self._extract_email(cleaned)
            if not to_email:
                self.speak("Please say a valid email address, like name at gmail dot com.")
                return
            draft["to"] = to_email
            draft["stage"] = "subject"
            self.pending_email_compose = draft
            self.speak("Got it. What should be the subject?")
            return

        if stage == "subject":
            draft["subject"] = cleaned
            draft["stage"] = "body"
            self.pending_email_compose = draft
            self.speak("What message should I write in the email body?")
            return

        draft["body"] = cleaned
        plan = {
            "intent": "gmail_compose_ui",
            "action": {"to": draft.get("to", ""), "subject": draft.get("subject", ""), "body": draft.get("body", "")},
            "spoken": "Opening Gmail compose in automated browser window.",
            "user_text": "compose email",
        }
        self.pending_email_compose = None
        self.execute_plan(plan, speak_out=True)

    @property
    def _in_conversation(self):
        return False

    def _classify(self, text: str) -> tuple[str, dict, str]:
        t = self._canonicalize(text)

        if ("open" in t or "launch" in t) and ("chrome" in t or "google chrome" in t):
            return "desktop_open_chrome", {}, "I can open Google Chrome."

        if "gmail" in t and ("compose" in t or "new mail" in t):
            return "gmail_compose_ui", {"to": "", "subject": "", "body": ""}, "I can open Gmail compose window."

        if "gmail" in t and ("read" in t or "inbox" in t or "unread" in t):
            return "gmail_read_ui", {"filter": "is:unread"}, "I can open your Gmail unread inbox."

        if "gmail" in t and "reply" in t:
            return "gmail_reply_last", {"reply_to": "", "body": "Thanks, received."}, "I can reply to the latest email, if Gmail API is connected."

        if "whatsapp" in t and ("open" in t or "web" in t):
            return "whatsapp_open_ui", {}, "I can open WhatsApp Web."

        # Clarification-first for ambiguous schedule/time queries.
        if any(k in t for k in ["what time", "time", "when"]) and not any(
            k in t for k in ["reminder", "alarm"]
        ):
            return "general", {}, "Please clarify what time information you need."

        if "save" in t:
            m = re.search(r"save\s+(.+?)\s*[:=]\s*(.+)", t)
            if m:
                key, value = m.group(1).strip(), m.group(2).strip()
                return "memory_save", {"key": key, "value": value}, "Saved."

        if any(k in t for k in ["email", "mail", "mails", "gmail"]) and any(k in t for k in ["read", "padho", "check", "inbox", "unread"]):
            return "email_read", {"filter": "is:unread"}, "I can check your unread emails."

        if any(k in t for k in ["email", "mail", "mails", "gmail"]) and any(k in t for k in ["summarize", "summary", "summarise"]):
            return "email_summarize", {"filter": "is:unread", "max_results": 5}, "I can summarize your unread emails."

        reply_latest_match = re.search(
            r"(?:reply|reply back)(?:\s+(?:to )?(?:the )?(?:latest|last))?.*(?:email|mail|gmail)(?:\s+saying\s+(.+))?$",
            t
        ) or re.search(
            r"(?:email|mail|gmail).*(?:reply|reply back)(?:\s+(?:to )?(?:the )?(?:latest|last))?(?:\s+saying\s+(.+))?$",
            t
        )
        if reply_latest_match:
            body = (reply_latest_match.group(1) or "").strip()
            if not body:
                body = "Thanks, received."
            return "email_reply_latest", {"body": body}, "I can reply to your latest email."

        if "email" in t and ("send" in t or "bhejo" in t):
            return "email_send", {"to": "", "subject": "", "body": text}, "I can send that email."

        if "whatsapp" in t and ("read" in t or "padho" in t):
            return "whatsapp_read", {"from": "all"}, "I can read saved WhatsApp messages."

        if "whatsapp" in t and ("send" in t or "karo" in t or "bhejo" in t):
            number = self._extract_number(t)
            return "whatsapp_send", {"to": number or "", "message": text}, "I can open WhatsApp message window."

        if "call" in t or "phone" in t:
            number = self._extract_number(t)
            return "call", {"to": number or ""}, "I can place that call."

        if "reminder" in t:
            return "reminder", {"text": text, "time": text}, "I can set that reminder."

        if "book" in t or "booking" in t:
            btype = "flight"
            if "train" in t:
                btype = "train"
            elif "hotel" in t:
                btype = "hotel"
            elif "movie" in t:
                btype = "movie"
            return "booking", {"type": btype, "details": text}, f"I can open the {btype} booking flow."

        # LLM planner after specific rules, to avoid hijacking email/gmail intents.
        llm_plan = self.llm.plan_command(text)
        if llm_plan and llm_plan.get("confidence", 0.0) >= 0.7:
            llm_intent = llm_plan.get("intent", "")
            llm_action = llm_plan.get("action", {})
            llm_spoken = llm_plan.get("spoken", "Okay, doing that.")
            if llm_intent in {"desktop_open_app", "desktop_open_website", "desktop_search_web"}:
                # Safety: if prompt clearly mentions email/gmail, don't route to open-app.
                if any(k in t for k in ["email", "mail", "mails", "gmail", "inbox"]):
                    pass
                else:
                    return llm_intent, llm_action, llm_spoken

        open_match = re.search(r"\b(?:can you\s+)?(?:please\s+)?(?:open|launch|start|run)\s+(.+)$", t)
        if open_match:
            target = open_match.group(1).strip()
            if target:
                return "desktop_open_app", {"app": target}, f"Opening {target}."

        return "general", {}, "I understood. Please give a more specific command."

    def _is_confirmation(self, text: str) -> bool:
        t = self._canonicalize(text)
        yes_words = {
            "yes", "yeah", "yep", "yup", "yas",
            "haan", "ha", "han", "hmm yes",
            "ok", "okay", "sure", "alright", "all right",
            "karo", "do it", "go ahead", "continue", "confirm",
        }
        if any(w in t for w in yes_words):
            return True
        # STT can return short noisy variants; accept clean single-token confirmations.
        tokens = set(t.split())
        return bool(tokens & {"yes", "ok", "okay", "sure", "haan", "ha"})

    def _is_rejection(self, text: str) -> bool:
        t = self._canonicalize(text)
        no_words = {"no", "nope", "nah", "mat", "cancel", "stop", "nahin", "nahi", "na", "dont", "don't"}
        return any(w in t for w in no_words)

    def _extract_number(self, text: str) -> str | None:
        digits = re.findall(r"\d+", text)
        if not digits:
            return None
        joined = "".join(digits)
        return joined if len(joined) >= 10 else None

    def _normalize_text(self, text: str) -> str:
        # Keep letters/digits/spaces and collapse multiple spaces.
        t = re.sub(r"[^\w\s]", " ", text.lower())
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _canonicalize(self, text: str) -> str:
        t = self._normalize_text(text)
        replacements = {
            "गूगल": "google",
            "क्रोम": "chrome",
            "खोलो": "open",
            "खोल": "open",
            "ओपन": "open",
            "मेल": "mail",
            "जीमेल": "gmail",
            "हाँ": "haan",
            "हां": "haan",
            "यस": "yes",
            "नहीं": "no",
            "नही": "no",
        }
        if self.english_only:
            replacements = {}
        for k, v in replacements.items():
            t = t.replace(k, v)
        return re.sub(r"\s+", " ", t).strip()

    def _is_wake_trigger(self, text: str) -> bool:
        t = self._normalize_text(text)
        # Accept common recognizer variants in Hindi/English.
        if re.search(r"\b(hey|hi|he|ok|okay)?\s*(nova|nove|no va|नोवा|नवा|लेनेवो|ले नोवो|नेवो|jarvis|जार्विस|जार|जार)\b", t):
            return True
        # Recognizer sometimes drops "nova" but keeps greeting.
        if re.search(r"\b(hey|hi|hello|he|हेलो|हे|हाय|ही)\b", t):
            return True
        return False

    def _strip_wake_words(self, text: str) -> str:
        t = self._normalize_text(text)
        t = re.sub(r"\b(hey|hi|he|ok|okay)\s*(nova|nove|no va|नोवा|नवा|लेनेवो|ले नोवो|नेवो|jarvis|जार्विस|जार|जार)\b", " ", t)
        t = re.sub(r"\b(nova|nove|no va|नोवा|नवा|लेनेवो|ले नोवो|नेवो|jarvis|जार्विस|जार|जार)\b", " ", t)
        t = re.sub(r"\b(hey|hi|hello|he|हेलो|हे|हाय|ही)\b", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _looks_like_command(self, text: str) -> bool:
        t = self._canonicalize(text)
        return any(k in t for k in COMMAND_HINTS)

    def process_text(self, text: str, speak_out: bool = True, require_confirmation: bool = True) -> dict:
        intent, action, spoken = self._classify(text)
        if intent == "gmail_compose_ui":
            if not action.get("to") and not action.get("subject") and not action.get("body"):
                self._start_email_compose_flow()
                return {
                    "ok": True,
                    "intent": intent,
                    "spoken_reply": "Sure. Tell me recipient email address.",
                    "action": {},
                    "awaiting_input": "email_to",
                }
        self.pending_plan = {"intent": intent, "action": action, "spoken": spoken, "user_text": text}
        if not require_confirmation:
            plan = self.pending_plan
            self.pending_plan = None
            return self.execute_plan(plan, speak_out=speak_out)
        preview = f"{spoken} Should I continue?"
        if speak_out:
            self.speak(preview)
        return {"ok": True, "intent": intent, "spoken_reply": preview, "action": action, "awaiting_confirmation": True}

    def execute_plan(self, plan: dict, speak_out: bool = True) -> dict:
        intent = plan["intent"]
        action = plan["action"]
        spoken = plan["spoken"]
        user_text = plan.get("user_text", "")

        self.memory.save_interaction(user_text, intent, action)

        try:
            if intent == "email_send":
                if self.email.api_connected:
                    self.email.send(action.get("to"), action.get("subject"), action.get("body"))
                else:
                    # Browser fallback: open compose flow for manual send.
                    self.desktop.open_gmail_compose(action.get("to", ""), action.get("subject", ""), action.get("body", ""))
                    spoken = "Opened Gmail compose in browser. Please review and send."
            elif intent == "email_reply":
                if self.email.api_connected:
                    self.email.reply(action.get("reply_to"), action.get("body"))
                else:
                    sent_to = self.email.reply_latest_browser(action.get("body", "Thanks, received."))
                    spoken = f"Opened browser reply for latest email from {sent_to}."
            elif intent == "email_read":
                emails = self.email.read(action.get("filter", "is:unread")) if self.email.api_connected else self.email.read_browser(5)
                if not emails:
                    spoken = "You have no unread emails."
                else:
                    top = emails[:3]
                    brief = "; ".join([f"{e.get('from','Unknown')} about {e.get('subject','(no subject)')}" for e in top])
                    spoken = f"You have {len(emails)} unread emails. Top ones: {brief}."
            elif intent == "email_summarize":
                max_results = int(action.get("max_results", 5))
                emails = self.email.read(action.get("filter", "is:unread"), max_results) if self.email.api_connected else self.email.read_browser(max_results)
                if not emails:
                    spoken = "No unread emails to summarize."
                else:
                    bullets = []
                    for e in emails[:5]:
                        bullets.append(f"From {e.get('from','Unknown')}, subject {e.get('subject','(no subject)')}.")
                    prompt = "Summarize these unread emails in two short spoken lines:\n" + "\n".join(bullets)
                    ai_reply = self.llm.reply(prompt)
                    spoken = ai_reply or " ".join(bullets[:2])
            elif intent == "email_reply_latest":
                if self.email.api_connected:
                    sent_to = self.email.reply_latest(action.get("body", "Thanks, received."))
                    spoken = f"Replied to your latest email from {sent_to}."
                else:
                    sent_to = self.email.reply_latest_browser(action.get("body", "Thanks, received."))
                    spoken = f"Opened browser reply for latest email from {sent_to}. Please review and send."
            elif intent == "whatsapp_send":
                self.whatsapp.send(action.get("to"), action.get("message"))
            elif intent == "whatsapp_read":
                msgs = self.whatsapp.read(action.get("from", "all"))
                spoken = f"There are {len(msgs)} messages in saved inbox."
            elif intent == "desktop_open_chrome":
                self.desktop.open_chrome()
                spoken = "Opened Chrome."
            elif intent == "desktop_open_app":
                app = action.get("app", "")
                self.desktop.open_app(app)
                spoken = spoken or f"Opening {app}."
            elif intent == "desktop_open_website":
                url = action.get("url", "")
                self.desktop.open_website(url)
                spoken = spoken or "Opening website."
            elif intent == "desktop_search_web":
                query = action.get("query", "")
                self.desktop.search_web(query)
                spoken = spoken or "Searching on web."
            elif intent == "gmail_compose_ui":
                to = action.get("to", "")
                subject = action.get("subject", "")
                body = action.get("body", "")
                ok = self.desktop.compose_gmail_with_playwright(to, subject, body)
                if not ok:
                    self.desktop.open_gmail_compose(to, subject, body)
                spoken = "Opened Gmail compose. Please review and click send."
            elif intent == "gmail_read_ui":
                self.desktop.open_gmail_search(action.get("filter", "is:unread"))
                spoken = "Opened Gmail unread inbox."
            elif intent == "gmail_reply_last":
                if self.email.api_connected:
                    self.email.reply(action.get("reply_to", ""), action.get("body", "Thanks, received."))
                    spoken = "Replied to the latest email."
                else:
                    sent_to = self.email.reply_latest_browser(action.get("body", "Thanks, received."))
                    spoken = f"Opened browser reply for latest email from {sent_to}."
            elif intent == "whatsapp_open_ui":
                self.desktop.open_whatsapp()
                spoken = "Opened WhatsApp Web."
            elif intent == "call":
                self.call.dial(action.get("to"))
            elif intent == "booking":
                self.booking.book(action.get("type"), action.get("details"))
            elif intent == "reminder":
                trigger_at = self.reminder.set(action.get("text"), action.get("time"))
                action["trigger_at"] = trigger_at.isoformat()
                spoken = f"Reminder set for {trigger_at.strftime('%H:%M')}."
            elif intent == "memory_save":
                self.memory.save(action.get("key"), action.get("value"))
            elif intent == "general":
                ai_reply = self.llm.reply(user_text)
                if ai_reply:
                    spoken = ai_reply
        except Exception as e:
            print(f"[Module Error {intent}]: {e}")
            spoken = "Kaam start hua, lekin ek issue aaya. Please check settings."

        if speak_out:
            self.speak(spoken)
        return {"ok": True, "intent": intent, "spoken_reply": spoken, "action": action}

    def handle_command(self, text: str):
        self.process_text(text, speak_out=True, require_confirmation=True)


class NovaAgent(JarvisAgent):
    """Backward-compatible alias used by main.py."""
    pass
