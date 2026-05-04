# NOVA - Free Stack + Optional Groq Brain

This build avoids paid APIs by default. You can optionally add Groq API for smarter replies.

## Stack
- Local rule-based intent engine (default, no paid LLM)
- Optional Groq API (free tier) for smarter conversational replies
- SpeechRecognition (Google web STT, no paid key)
- pyttsx3 TTS (offline)
- Gmail API (free quota)
- WhatsApp send via `wa.me` browser links
- Call helper via OS dialer (`tel:` link)
- Booking via browser open / Playwright helper
- SQLite memory + OS reminders

## PC Setup
1. Install:
```bash
pip install -r requirements.txt
playwright install chromium
```

2. Optional: enable Groq brain
- Create `.env` file in `jarvis/`:
```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.1-8b-instant
```
- If `GROQ_API_KEY` is missing, Nova falls back to local rule responses.

3. Optional Gmail setup for email features:
- Enable Gmail API in Google Cloud
- Put OAuth desktop client as `data/gmail_credentials.json`

4. Run:
```bash
python main.py
```

NOVA API starts at:
`http://<PC-LAN-IP>:8787/api/command`

## Mobile Setup (free)
Mobile app is text-command client.

```bash
cd mobile
npm install
set EXPO_PUBLIC_NOVA_API_URL=http://<PC-LAN-IP>:8787/api/command
npx expo start
```

## Notes
- WhatsApp read works only from locally saved webhook inbox file.
- Direct automated phone call is not free on PC; dialer helper opens instead.
- SpeechRecognition Google web STT depends on internet and may fail intermittently.
- Best reliability setup: Groq enabled + strong internet, or migrate to offline STT (Vosk).
