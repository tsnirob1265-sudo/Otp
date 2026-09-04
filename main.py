# -*- coding: utf-8 -*-

import os
import asyncio
import re
import requests
import time

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

MY_USER = os.getenv("MY_USER")
MY_PASS = os.getenv("MY_PASS")

TARGET_URL = "http://2.59.169.96/ints/agent/SMSCDRReports"
LOGIN_URL = "http://2.59.169.96/ints/login"

FB_URL = "https://mhnirob-default-rtdb.firebaseio.com/bot"

ADMIN_LINK = "https://t.me/Mhnirob1"
BOT_LINK = "https://t.me/tsall_bot"
DV_LINK = "https://t.me/Mhnirob1"
CN_LINK = "https://t.me/TS_CHENNEL"


# =========================================================
# GLOBAL
# =========================================================

sent_msgs = {}

START_TIME = time.time()


# =========================================================
# FIREBASE
# =========================================================

def update_firebase(num, msg, date_str, cli_source):

    try:
        clean_num = num.strip().lstrip("+")
        plus_num = f"+{clean_num}"

        # একই নাম্বার + একই OTP আগে Firebase-এ আছে কিনা চেক
        check_url = f"{FB_URL}/sms_logs.json"

        check_res = requests.get(
            check_url,
            timeout=10
        )

        if check_res.status_code == 200:
            existing_data = check_res.json() or {}

            for key, data in existing_data.items():

                if not isinstance(data, dict):
                    continue

                old_num = str(data.get("number", "")).strip().lstrip("+")
                old_msg = str(data.get("message", "")).strip()

                # একই নাম্বার + একই OTP
                if old_num == clean_num and old_msg == msg.strip():
                    print(f"♻️ Duplicate skipped: {clean_num} | {msg}")
                    return

        # ==========================================
        # নতুন SMS → ২টি Firebase entry
        # ==========================================

        timestamp = int(time.time() * 1000)

        # 1️⃣ Without +
        unique_id_1 = f"{clean_num}_{timestamp}"

        payload_1 = {
            "number": clean_num,
            "message": msg,
            "time": date_str,
            "service": cli_source,
            "paid": False
        }

        url_1 = f"{FB_URL}/sms_logs/{unique_id_1}.json"

        res1 = requests.put(
            url_1,
            json=payload_1,
            timeout=10
        )

        # 2️⃣ With +
        unique_id_2 = f"{plus_num}_{timestamp}"

        payload_2 = {
            "number": plus_num,
            "message": msg,
            "time": date_str,
            "service": cli_source,
            "paid": False
        }

        url_2 = f"{FB_URL}/sms_logs/{unique_id_2}.json"

        res2 = requests.put(
            url_2,
            json=payload_2,
            timeout=10
        )

        if res1.status_code in (200, 201) and res2.status_code in (200, 201):
            print(f"🔥 Firebase saved 2x: {clean_num}")
        else:
            print(
                f"⚠️ Firebase Error: "
                f"{res1.status_code} / {res2.status_code}"
            )

    except Exception as e:
        print("❌ Firebase Error:", repr(e))

# =========================================================
# OTP EXTRACT
# =========================================================

def extract_otp(msg):

    if not msg:
        return "N/A"

    match = re.search(
        r'\b\d{3,4}(?:[ -]?\d{3,4})?\b',
        msg
    )

    if match:

        otp = match.group(0)

        # Space এবং dash remove
        otp = re.sub(r'[\s-]', '', otp)

        return otp

    return "N/A"


# =========================================================
# TELEGRAM
# =========================================================

def send_telegram(
    date_str,
    num,
    sms_text,
    otp,
    cli_source,
    is_update=False
):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    masked = (
        num[:4] + "TS" + num[-4:]
        if len(num) > 8
        else num
    )

    if is_update:
        header = "🔄🛎️ <b>UPDATED SMS RECEIVED</b>"
    else:
        header = "🛎️ <b>NEW SMS RECEIVED</b>"

    text = (
        f"{header}\n\n"
        f"📞 <b>Number:</b> <code>{masked}</code>\n"
        f"🌐 <b>Service:</b> <code>{cli_source}</code>\n\n"
        f"🔑 <b>OTP:</b> <code>{otp}</code>\n\n"
        f"📩 <b>Full Message:</b>\n"
        f"<blockquote>{sms_text}</blockquote>\n"
    )

    keyboard = [
        [
            {
                "text": "👨‍🦲 Admin",
                "url": ADMIN_LINK
            },
            {
                "text": "🔢 Number bot",
                "url": BOT_LINK
            }
        ],
        [
            {
                "text": "💥 Channel",
                "url": CN_LINK
            },
            {
                "text": "💻 Developer",
                "url": DV_LINK
            }
        ]
    ]

    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": {
            "inline_keyboard": keyboard
        }
    }

    try:

        res = requests.post(
            url,
            json=payload,
            timeout=15
        )

        if res.status_code == 200:

            print(
                f"📤 Telegram sent: "
                f"{num} | {otp}"
            )

            return True

        print(
            f"⚠️ Telegram HTTP {res.status_code}: "
            f"{res.text[:300]}"
        )

        return False

    except Exception as e:

        print(
            "❌ Telegram Error:",
            repr(e)
        )

        return False


# =========================================================
# MAIN BOT
# =========================================================

async def start_bot():

    print("🚀 Bot started...")
    print("🌐 Target:", TARGET_URL)

    async with Stealth().use_async(
        async_playwright()
    ) as p:

        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu"
            ]
        )

        context = await browser.new_context(
            viewport={
                "width": 1280,
                "height": 720
            }
        )

        page = await context.new_page()


        # =================================================
        # LOGIN FUNCTION
        # =================================================

        async def login():

            try:

                print("🔐 Opening login page...")

                await page.goto(
                    LOGIN_URL,
                    wait_until="domcontentloaded",
                    timeout=60000
                )

                await page.wait_for_timeout(1500)

                print(
                    "🔐 Login URL:",
                    page.url
                )


                # -----------------------------------------
                # Find fields
                # -----------------------------------------

                inputs = await page.query_selector_all(
                    "input"
                )

                user_selector = None
                pass_selector = None
                ans_selector = None

                for inp in inputs:

                    try:

                        inp_type = (
                            await inp.get_attribute("type")
                        ) or ""

                        placeholder = (
                            await inp.get_attribute(
                                "placeholder"
                            )
                        ) or ""

                        name = (
                            await inp.get_attribute("name")
                        ) or ""

                        inp_id = (
                            await inp.get_attribute("id")
                        ) or ""

                        ptext = placeholder.lower()
                        ntext = name.lower()
                        idtext = inp_id.lower()

                        # Password
                        if inp_type.lower() == "password":
                            pass_selector = inp

                        # Answer
                        elif (
                            "answer" in ptext
                            or "answer" in ntext
                            or "ans" in ntext
                            or "answer" in idtext
                        ):
                            ans_selector = inp

                        # Username
                        elif (
                            "user" in ptext
                            or "user" in ntext
                            or "username" in idtext
                        ):
                            user_selector = inp

                    except Exception:
                        pass


                # -----------------------------------------
                # Fallback username
                # -----------------------------------------

                if not user_selector:

                    for inp in inputs:

                        try:

                            inp_type = (
                                await inp.get_attribute(
                                    "type"
                                )
                            ) or ""

                            if inp_type.lower() in (
                                "text",
                                ""
                            ):

                                user_selector = inp
                                break

                        except Exception:
                            pass


                # -----------------------------------------
                # Detect math question
                # -----------------------------------------

                body_text = await page.locator(
                    "body"
                ).inner_text()

                match = re.search(
                    r'What is\s+(\d+)\s*\+\s*(\d+)',
                    body_text,
                    re.I
                )

                answer = ""

                if match:

                    answer = str(
                        int(match.group(1))
                        + int(match.group(2))
                    )

                    print(
                        f"🧮 Captcha: "
                        f"{match.group(1)} + "
                        f"{match.group(2)} = "
                        f"{answer}"
                    )


                # -----------------------------------------
                # Fill username
                # -----------------------------------------

                if user_selector and MY_USER:

                    await user_selector.fill(
                        MY_USER
                    )


                # -----------------------------------------
                # Fill password
                # -----------------------------------------

                if pass_selector and MY_PASS:

                    await pass_selector.fill(
                        MY_PASS
                    )


                # -----------------------------------------
                # Fill answer
                # -----------------------------------------

                if (
                    ans_selector
                    and answer != ""
                ):

                    await ans_selector.fill(
                        answer
                    )


                # -----------------------------------------
                # Submit
                # -----------------------------------------

                buttons = await page.query_selector_all(
                    "button, input[type='submit']"
                )

                clicked = False

                for button in buttons:

                    try:

                        text = (
                            await button.inner_text()
                        ).strip()

                        value = (
                            await button.get_attribute(
                                "value"
                            )
                        ) or ""

                        combined = (
                            text + " " + value
                        ).lower()

                        if "login" in combined:

                            await button.click()

                            clicked = True

                            print(
                                "🔘 Login button clicked"
                            )

                            break

                    except Exception:
                        pass


                if not clicked:

                    print(
                        "⚠️ Login button not found"
                    )

                    return False


                # -----------------------------------------
                # Wait for navigation
                # -----------------------------------------

                await page.wait_for_timeout(
                    3000
                )

                print(
                    "➡️ After login:",
                    page.url
                )


                # -----------------------------------------
                # Check login status
                # -----------------------------------------

                if "login" not in page.url.lower():

                    print(
                        "✅ Login successful"
                    )

                    return True


                # Check page text
                current_text = (
                    await page.locator(
                        "body"
                    ).inner_text()
                ).lower()

                if (
                    "invalid" in current_text
                    or "incorrect" in current_text
                    or "wrong" in current_text
                ):

                    print(
                        "❌ Username/password/captcha "
                        "may be incorrect"
                    )

                else:

                    print(
                        "⚠️ Still on login page"
                    )

                return False


            except Exception as e:

                print(
                    "❌ Login Error:",
                    repr(e)
                )

                return False


        # =================================================
        # FIRST LOGIN
        # =================================================

        login_ok = await login()

        if not login_ok:

            print(
                "⚠️ Initial login failed."
            )

            print(
                "🔄 Bot will keep retrying..."
            )

        is_first_scan = True


        # =================================================
        # MAIN LOOP
        # =================================================

        while True:

            try:

                # -----------------------------------------
                # OPEN SMS REPORT
                # -----------------------------------------

                navigation_ok = False

                for attempt in range(1, 4):

                    try:

                        print(
                            f"🌐 Opening SMS page "
                            f"({attempt}/3)"
                        )

                        await page.goto(
                            TARGET_URL,
                            wait_until="commit",
                            timeout=30000
                        )

                        navigation_ok = True

                        break

                    except Exception as e:

                        print(
                            f"⚠️ Navigation error "
                            f"({attempt}/3):",
                            repr(e)
                        )

                        await asyncio.sleep(3)


                if not navigation_ok:

                    print(
                        "❌ Could not open SMS page"
                    )

                    await asyncio.sleep(10)

                    continue


                await page.wait_for_timeout(
                    1500
                )

                print(
                    "📍 Current URL:",
                    page.url
                )


                # -----------------------------------------
                # CHECK LOGIN
                # -----------------------------------------

                if "login" in page.url.lower():

                    print(
                        "🔐 Session expired. "
                        "Logging in again..."
                    )

                    login_ok = await login()

                    if login_ok:

                        await asyncio.sleep(2)

                    else:

                        await asyncio.sleep(5)

                    continue


                # -----------------------------------------
                # GET TABLE ROWS
                # -----------------------------------------

                valid_rows = []

                rows = await page.query_selector_all(
                    "table tbody tr"
                )

                print(
                    f"📋 Rows found: {len(rows)}"
                )


                for row in rows:

                    try:

                        cols = await row.query_selector_all(
                            "td"
                        )

                        # We use cols[0], [2], [3], [5]
                        if len(cols) >= 6:

                            d = (
                                await cols[0].inner_text()
                            ).strip()

                            n = (
                                await cols[2].inner_text()
                            ).strip()

                            cli = (
                                await cols[3].inner_text()
                            ).strip()

                            s = (
                                await cols[5].inner_text()
                            ).strip()


                            clean_num = re.sub(
                                r'\D',
                                '',
                                n
                            )


                            if (
                                d
                                and len(clean_num) >= 8
                                and s
                            ):

                                valid_rows.append({
                                    "date": d,
                                    "num": n,
                                    "sms": s,
                                    "cli": cli
                                })

                    except Exception as e:

                        print(
                            "⚠️ Row error:",
                            repr(e)
                        )


                # =================================================
                # PROCESS SMS
                # =================================================

                if valid_rows:

                    print(
                        f"📨 Valid SMS rows: "
                        f"{len(valid_rows)}"
                    )

                    latest = valid_rows[0]


                    # =================================================
                    # FIRST SCAN
                    # =================================================

                    if is_first_scan:

                        print(
                            "🟢 First scan detected"
                        )

                        otp = extract_otp(
                            latest["sms"]
                        )


                        sent = send_telegram(
                            latest["date"],
                            latest["num"],
                            latest["sms"],
                            otp,
                            latest["cli"]
                        )


                        if sent:

                            update_firebase(
                                latest["num"],
                                latest["sms"],
                                latest["date"],
                                latest["cli"]
                            )


                        sent_msgs[
                            f"{latest['num']}|"
                            f"{latest['sms']}"
                        ] = latest["date"]


                        # Mark existing old SMS
                        for item in valid_rows[1:]:

                            sent_msgs[
                                f"{item['num']}|"
                                f"{item['sms']}"
                            ] = item["date"]


                        is_first_scan = False

                        print(
                            "✅ First scan completed"
                        )


                    # =================================================
                    # NORMAL SCAN
                    # =================================================

                    else:

                        for item in reversed(
                            valid_rows
                        ):

                            uid = (
                                f"{item['num']}|"
                                f"{item['sms']}"
                            )


                            if uid in sent_msgs:

                                continue


                            otp = extract_otp(
                                item["sms"]
                            )


                            print(
                                f"🆕 New SMS: "
                                f"{item['num']} | "
                                f"{otp}"
                            )


                            sent = send_telegram(
                                item["date"],
                                item["num"],
                                item["sms"],
                                otp,
                                item["cli"]
                            )


                            if sent:

                                update_firebase(
                                    item["num"],
                                    item["sms"],
                                    item["date"],
                                    item["cli"]
                                )


                            sent_msgs[uid] = (
                                item["date"]
                            )


                # =================================================
                # CACHE LIMIT
                # =================================================

                if len(sent_msgs) > 1000:

                    print(
                        "🧹 Clearing SMS cache"
                    )

                    sent_msgs.clear()


            # =================================================
            # LOOP ERROR
            # =================================================

            except Exception as e:

                print(
                    "❌ Loop Error:",
                    repr(e)
                )

                await asyncio.sleep(5)


            # =================================================
            # POLLING DELAY
            # =================================================

            await asyncio.sleep(2)


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            start_bot()
        )

    except KeyboardInterrupt:

        print(
            "\n🛑 Bot stopped."
        )

    except Exception as e:

        print(
            "💥 Fatal Error:",
            repr(e)
                        )
