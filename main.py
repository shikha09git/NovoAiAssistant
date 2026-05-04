"""
Nova - Personal AI Voice Agent
Run: python main.py
Requirements: pip install openai anthropic speechrecognition pyttsx3 pyaudio
              pip install twilio google-auth google-auth-oauthlib google-api-python-client
              pip install playwright sqlite-utils pystray pillow
"""

import sys
import threading
import time
from core.agent import NovaAgent
from core.tray import run_tray
from core.api_server import run_api_server

def main():
    print("=" * 50)
    print("  Nova - AI Voice Agent  ")
    print("=" * 50)
    print("Starting... Press Ctrl+C to quit\n")

    agent = NovaAgent()
    agent.speak("Nova ready. How can I help you?")

    # Run system tray icon in background thread
    tray_thread = threading.Thread(target=run_tray, args=(agent,), daemon=True)
    tray_thread.start()

    # Run HTTP API for mobile clients on the same agent core/memory
    api_thread = threading.Thread(target=run_api_server, args=(agent,), daemon=True)
    api_thread.start()

    # Main voice loop
    print("Say 'Hey Nova' or press the tray icon mic to start...\n")
    try:
        agent.listen_loop()
    except KeyboardInterrupt:
        agent.speak("Goodbye!")
        print("\nNova stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
