# Raspberry Pi installation

## Requirements

Use Raspberry Pi OS with Python 3.10+, UART access, an AX309 board, and an `openFPGALoader`-compatible programmer. The current agent uses an FT232H cable with the `digilent_hs2` driver. Adjust `pi_agent.py` if using a different cable.

```sh
git clone https://github.com/aminbqe/python.git
cp -r python/fpga-remote-lab ~/fpga-sim
cd ~/fpga-sim
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install `openFPGALoader` separately using a package suitable for your OS and architecture. The service user needs USB and UART permissions. On Raspberry Pi OS, use `raspi-config` to disable the serial console and enable UART hardware. Configure access groups and udev rules for your system; installing Python packages does not grant USB access.

## Create private configuration

Run the following on Linux to create a new `.env`. It stops if the file already exists, prompts for the password without displaying it, and stores only its hash:

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

Find your FTDI serial number using USB inspection tools or your cable configuration. The published agent does not depend on the administrator's private cable identifier. To change an existing upload password, generate a hash with `upload_auth.hash_password`, replace only `UPLOAD_PASSWORD_HASH` in `.env`, and restart the server service. Keep the agent token unless you intend to rotate it.

Uvicorn does not automatically load this `.env`; the systemd units load it through `EnvironmentFile`. For manual execution, load it in each Bash terminal:

```sh
set -a
. ./.env
set +a
# First terminal:
uvicorn server:app --host 127.0.0.1 --port 8000
# Second terminal, after loading the same .env:
python pi_agent.py
```

## Automatic startup

```sh
mkdir -p ~/.config/systemd/user
cp deploy/fpga-lab.service deploy/fpga-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now fpga-lab fpga-agent
sudo loginctl enable-linger "$USER"
journalctl --user -u fpga-lab -u fpga-agent -n 60
```

These units expect the project at `~/fpga-sim`. Update their paths if necessary. The example server listens on `0.0.0.0:8000`; for a tunnel-only installation, you can bind it to `127.0.0.1`.

## Wiring

USB/JTAG programming and UART input/output are separate connections. The Raspberry Pi and FPGA need a common ground and 3.3 V logic levels. Do not connect a power pin just to establish UART communication, and do not apply RS232 signal levels to GPIO.

The current `lab.ucf` assigns TX/RX to K16/L16. Verify the corresponding header pins against the schematic and numbering for your board revision. A printed connector name such as J2 or the connector's appearance is insufficient to identify a signal. Connect each transmitter to the other device's receiver. Raspberry Pi physical pin 8 is GPIO14/TXD, pin 10 is GPIO15/RXD, and pin 6 can provide ground. Confirm the numbering orientation on both headers before connecting them.

This repository does not distribute programmer binaries, ISE, cloudflared, or VPN configurations. Match executables to the OS userspace architecture; an ARM64 kernel does not necessarily imply a 64-bit userspace.
