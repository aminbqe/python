`timescale 1ns/1ps
module test_template;
 reg clk=0;
 always #10 clk=~clk;
 reg rx=1;
 wire tx;
 wire [3:0] led;
 lab_top dut(.clk(clk),.lab_rx(rx),.lab_tx(tx),.led_pins(led));
 reg [3:0] sw=0;
 wire [3:0] lamps;
 wire [31:0] result;
 user_logic adapter(.clk(clk),.reset(1'b0),.switches(sw),.buttons(4'b0),
  .input_a(32'b0),.input_b(32'b0),.leds(lamps),.result(result));
 integer i,j;
 reg [7:0] response[0:6];
 task send_byte(input [7:0] value);
  integer b;
  begin
   @(negedge clk);rx=0;repeat(434) @(negedge clk);
   for(b=0;b<8;b=b+1) begin rx=value[b];repeat(434) @(negedge clk);end
   rx=1;repeat(434) @(negedge clk);
  end
 endtask
 task receive_byte(output [7:0] value);
  integer b;
  begin
   @(negedge tx);repeat(651) @(posedge clk);
   for(b=0;b<8;b=b+1) begin value[b]=tx;repeat(434) @(posedge clk);end
   if(tx!==1'b1) $fatal(1,"Bad UART stop bit");
  end
 endtask
 initial begin
  for(i=0;i<8;i=i+1) begin
   sw=i;#1;
   if(lamps[0] !== ((i&1)^((i>>1)&1)^((i>>2)&1))) $fatal(1,"sum mismatch");
   if(lamps[1] !== (((i&1)+((i>>1)&1)+((i>>2)&1))>=2)) $fatal(1,"carry mismatch");
  end
  repeat(300) @(posedge clk);
  if(dut.reset!==0) $fatal(1,"Standalone startup reset stuck");
  // switches=3: a=1 b=1 cin=0; reset=0; numeric inputs=0.
  send_byte(8'ha5);send_byte(8'h03);send_byte(8'h00);
  for(j=0;j<8;j=j+1) send_byte(0);
  send_byte(8'ha6);
  repeat(20) @(posedge clk);
  if(dut.switches!==4'h3 || dut.reset!==0 || dut.leds!==4'h2)
   $fatal(1,"UART request not applied");
  if(led!==4'h2) $fatal(1,"Physical LED bus not connected");
  fork
   begin for(j=0;j<7;j=j+1) receive_byte(response[j]);end
   begin @(negedge clk);dut.bridge.period=4999999;end
  join
  if(response[0]!==8'h5a || response[1]!==8'h02 || response[6]!==8'h58)
   $fatal(1,"Telemetry frame mismatch");
  // An invalid checksum must not overwrite inputs.
  send_byte(8'ha5);send_byte(8'h00);send_byte(8'h00);
  for(j=0;j<8;j=j+1) send_byte(0);
  send_byte(8'h00);
  repeat(20) @(posedge clk);
  if(dut.switches!==4'h3) $fatal(1,"Bad checksum was accepted");
  @(negedge clk);dut.bridge.watchdog=49999999;
  repeat(3) @(posedge clk);#1;
  if(dut.reset!==1 || dut.switches!==0) $fatal(1,"Watchdog did not clear inputs");
  $display("PASS: all 8 full-adder inputs, UART RX/TX, checksum rejection, watchdog");
  $finish;
 end
 initial begin #20000000;$fatal(1,"Simulation timed out");end
endmodule
