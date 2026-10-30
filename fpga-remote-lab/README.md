# مدار — آزمایشگاه آنلاین FPGA

اجرای طرح‌های دیجیتال روی **FPGA فیزیکی ALINX AX309 / Spartan-6 XC6SLX9-2FTG256C** با سرور Python روی Raspberry Pi و رابط وب فارسی.

- [پنل آزمایشگاه](https://aminbagheri.com/rasp/)
- [مبدل Verilog به پروژهٔ آزمایشگاه](https://aminbagheri.com/fpga/)
- [راهنمای استفاده از سایت و مثال فول‌ادر](docs/USER_GUIDE.fa.md)
- [نصب، تنظیم رمز و راه‌اندازی روی رزبری](docs/INSTALL.fa.md)
- [معماری، پروتکل و محدودیت‌ها](docs/ARCHITECTURE.fa.md)
- [انتشار اینترنتی و عیب‌یابی](docs/DEPLOYMENT.fa.md)

## روند کار

```text
Verilog کاربر → مبدل و نگاشت پورت‌ها → پروژهٔ V/UCF
→ ساخت lab_top.bit با ISE روی کامپیوتر کاربر
→ آپلود با رمز → FastAPI → عامل رزبری → JTAG → FPGA واقعی
                                              ↕ UART
                                WebSocket ← نمایش زندهٔ سایت
```

مبدل، کامپایلر FPGA نیست؛ ساخت بیت‌فایل Spartan-6 همچنان خارج از سایت انجام می‌شود. مشاهدهٔ زنده به بیت‌فایل دارای قالب UART آزمایشگاه نیاز دارد. بیت‌فایل معمولی ممکن است روی برد اجرا شود، اما وضعیت LEDهای آن از USB پروگرامر قابل استنتاج نیست.

## فایل‌ها

| مسیر | نقش |
| --- | --- |
| `server.py` | API، WebSocket، مدیریت جلسهٔ مشترک و تحویل بیت‌فایل به عامل |
| `converter.py` | استخراج پورت‌های Verilog و تولید پروژهٔ ZIP |
| `pi_agent.py` | عامل JTAG/UART، بررسی حضور سخت‌افزار و پروگرام SRAM |
| `upload_auth.py` | ساخت و بررسی هش رمز آپلود با PBKDF2-SHA256 |
| `static/` | پنل و مبدل فارسی |
| `hardware/template/` | قالب ثابت Verilog، UCF و اسکریپت ISE |
| `hardware/test_template.v` | تست‌بنچ پروتکل قالب |
| `deploy/` | سرویس‌های systemd و بستهٔ مبدل cPanel |
| `deploy/cloudflare/` | Worker مسیر `/rasp/`، تست‌ها و ابزار انتشار |
| `tunnel_dns.py` | ابزار اختیاری DNS محلی برای شبکهٔ پراکسی؛ برای اجرای عادی لازم نیست |

## شروع سریع برای توسعه

Python 3.10 یا جدیدتر:

```sh
python -m venv .venv
# Linux:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 8000
```

نشانی محلی: `http://127.0.0.1:8000/rasp/`. بدون عامل سخت‌افزار، کنترل‌ها غیرفعال‌اند. برای آپلود باید `UPLOAD_PASSWORD_HASH` تنظیم شود؛ [راهنمای نصب](docs/INSTALL.fa.md) را ببینید.

## آزمون‌ها

```sh
pip install -r requirements-dev.txt
python -m unittest -v test_converter test_server test_pi_agent
node --test deploy/cloudflare/rasp-worker.test.mjs
node --check static/app.js
```

این تست‌های Python از عامل شبیه‌سازی‌شده استفاده می‌کنند و برد واقعی را پروگرام نمی‌کنند. تست‌های Worker به Node.js با پشتیبانی `Request` و `Response` نیاز دارند. تست سخت‌افزار واقعی جداگانه است.

## وضعیت و حقوق

نسخهٔ مستندشده: ۲۰۲۶-۱۰-۳۰. این نسخه یک برد و یک جلسهٔ مشترک دارد. رمز فعلی فقط آپلود را محدود می‌کند؛ مشاهده و سایر کنترل‌ها حساب کاربری ندارند. سون‌سگمنت در نمای گرافیکی وجود دارد، ولی پروتکل فعلی عامل فقط LEDها و نتیجهٔ ۳۲ بیتی را منتقل می‌کند.

رمز، توکن، هش عملیاتی، نسخهٔ پشتیبان DNS، تنظیمات VPN و بیت‌فایل‌های خصوصی در این پوشه منتشر نشده‌اند. شناسهٔ پروگرامر در نسخهٔ قابل انتشار از متغیر محیطی خوانده می‌شود.

© کپی‌رایت برای مهدی هادی نژاد و امین باقری محفوظ است. مجوز متن‌باز مستقلی برای این پروژه اعطا نشده است.
