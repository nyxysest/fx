<div dir="rtl" align="center">

# 💱 fx | نرخ لحظه‌ای ارز، طلا، سکه و نفت

**منبع پایه:** ریپوی اوپن‌سورس [`itsyebekhe/usd`](https://github.com/itsyebekhe/usd) (هر ۳۰ دقیقه آپدیت)

این ریپو هر **۱۵ دقیقه** `market.json` ریپوی اصلی را می‌خواند، هر فیلد را اعتبارسنجی می‌کند
(عدد معتبر؟ تازه؟ در رنج عقلانی؟) و فیلدهای خراب یا کهنه را **مستقیم از منبع رسمی**
(همان منابع ریپوی اصلی: `alanchand.com` برای ارز/طلا/سکه و `oilprice.com` برای نفت) می‌گیرد
و `market.json` تمیز و همیشه‌تازه را بازنشر می‌کند.

ساختار `market.json` دقیقاً مثل ریپوی اصلی است (+ دو فیلد `source` و `upstream_updated_at`).

</div>

<div dir="rtl">

### 🚀 API

* **قیمت‌های زنده (این ریپو):**
  ```text
  https://raw.githubusercontent.com/nyxysest/fx/main/market.json
  ```

* **ریپوی اصلی (منبع پایه):**
  ```text
  https://raw.githubusercontent.com/itsyebekhe/usd/main/market.json
  ```

</div>
