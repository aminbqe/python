# Website user guide

## 1. Prepare your Verilog design

Open the [converter](https://aminbagheri.com/fpga/), enter your Verilog source, inspect the ports, and select the top module. Map every input and output to the laboratory interface. For example, this is a one-bit full adder:

```verilog
module full_adder (
    input wire a, b, cin,
    output wire sum, cout
);
    assign sum = a ^ b ^ cin;
    assign cout = (a & b) | (a & cin) | (b & cin);
endmodule
```

| Port | Mapping |
| --- | --- |
| `a` | `switches:0` |
| `b` | `switches:1` |
| `cin` | `switches:2` |
| `sum` | `leds:0` |
| `cout` | `leds:1` |

For sequential designs, map clock and reset inputs to `clk` and `reset`. The converter supports basic ANSI and non-ANSI ports and descending literal ranges up to 32 bits. Parameters, macros, `inout`, and port arrays are unsupported. Successful conversion does not establish functional correctness or synthesizability.

## 2. Download the project and build a bitstream

Download and extract the ZIP. If downloading fails, use the interface's code display and copy controls. ZIP names contain the date, time, seconds, and milliseconds in the Tehran time zone.

In ISE 14.7, create a project targeting `XC6SLX9-2FTG256C`, add all generated `.v` files and `lab.ucf`, and set `lab_top` as the top module. Review pin assignments, timing reports, and errors before generating the bitstream. With ISE tools available in your environment, you can also run `xtclsh build.tcl` from the extracted directory.

- `design.v`: your original source; edit your circuit logic here.
- `user_logic.v`: generated port adapter; regenerate it through the converter when changing mappings.
- `lab_top.v`, `lab_bridge.v`, `lab_uart_rx.v`, `lab_uart_tx.v`, and `lab.ucf`: fixed laboratory infrastructure; ordinary design changes do not require editing these files.

## 3. Upload and run on the physical FPGA

1. Open the [laboratory panel](https://aminbagheri.com/rasp/).
2. Check the agent connection, USB programmer status, and FPGA detection status.
3. If a previous session is active, coordinate with its user before ending it. Only one design runs at a time.
4. Select `lab_top.bit`. The maximum size is 8 MiB.
5. Obtain the upload password from the administrator and enter it in the password field.
6. Click the button for programming and starting execution, then watch the session status and event console.

An incorrect password rejects the request before programming. The password is not embedded in the site source, and the application does not save it in localStorage. This password protects uploads; it does not act as a login for the entire panel.

## 4. Test the full adder

Once UART is live, toggle the first three virtual switches. A switch holds its state; a push button stays active only while held. These are software inputs to the design and do not necessarily represent the physical board switches.

| a | b | cin | LED1: sum | LED2: cout |
| --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 0 | 0 |
| 0 | 0 | 1 | 1 | 0 |
| 0 | 1 | 0 | 1 | 0 |
| 0 | 1 | 1 | 0 | 1 |
| 1 | 0 | 0 | 1 | 0 |
| 1 | 0 | 1 | 0 | 1 |
| 1 | 1 | 0 | 0 | 1 |
| 1 | 1 | 1 | 1 | 1 |

A lit LED in the interface means logical 1 in the template telemetry. The website does not independently measure the physical light. The reset control asserts the design reset. Ending a session makes the agent hold reset and release inputs.

## Understanding status indicators

- **USB connected:** the programmer was detected; this alone does not prove the FPGA responds.
- **XC6SLX9 detected:** the FPGA responded through JTAG.
- **UART live:** valid template packets are arriving, enabling live telemetry.
- **UART disconnected / no design data:** the FPGA may be programmed, but the template or serial connection is unavailable.
- The graphical seven-segment displays are not currently supported as live outputs by the UART template.

The event console shows application messages, programming output, and agent errors. It is not a general Linux terminal or a raw interactive UART terminal. The deployed interface uses Persian labels; the status names above describe their English meanings.
