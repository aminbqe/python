// FIXED TEMPLATE — do not change pins or bridge connections.
module lab_top(input wire clk, input wire lab_rx, output wire lab_tx,
 output wire [3:0] led_pins);
 wire reset;
 wire [3:0] switches,buttons,leds;
 wire [31:0] input_a,input_b,result;
 lab_bridge bridge(.clk(clk),.rx(lab_rx),.tx(lab_tx),.reset(reset),
  .switches(switches),.buttons(buttons),.input_a(input_a),.input_b(input_b),
  .leds(leds),.result(result));
 user_logic user_design(.clk(clk),.reset(reset),.switches(switches),.buttons(buttons),
  .input_a(input_a),.input_b(input_b),.leds(leds),.result(result));
 // AX309 user LEDs are active-high: bit 0..3 = P4, N5, P5, M6.
 assign led_pins=leds;
endmodule
