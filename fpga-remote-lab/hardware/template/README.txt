AX309 LAB TEMPLATE v2
====================
Target: XC6SLX9-2FTG256C, 50 MHz clock on T8.

1. Inspect mapping.json and generated user_logic.v.
2. In ISE 14.7 add all .v files and lab.ucf; set lab_top as top.
   Alternatively run xtclsh build.tcl from this extracted folder.
3. Check build success, timing reports, pin report and warnings.
4. Upload lab_top.bit to the laboratory website.

EDIT: design.v (your original design).
DO NOT EDIT: UART/bridge/top/UCF files unless maintaining the lab itself.
Regenerate user_logic.v through the website to change port mappings.

IMPORTANT: A generated project is not a compiled or board-verified bitstream.
The converter supports basic Verilog input/output ports, ANSI and non-ANSI,
descending literal ranges up to 32 bits. No parameters, macros, inout,
interfaces, arrays or arbitrary SystemVerilog port types. A successful
conversion does not prove the user's HDL is synthesizable or functionally correct.

Reference wiring (verify connector orientation and board revision before use):
  FPGA J2 pin 3 / K16 TX -> 3.3V TTL USB-UART adapter RX
  FPGA J2 pin 5 / L16 RX <- 3.3V TTL USB-UART adapter TX
  FPGA J2 pin 1 GND      -> adapter GND
  USB-UART adapter USB  -> Raspberry Pi
Do not connect adapter power/VCC. Do not use RS232 voltage levels.
Verify connector orientation, board revision and 3.3V bank voltage first.
Reference: https://alinx.com/public/upload/file/AX309_User_Manual.pdf
JTAG programming cable remains a separate connection.

All four leds bits drive physical active-high user LEDs:
 leds[0] = P4, leds[1] = N5, leds[2] = P5, leds[3] = M6.
Source: ALINX AX309 manual, Part 12, Table 12-1.
Virtual inputs are not the physical board switches. Telemetry reports logic
signals, not an independent optical measurement of the LEDs.

UART PROTOCOL v1: 115200 baud, 8 data bits, no parity, one stop bit.
Host request, 12 bytes:
 A5, {buttons[3:0],switches[3:0]}, reset (bit0),
 input_a (4 bytes little endian), input_b (4 bytes little endian),
 XOR of previous 11 bytes.
Send a complete request periodically, at least every 500ms.
On power-up, reset is asserted for 255 clock cycles, then released so a
standalone blink/chaser design runs without UART wiring. After the first
valid UART request, a session watchdog is armed. Without a valid request for 1 second,
reset is asserted again and inputs are cleared. User design must honor reset.
An incomplete packet is discarded after approximately 100ms.

FPGA response, 7 bytes, approximately 10Hz:
 5A, leds[3:0] (upper bits zero), result (4 bytes little endian),
 XOR of previous 6 bytes.

Server hardware integration is implemented in pi_agent.py. Live telemetry
requires this UART template and matching wiring. See docs/INSTALL.fa.md
and docs/ARCHITECTURE.fa.md in the project repository.
