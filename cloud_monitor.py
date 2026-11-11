#!/usr/bin/env python3
"""
Singapore Grand Prix 2027 - Cloud Ticket Monitor for GitHub Actions / Cloud Cron
雲端專用監控腳本：支援定時檢查與即時 Bark 手機推播。
"""

import sys
import time
import json
import re
import os
import ssl
import urllib.request
import urllib.parse
from datetime import datetime

TARGET_URL = "https://singaporegp.sg/en/tickets/general-tickets/grandstands/"
TARGET_SLUG = "republic-grandstand"
DEFAULT_BUY_URL = "https://queue-sg.axs.com/?c=axssg&e=6593660497585235&t_skin=singaporegp"

# 從環境變數讀取 Bark Key (例如: KB34tEmNct4QSTj24Nxs2E)
BARK_KEY = os.environ.get("BARK_KEY", "KB34tEmNct4QSTj24Nxs2E")

class SmartRedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_307(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_301(req, fp, code, msg, headers)

def send_bark_alert(key: str, title: str, message: str, url: str):
    """發送 iOS Bark 推播通知（時效性通知，點擊直接進入 AXS 隊列）"""
    if not key:
        print("[-] 未設定 BARK_KEY，跳過推播")
        return
    try:
        ctx = ssl._create_unverified_context()
        device_key = key.rstrip("/").split("/")[-1]
        quoted_title = urllib.parse.quote(title)
        quoted_msg = urllib.parse.quote(message)
        quoted_url = urllib.parse.quote(url)
        
        bark_url = (
            f"https://api.day.app/{device_key}/{quoted_title}/{quoted_msg}"
            f"?url={quoted_url}&group=SingaporeGP2027&level=timeSensitive&isArchive=1"
        )
        req = urllib.request.Request(bark_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            print("[+] Bark 手機推播已成功送達！")
    except Exception as e:
        print(f"[-] Bark 發送失敗: {e}")

def check_ticket():
    ctx = ssl._create_unverified_context()
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), SmartRedirectHandler)
    req = urllib.request.Request(
        TARGET_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache"
        }
    )

    with opener.open(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    m = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html)
    if not m:
        raise ValueError("未能解析頁面中的 __NEXT_DATA__")

    data = json.loads(m.group(1))
    tickets = data.get("props", {}).get("pageProps", {}).get("tickets", {})
    rg = tickets.get(TARGET_SLUG, [])
    if not rg:
        raise ValueError(f"未找到 {TARGET_SLUG}")

    item = rg[0]
    name = item.get("name", "Republic Grandstand")
    p0 = item.get("prices", [{}])[0]
    status = p0.get("ticket_status", "unknown")
    price = p0.get("price", "N/A")
    link = p0.get("ticketing_link") or DEFAULT_BUY_URL

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{now_str}] 檢查結果: 【{name}】 狀態: [{status.upper()}] | 票價: {price}")

    # 只要不是 currently_soldout 或 soldout，即代表有票！
    if status not in ["currently_soldout", "soldout", "inactive", "hidden"]:
        print(f"[{now_str}] 🎉 檢測到有票釋出！立即觸發手機推播！")
        msg = f"【新加坡 GP 2027 放票】{name} 目前有票！價格: {price}。請點擊本通知立即進入排隊購票！"
        send_bark_alert(BARK_KEY, "🏎️ Republic Grandstand 放票啦！", msg, link)
        return True
    return False

def main():
    print("=== Singapore GP 2027 雲端檢查任務啟動 ===")
    # 每次雲端任務執行進行 3 次檢測（間隔 20 秒，涵蓋約 1 分鐘區間）
    for i in range(3):
        has_ticket = check_ticket()
        if has_ticket:
            break
        if i < 2:
            time.sleep(20)

if __name__ == "__main__":
    main()
