"""
modules/booking_mod.py — Ticket/hotel booking via browser automation
Uses Playwright to open booking sites. User confirms before purchase.
"""

import webbrowser
import urllib.parse


BOOKING_URLS = {
    "flight": "https://www.makemytrip.com/flights/",
    "train": "https://www.irctc.co.in/",
    "hotel": "https://www.booking.com/",
    "movie": "https://www.bookmyshow.com/",
    "bus": "https://www.redbus.in/",
}


class BookingModule:
    def book(self, booking_type: str, details: str):
        """
        Tries automation first, then falls back to opening the site.
        """
        booking_type = (booking_type or "flight").lower()
        url = BOOKING_URLS.get(booking_type, BOOKING_URLS["flight"])

        # If details include search terms, add to URL
        if details and booking_type == "train":
            # IRCTC search
            url = f"https://www.irctc.co.in/nget/train-search?detailss={urllib.parse.quote(details)}"
        elif details and booking_type == "movie":
            url = f"https://in.bookmyshow.com/explore/movies-national?q={urllib.parse.quote(details)}"

        if self._try_automation(url, details):
            return

        print(f"[Booking] Opening {booking_type} booking: {url}")
        webbrowser.open(url)

    def _try_automation(self, url: str, details: str) -> bool:
        """
        Open page via Playwright so the user lands on controlled browser session.
        Full form fill can be added per provider later.
        """
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if details:
                    print(f"[Booking] Opened with details: {details}")
                print("[Booking] Browser opened for manual confirmation.")
                return True
        except Exception as e:
            print(f"[Booking] Automation unavailable, using browser fallback. Reason: {e}")
            return False
