// FIXED TEMPLATE: 115200 baud, 8N1. See README for the binary protocol.
module lab_bridge(input wire clk, input wire rx, output wire tx,
 output reg reset=1, output reg [3:0] switches=0, buttons=0,
 output reg [31:0] input_a=0, input_b=0,
 input wire [3:0] leds, input wire [31:0] result);
 wire [7:0] received;
 wire valid;
 lab_uart_rx receiver(.clk(clk),.rx(rx),.data(received),.valid(valid));
 reg [3:0] position=0;
 reg [7:0] checksum=0;
 reg [7:0] payload[0:9];
 reg [23:0] timeout_ticks=0;
 reg [25:0] watchdog=0;
 reg [7:0] startup=0;
 reg session_seen=0;
 always @(posedge clk) begin
  if(startup!=255) begin startup<=startup+1'b1;reset<=1;end
  // Allow standalone LED designs before the first UART session.
  if(startup==254 && !session_seen) reset<=0;
  if(watchdog<49999999) watchdog<=watchdog+1'b1;
  else if(session_seen) begin reset<=1;switches<=0;buttons<=0;input_a<=0;input_b<=0;end
  if(position!=0) begin
   if(timeout_ticks==4999999) begin position<=0;timeout_ticks<=0;end
   else timeout_ticks<=timeout_ticks+1'b1;
  end
  if(valid) begin
   timeout_ticks<=0;
   if(position==0) begin
    if(received==8'ha5) begin position<=1;checksum<=8'ha5;end
   end else if(position==11) begin
    position<=0;
    if(received==checksum && startup==255) begin
     switches<=payload[0][3:0];buttons<=payload[0][7:4];reset<=payload[1][0];
     input_a<={payload[5],payload[4],payload[3],payload[2]};
     input_b<={payload[9],payload[8],payload[7],payload[6]};watchdog<=0;session_seen<=1;
    end
   end else begin
    payload[position-1]<=received;checksum<=checksum^received;position<=position+1'b1;
   end
  end
 end
 reg start=0;
 reg [7:0] outgoing=0;
 wire busy;
 lab_uart_tx transmitter(.clk(clk),.start(start),.data(outgoing),.tx(tx),.busy(busy));
 reg [22:0] period=0;
 reg [1:0] phase=0;
 reg [2:0] out_index=0;
 reg [7:0] out_frame[0:6];
 always @(posedge clk) begin
  start<=0;
  case(phase)
   0: if(period==4999999) begin
    period<=0;
    out_frame[0]<=8'h5a;out_frame[1]<={4'b0000,leds};
    out_frame[2]<=result[7:0];out_frame[3]<=result[15:8];
    out_frame[4]<=result[23:16];out_frame[5]<=result[31:24];
    out_frame[6]<=8'h5a^{4'b0000,leds}^result[7:0]^result[15:8]^result[23:16]^result[31:24];
    out_index<=0;phase<=1;
   end else period<=period+1'b1;
   1: if(!busy) begin outgoing<=out_frame[out_index];start<=1;phase<=2;end
   2: if(busy) phase<=3;
   3: if(!busy) begin
    if(out_index==6) phase<=0;
    else begin out_index<=out_index+1'b1;phase<=1;end
   end
  endcase
 end
endmodule
