#!/usr/bin/env python3
"""
Singapore Grand Prix 2027 - Republic Grandstand Ticket Monitor
監控 Singapore GP 2027 官方網站 Republic Grandstand 票務狀態。
一旦狀態從 'currently_soldout' 變為 'active' 或有釋票，立即觸發手機推播通知與自動開啟搶票連結。
（已依要求關閉語音與高分貝警報音效）
"""

import sys
import time
import json
import re
import os
import ssl
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime

# 目錄與配置檔案路徑
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

# 預設配置
DEFAULT_CONFIG = {
    "target_ticket_slug": "republic-grandstand",
    "check_interval_seconds": 30,
    "default_buy_url": "https://queue-sg.axs.com/?c=axssg&e=6593660497585235&t_skin=singaporegp",
    "auto_open_browser": True,
    "mac_notification": True,
    # 手機推播配置
    "discord_webhook_url": "",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "bark_key": "",
    "custom_webhook_url": ""
}

def load_config():
    """載入設定檔，優先使用 config.json，其次環境變數"""
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                config.update(user_cfg)
        except Exception as e:
            print(f"[Config Warning] 讀取 config.json 失敗: {e}")

    # 環境變數覆蓋
    if os.environ.get("DISCORD_WEBHOOK_URL"):
        config["discord_webhook_url"] = os.environ["DISCORD_WEBHOOK_URL"]
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        config["telegram_bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
    if os.environ.get("TELEGRAM_CHAT_ID"):
        config["telegram_chat_id"] = os.environ["TELEGRAM_CHAT_ID"]
    if os.environ.get("BARK_KEY"):
        config["bark_key"] = os.environ["BARK_KEY"]
    if os.environ.get("CUSTOM_WEBHOOK_URL"):
        config["custom_webhook_url"] = os.environ["CUSTOM_WEBHOOK_URL"]

    return config

TARGET_URL = "https://singaporegp.sg/en/tickets/general-tickets/grandstands/"

class SmartRedirectHandler(urllib.request.HTTPRedirectHandler):
    """處理 Next.js 頁面可能返回的 307/308 重定向"""
    def http_error_307(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_301(req, fp, code, msg, headers)

def send_mac_notification(title: str, message: str):
    """觸發 macOS 系統靜音/標準通知（無高分貝報警）"""
    try:
        apple_script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", apple_script], check=False)
    except Exception as e:
        print(f"[Mac Notification Error] {e}")

def open_checkout_browser(url: str):
    """自動開啟瀏覽器前往購票頁面"""
    try:
        print(f"[*] 自動開啟瀏覽器購票連結: {url}")
        subprocess.run(["open", url], check=False)
    except Exception as e:
        print(f"[Open Browser Error] {e}")

def send_telegram_alert(token: str, chat_id: str, message: str):
    """發送 Telegram 推播通知"""
    if not token or not chat_id:
        return
    try:
        tg_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": False
        }).encode("utf-8")
        req = urllib.request.Request(tg_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
        print("[+] Telegram 手機通知已成功發送！")
    except Exception as e:
        print(f"[-] Telegram 發送失敗: {e}")

def send_discord_alert(webhook_url: str, message: str):
    """發送 Discord Webhook 通知"""
    if not webhook_url:
        return
    try:
        payload = json.dumps({
            "content": f"🚨 **【Singapore GP 2027 放票通知】** 🚨\n{message}"
        }).encode("utf-8")
        req = urllib.request.Request(webhook_url, data=payload, headers={
            "Content-Type": "application/json",
            "User-Agent": "TicketMonitor/1.0"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
        print("[+] Discord 手機通知已成功發送！")
    except Exception as e:
        print(f"[-] Discord 發送失敗: {e}")

def send_bark_alert(bark_key: str, title: str, message: str, url: str = ""):
    """發送 iOS Bark App 推播通知（設定為時效性通知，點擊直接跳轉購票頁面）"""
    if not bark_key:
        return
    try:
        ctx = ssl._create_unverified_context()
        key = bark_key.rstrip("/").split("/")[-1]
        quoted_title = urllib.parse.quote(title)
        quoted_msg = urllib.parse.quote(message)
        bark_url = f"https://api.day.app/{key}/{quoted_title}/{quoted_msg}?group=SingaporeGP2027&level=timeSensitive"
        if url:
            bark_url += f"&url={urllib.parse.quote(url)}"

        req = urllib.request.Request(bark_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            pass
        print("[+] iOS Bark 手機通知已成功發送！")
    except Exception as e:
        print(f"[-] Bark 發送失敗: {e}")

def send_custom_webhook(webhook_url: str, data: dict):
    """發送自訂 Webhook"""
    if not webhook_url:
        return
    try:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(webhook_url, data=payload, headers={
            "Content-Type": "application/json",
            "User-Agent": "TicketMonitor/1.0"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
        print("[+] 自訂 Webhook 通知已發送！")
    except Exception as e:
        print(f"[-] 自訂 Webhook 發送失敗: {e}")

def trigger_all_alerts(config: dict, ticket_name: str, price: str, buy_url: str):
    """釋票時觸發通知（安靜模式：無語音、無高分貝警報）"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"【放票通知】{ticket_name} 目前有票！價格: {price}。\n請立即前往搶票: {buy_url}"
    print("\n" + "!" * 60)
    print(f"[{timestamp}] 🚨 {msg}")
    print("!" * 60 + "\n")

    # 1. macOS 靜音桌面通知
    if config.get("mac_notification", True):
        send_mac_notification("Singapore GP 2027 放票啦！", f"{ticket_name} ({price}) 目前可購買！")

    # 2. 自動開啟購票連結
    if config.get("auto_open_browser", True):
        open_checkout_browser(buy_url)

    # 3. 手機推播通知
    send_discord_alert(config.get("discord_webhook_url", ""), msg)
    send_telegram_alert(config.get("telegram_bot_token", ""), config.get("telegram_chat_id", ""), msg)
    send_bark_alert(config.get("bark_key", ""), "Singapore GP 2027 放票啦！", msg, buy_url)
    send_custom_webhook(config.get("custom_webhook_url", ""), {
        "event": "ticket_available",
        "ticket": ticket_name,
        "price": price,
        "url": buy_url,
        "timestamp": timestamp
    })

def fetch_ticket_status(target_slug: str):
    """向官方網站請求並解析票務狀態"""
    ctx = ssl._create_unverified_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), SmartRedirectHandler)
    req = urllib.request.Request(
        TARGET_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    )

    with opener.open(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not m:
        raise ValueError("未能解析頁面中的 __NEXT_DATA__ JSON 數據")

    data = json.loads(m.group(1))
    tickets = data.get("props", {}).get("pageProps", {}).get("tickets", {})
    rg = tickets.get(target_slug, [])

    if not rg:
        raise ValueError(f"未在票務列表中找到 '{target_slug}'")

    ticket_item = rg[0]
    name = ticket_item.get("name", "Republic Grandstand")
    prices = ticket_item.get("prices", [])

    if not prices:
        raise ValueError("未獲取到價格或售票狀態信息")

    p = prices[0]
    ticket_status = p.get("ticket_status", "unknown")
    price = p.get("price", "N/A")
    ticketing_link = p.get("ticketing_link") or DEFAULT_CONFIG["default_buy_url"]

    return {
        "name": name,
        "status": ticket_status,
        "price": price,
        "link": ticketing_link,
        "date_updated": p.get("date_updated")
    }

def main():
    config = load_config()
    check_interval = config.get("check_interval_seconds", 30)
    target_slug = config.get("target_ticket_slug", "republic-grandstand")

    print("=" * 65)
    print("🏎️  Formula 1 Singapore Airlines Singapore Grand Prix 2027")
    print(f"📍 監控看台: {target_slug} (3-Day Pass)")
    print(f"⏱️ 檢查頻率: 每 {check_interval} 秒一次")
    print(f"🔕 警報模式: 安靜模式（已關閉語音與高分貝警報音效）")

    has_mobile_push = False
    if config.get("discord_webhook_url"):
        print("📱 手機推播: Discord Webhook [已設定]")
        has_mobile_push = True
    if config.get("telegram_bot_token") and config.get("telegram_chat_id"):
        print("📱 手機推播: Telegram Bot [已設定]")
        has_mobile_push = True
    if config.get("bark_key"):
        print("📱 手機推播: iOS Bark [已設定]")
        has_mobile_push = True
    if config.get("custom_webhook_url"):
        print("📱 手機推播: 自訂 Webhook [已設定]")
        has_mobile_push = True

    if not has_mobile_push:
        print("📱 手機推播: 尚未設定（目前僅會透過 Mac 桌面通知與自動開啟瀏覽器）")
    print("=" * 65)

    last_status = None
    loop_count = 0

    while True:
        loop_count += 1
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        try:
            info = fetch_ticket_status(target_slug)
            current_status = info["status"]
            name = info["name"]
            price = info["price"]
            link = info["link"]

            if current_status != last_status:
                print(f"[{now_str}] 狀態更新 -> 【{name}】 狀態: [{current_status.upper()}] | 票價: {price}")
                
                # 判定是否有票：只要不是 soldout 或 currently_soldout，就視為可購買
                if current_status not in ["currently_soldout", "soldout", "inactive", "hidden"]:
                    print(f"[{now_str}] 🎉 檢測到有票釋出！狀態: {current_status}")
                    trigger_all_alerts(config, name, price, link)
                elif last_status is not None:
                    print(f"[{now_str}] 狀態變更回售罄: {current_status}")

                last_status = current_status
            else:
                if loop_count % 10 == 0:
                    print(f"[{now_str}] 正常運行中 (已檢查 {loop_count} 次) - 目前狀態: {current_status} (暫時售完)")

        except Exception as e:
            print(f"[{now_str}] ⚠️ 檢查時發生錯誤: {e}")

        time.sleep(check_interval)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[*] 監控已手動停止。")
        sys.exit(0)
