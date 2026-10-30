# Madar — Remote FPGA Lab

Run digital designs on a **physical ALINX AX309 / Spartan-6 XC6SLX9-2FTG256C FPGA**, using a Python server on a Raspberry Pi and a Persian web interface.

- [Live laboratory panel](https://aminbagheri.com/rasp/)
- [Verilog project converter](https://aminbagheri.com/fpga/)
- [Website user guide and full-adder example](docs/USER_GUIDE.md)
- [Installation and password setup](docs/INSTALL.md)
- [Architecture, protocol, and limitations](docs/ARCHITECTURE.md)
- [Public deployment and troubleshooting](docs/DEPLOYMENT.md)

## Workflow

Users prepare and compile their projects, then deliver them to the administrator through an agreed channel. The administrator keeps the upload password private and programs the board. Users test their design in the panel after confirmation. The site currently has no submission or approval queue. See the [step-by-step user guide](docs/USER_GUIDE.md) for the separate user and administrator tasks.

```text
User Verilog -> converter and port mapping -> Verilog/UCF project
-> build lab_top.bit with ISE on the user's computer
-> password-protected upload -> FastAPI -> Raspberry Pi agent -> JTAG -> FPGA
                                                   <-> UART
                                  browser <- WebSocket telemetry
```

The converter generates project sources; the Spartan-6 bitstream is built outside the website. Live monitoring requires a bitstream containing the laboratory's UART template. An ordinary bitstream may run on the board, but the programming USB connection alone cannot report its LED states.

## Source files

| Path | Purpose |
| --- | --- |
| `server.py` | API, WebSockets, shared session management, and bitstream delivery |
| `converter.py` | Verilog port inspection and ZIP project generation |
| `pi_agent.py` | JTAG/UART agent, hardware detection, and SRAM programming |
| `upload_auth.py` | Upload password hashing and verification using PBKDF2-SHA256 |
| `static/` | Persian laboratory panel and converter interface |
| `hardware/template/` | Fixed Verilog template, UCF constraints, and ISE build script |
| `hardware/test_template.v` | Template protocol testbench |
| `deploy/` | systemd services and standalone cPanel converter package |
| `deploy/cloudflare/` | Worker for `/rasp/`, tests, and deployment utility |
| `tunnel_dns.py` | Optional local DNS relay for proxy-based networks |

## Development quick start

Requires Python 3.10 or later. Run these commands from this project directory:

```sh
python -m venv .venv
# Linux:
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn server:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/rasp/`. Hardware controls remain disabled without an agent. Uploads require `UPLOAD_PASSWORD_HASH`; see the [installation guide](docs/INSTALL.md).

## Tests

```sh
pip install -r requirements-dev.txt
python -m unittest -v test_converter test_server test_pi_agent
node --test deploy/cloudflare/rasp-worker.test.mjs
node deploy/test_cpanel.cjs
node --check static/app.js
```

The Python tests use a mock hardware agent and do not program a physical board. Worker tests require Node.js with `Request` and `Response` support. Physical hardware validation is a separate step.

## Current scope and rights

Documented version: October 30, 2026. This version supports one board and one shared session. The password protects uploads only; viewing and other controls do not have user accounts. Seven-segment displays appear in the interface, but the current hardware protocol carries only LED states and a 32-bit result.

Operational passwords, tokens, password hashes, DNS backups, VPN configurations, and private bitstreams are excluded. The published agent reads the programmer's serial number from an environment variable.

Copyright © Mehdi Hadi Nejad and Amin Bagheri. All rights reserved. No separate open-source license is granted for this project.
