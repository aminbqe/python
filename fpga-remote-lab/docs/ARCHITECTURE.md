# Architecture and communication protocol

`server.py` is a FastAPI application with shared in-memory state. Browsers receive state and events over WebSocket. The `pi_agent.py` agent authenticates to `/agent` with a separate token, downloads the bitstream, checks its target device, and programs SRAM using `openFPGALoader`. UART periodically carries inputs and design responses.

## Main endpoints

| Path | Purpose |
| --- | --- |
| `GET /` or `/rasp/` | Web panel |
| `POST /api/upload` or `/rasp/api/upload` | Multipart upload with a `file` field and `X-Upload-Password` header |
| `/ws` or `/rasp/ws` | Browser WebSocket |
| `/agent` | Agent WebSocket with `Authorization: Bearer <AGENT_TOKEN>` |
| `/api/verilog/inspect` | Inspect source ports |
| `/api/verilog/files` | Retrieve generated source files |
| `/api/verilog/prepare-download` | Prepare a downloadable ZIP |

The agent should connect to a local root URL such as `http://127.0.0.1:8000`. The public Worker blocks agent access. For exact API models and routes, inspect the local `/docs` endpoint after starting the server.

## UART format

115200 baud, 8N1. All multibyte integers are little-endian.

Host request, 12 bytes:

```text
A5 | buttons[3:0]:switches[3:0] | reset(bit0)
   | input_a(4 bytes) | input_b(4 bytes) | XOR(previous 11 bytes)
```

FPGA response, 7 bytes:

```text
5A | leds[3:0] | result(4 bytes) | XOR(previous 6 bytes)
```

The agent sends requests approximately every 150 ms and converts responses into LED states and a numeric result. Incomplete packets and invalid checksums are rejected. UART becomes stale after approximately 1.5 seconds without a valid response. After the first valid host request, the template watchdog asserts reset if no valid request arrives for one second. User designs must honor reset.

The four LED bits drive P4, N5, P5, and M6. Seven-segment data is absent from the current packet. Supporting it requires coordinated changes to the template, protocol, and agent. The interface has a `digits` field, but the current agent does not sample these displays.

## Current limitations

- One agent and one shared session; no user queue, session ownership, or user accounts.
- USB presence, JTAG response, and UART freshness are checked separately. Each verifies a different part of the connection.
- The protocol includes `input_a` and `input_b`, but the current panel has no general-purpose controls for entering them. Switches and push buttons are the primary inputs for the website examples.
- Virtual controls supply values to user logic through the template; they do not physically press board switches.
- The password protects only the upload endpoint. Incorrect passwords return 401; a missing password hash returns 503. Other controls have no user authentication.
- Checking the `6slx9ftg256` device identifier does not establish safe pin assignments for arbitrary bitstreams. This version is intended for a trusted laboratory.
- State is not shared across multiple application workers or replicas. Run this version with one Uvicorn worker.
