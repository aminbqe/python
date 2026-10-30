# نصب روی Raspberry Pi

## پیش‌نیازها

Raspberry Pi OS با Python 3.10+، دسترسی سریال، پروگرامر سازگار با `openFPGALoader` و AX309. عامل فعلی برای کابل FT232H با درایور `digilent_hs2` تنظیم شده است؛ برای کابل دیگر پارامترهای `pi_agent.py` را تطبیق دهید.

```sh
git clone https://github.com/aminbqe/python.git
cp -r python/fpga-remote-lab ~/fpga-sim
cd ~/fpga-sim
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`openFPGALoader` باید جداگانه از مخزن سیستم‌عامل یا بستهٔ مناسب معماری نصب شود و کاربر سرویس به USB و UART دسترسی داشته باشد. در Raspberry Pi OS با `raspi-config` کنسول سریال را غیرفعال و سخت‌افزار UART را فعال کنید. گروه‌های دسترسی و قواعد udev را متناسب با سیستم تنظیم کنید. نصب Python به‌تنهایی دسترسی USB ایجاد نمی‌کند.

## ایجاد تنظیمات خصوصی

این فرمان در Linux یک `.env` تازه می‌سازد و در صورت وجود فایل قبلی متوقف می‌شود. رمز را بدون نمایش در ترمینال می‌پرسد و فقط هش آن را ذخیره می‌کند:

```sh
python - <<'PY'
import getpass, os, secrets
from upload_auth import hash_password
password = getpass.getpass('Upload password: ')
if password != getpass.getpass('Repeat upload password: '):
    raise SystemExit('Passwords do not match')
serial = input('FTDI programmer serial: ').strip()
if not serial:
    raise SystemExit('Programmer serial is required')
content = '\n'.join([
    'AGENT_TOKEN=' + secrets.token_urlsafe(32),
    'UPLOAD_PASSWORD_HASH=' + hash_password(password),
    'LAB_URL=http://127.0.0.1:8000',
    'UART_PORT=/dev/serial0',
    'FPGA_PROGRAMMER_SERIAL=' + serial,
]) + '\n'
with os.fdopen(os.open('.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
    f.write(content)
PY
```

شناسهٔ FTDI را با ابزارهای شناسایی USB یا تنظیمات کابل خود پیدا کنید. نسخهٔ منتشرشده به شناسهٔ کابل خصوصی مدیر وابسته نیست. برای تغییر رمز موجود، با `upload_auth.hash_password` هش تازه بسازید، تنها `UPLOAD_PASSWORD_HASH` را در `.env` جایگزین و سرویس سرور را ریستارت کنید؛ توکن عامل را بی‌دلیل عوض نکنید.

فایل `.env` خودکار توسط Uvicorn خوانده نمی‌شود؛ systemd آن را با `EnvironmentFile` بارگذاری می‌کند. برای اجرای دستی در هر دو ترمینال Bash:

```sh
set -a
. ./.env
set +a
# ترمینال اول:
uvicorn server:app --host 127.0.0.1 --port 8000
# ترمینال دوم، پس از بارگذاری همان .env:
python pi_agent.py
```

## اجرای خودکار

```sh
mkdir -p ~/.config/systemd/user
cp deploy/fpga-lab.service deploy/fpga-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now fpga-lab fpga-agent
sudo loginctl enable-linger "$USER"
journalctl --user -u fpga-lab -u fpga-agent -n 60
```

فایل‌ها باید در `~/fpga-sim` باشند؛ در غیر این صورت مسیر سرویس‌ها را اصلاح کنید. سرویس نمونه روی `0.0.0.0:8000` گوش می‌دهد؛ در نصب صرفاً تونلی می‌توان آن را به `127.0.0.1` محدود کرد.

## سیم‌کشی

USB/JTAG برای پروگرام و UART برای تبادل ورودی/خروجی دو مسیر جدا هستند. Raspberry Pi و FPGA باید زمین مشترک و سطح منطقی ۳٫۳ ولت داشته باشند. پایهٔ تغذیه را برای ارتباط UART متصل نکنید و از سیگنال RS232 روی GPIO استفاده نکنید.

قالب فعلی `lab.ucf` برای TX/RX از K16/L16 استفاده می‌کند. محل این سیگنال‌ها روی هدر باید با شماتیک و شماره‌گذاری همان نسخهٔ برد کنترل شود؛ نام چاپ‌شدهٔ J2 یا ظاهر کانکتور برای تعیین پایه کافی نیست. TX هر سمت به RX سمت دیگر وصل می‌شود. پین فیزیکی ۸ رزبری GPIO14/TXD و پین ۱۰ GPIO15/RXD است؛ زمین را می‌توان از پین ۶ گرفت. پیش از اتصال، جهت شماره‌گذاری هر دو هدر را تأیید کنید.

این مخزن فایل اجرایی پروگرامر، ISE، cloudflared یا تنظیمات VPN را توزیع نمی‌کند. برای اجرا از همان معماری userspace سیستم‌عامل استفاده کنید؛ ARM64 بودن کرنل الزاماً به معنی ۶۴ بیتی بودن userspace نیست.
