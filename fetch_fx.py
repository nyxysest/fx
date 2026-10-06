#!/usr/bin/env python3
"""fx — نرخ لحظه‌ای ارز/طلا/سکه/نفت.

منبع پایه: ریپوی اوپن‌سورس itsyebekhe/usd (market.json، هر ۳۰ دقیقه آپدیت).
این اسکریپت هر ۱۵ دقیقه اجرا می‌شود و:
  ۱. market.json ریپوی اصلی را می‌خواند
  ۲. هر فیلد را اعتبارسنجی می‌کند (عدد معتبر؟ تازه؟ در رنج عقلانی؟)
  ۳. فیلدهای خراب/قدیمی را از منبع رسمی مستقیم می‌گیرد:
     - دلار/یورو/طلا/سکه ← alanchand.com (همان منبع ریپوی اصلی)
     - نفت برنت ← oilprice.com (همان منبع ریپوی اصلی)
  ۴. market.json تمیز + سالم را در همین ریپو بازنشر می‌کند

ربات تلگرام از market.json همین ریپو می‌خواند، پس همیشه نرخ درست و لحظه‌ای دارد.
"""
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone

UPSTREAM = "https://raw.githubusercontent.com/itsyebekhe/usd/main/market.json"
TEHRAN = timezone(timedelta(hours=3, minutes=30))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"}

# رنج‌های عقلانی (تومان) — بیرون از این رنج = دیتای خراب
RANGES = {
    "usd": (100_000, 1_000_000),
    "eur": (100_000, 1_200_000),
    "gold_18k": (5_000_000, 100_000_000),
    "gold_mesghal": (20_000_000, 450_000_000),
    "coin_emami": (50_000_000, 1_000_000_000),
    "coin_bahar": (50_000_000, 1_000_000_000),
    "coin_half": (20_000_000, 500_000_000),
    "coin_quarter": (10_000_000, 300_000_000),
    "coin_gram": (5_000_000, 150_000_000),
    "gold_ounce": (1_000, 10_000),   # دلار
    "oil": (20, 250),                # دلار
}
MAX_AGE_MIN = 120  # دیتای قدیمی‌تر از ۲ ساعت = کهنه


def get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def valid(key, v):
    n = num(v)
    if n is None or n <= 0:
        return False
    lo, hi = RANGES[key]
    return lo <= n <= hi


def stale(market):
    """True اگر updated_at قدیمی‌تر از MAX_AGE_MIN باشد."""
    try:
        ts = datetime.strptime(market.get("updated_at", ""), "%Y-%m-%d %H:%M:%S")
        ts = ts.replace(tzinfo=TEHRAN)
        return (datetime.now(TEHRAN) - ts) > timedelta(minutes=MAX_AGE_MIN)
    except Exception:
        return True


def fetch_alanchand_jsonld(url, want):
    """منبع رسمی ریپوی اصلی برای ارز/طلا/سکه: alanchand.com — JSON-LD."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {}
    try:
        html = get(url)
    except Exception as e:
        print(f"  alanchand fail {url}: {e}")
        return {}
    soup = BeautifulSoup(html, "lxml")
    out = {}
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            c = json.loads(s.get_text(strip=True) or "{}")
        except Exception:
            continue
        items = []
        if c.get("@type") == "ItemList":
            for elem in c.get("itemListElement", []):
                items.append(elem.get("item", {}))
        elif c.get("@type") == "Product":
            items.append(c)
        for item in items:
            name = item.get("name", "")
            offers = item.get("offers", {})
            try:
                price_irr = float(offers.get("price", 0))
            except (ValueError, TypeError):
                continue
            if not price_irr:
                continue
            val_toman = int(round(price_irr / 10.0)) if offers.get("priceCurrency") == "IRR" else price_irr
            for key, needle in want:
                if needle in name and key not in out:
                    out[key] = val_toman
    return out


def fetch_direct():
    """گرفتن مستقیم از منابع رسمی (همان منابع ریپوی اصلی)."""
    d = {}
    # یورو — alanchand EUR
    d.update(fetch_alanchand_jsonld(
        "https://alanchand.com/en/currencies-price/eur", [("eur", "EUR")]))
    # طلا و سکه — alanchand gold-price
    d.update(fetch_alanchand_jsonld("https://alanchand.com/en/gold-price", [
        ("gold_mesghal", "Mesghal"), ("gold_18k", "18K Gold"),
        ("coin_emami", "Full Coin"), ("coin_emami", "Imami"),
        ("coin_bahar", "Bahar Azadi"), ("coin_half", "Half Coin"),
        ("coin_quarter", "Quarter Coin"), ("coin_gram", "gram sekke"),
        ("gold_ounce", "Gold Ounce"),
    ]))
    # دلار — از روی درهم (همان روش ریپوی اصلی: درهم÷نرخ پگ)
    try:
        html_aed = get("https://alanchand.com/en/currencies-price/aed")
        html_rate = get("https://alanchand.com/en/exchange-rates/aed-usd")
        m_price = re.search(r'data-curr="tmn"[^>]*data-price="([\d,\.]+)"', html_aed)
        if not m_price:
            m_price = re.search(r'data-price="([\d,\.]+)"', html_aed)
        m_rate = re.search(r'data-rate="([\d\.]+)"', html_rate)
        if m_price and m_rate:
            aed_toman = float(m_price.group(1).replace(",", "")) / 10.0
            usd_rate = float(m_rate.group(1))
            d["usd"] = int(round(aed_toman / usd_rate))
    except Exception as e:
        print(f"  usd-via-aed fail: {e}")
    # نفت برنت — oilprice.com
    try:
        from bs4 import BeautifulSoup
        html = get("https://oilprice.com/oil-price-charts/46")
        soup = BeautifulSoup(html, "lxml")
        el = soup.select_one(".last_price")
        if el and num(el.get_text(strip=True)):
            d["oil"] = el.get_text(strip=True)
    except Exception as e:
        print(f"  oil fail: {e}")
    return d


def main():
    print("[fx] reading upstream market.json ...")
    try:
        market = json.loads(get(UPSTREAM))
    except Exception as e:
        print(f"[fx] upstream unreachable: {e}")
        market = {}
    is_stale = stale(market)
    print(f"[fx] upstream updated_at={market.get('updated_at')} stale={is_stale}")

    fixed, kept, dropped = [], [], []
    for key in RANGES:
        v = market.get(key)
        if valid(key, v):
            kept.append(key)
        else:
            dropped.append((key, v))

    direct = {}
    if dropped or is_stale:
        print(f"[fx] need direct fetch (bad={len(dropped)} stale={is_stale})")
        direct = fetch_direct()
        for key, old in dropped:
            if valid(key, direct.get(key)):
                market[key] = direct[key]
                fixed.append(key)
            else:
                print(f"  [fx] {key}: upstream bad ({old}) + direct bad — keeping old")
        if is_stale:
            # رفرش همه فیلدها با دیتای مستقیم سالم
            for key in RANGES:
                if valid(key, direct.get(key)):
                    if market.get(key) != direct[key]:
                        market[key] = direct[key]
                        if key not in fixed:
                            fixed.append(key)
    else:
        print("[fx] all upstream fields valid and fresh — no direct fetch")

    now = datetime.now(TEHRAN)
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    market["upstream_updated_at"] = market.get("updated_at")
    market["updated_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
    market["updated_iso"] = now.isoformat()
    market["date"] = now.strftime("%Y-%m-%d")
    market["date_shamsi"] = f"{jy}/{jm:02d}/{jd:02d}"
    market["time"] = now.strftime("%H:%M")
    market["updated"] = now.strftime("%Y-%m-%d %H:%M")
    market["source"] = "itsyebekhe/usd (validated + refreshed)"
    # NOTE: upstream_updated_at قبلاً بالاتر ست شد — این خط تکراری حذف شد

    with open("market.json", "w", encoding="utf-8") as f:
        json.dump(market, f, ensure_ascii=False, indent=2)
    print(f"[fx] kept={len(kept)} fixed={fixed} dropped-unfixable={[k for k,_ in dropped if k not in fixed]}")
    print("[fx] market.json written")


def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy if (gm > 2) else (gy - 1)
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


if __name__ == "__main__":
    main()
