module lab_uart_rx #(
 parameter integer CLOCK_HZ=50000000, parameter integer BAUD=115200
)(input wire clk, input wire rx, output reg [7:0] data=0, output reg valid=0);
 localparam integer DIV=CLOCK_HZ/BAUD;
 reg sync1=1, sync2=1;
 reg [31:0] ticks=0;
 reg [1:0] state=0;
 reg [2:0] bit_index=0;
 reg [7:0] bits=0;
 always @(posedge clk) begin
  sync1<=rx; sync2<=sync1; valid<=0;
  case(state)
   0: if(!sync2) begin ticks<=DIV/2-1;state<=1;end
   1: if(ticks!=0) ticks<=ticks-1;
      else if(!sync2) begin ticks<=DIV-1;bit_index<=0;state<=2;end
      else state<=0;
   2: if(ticks!=0) ticks<=ticks-1;
      else begin
       bits[bit_index]<=sync2; ticks<=DIV-1;
       if(bit_index==7) state<=3; else bit_index<=bit_index+1'b1;
      end
   3: if(ticks!=0) ticks<=ticks-1;
      else begin if(sync2) begin data<=bits;valid<=1;end state<=0;end
  endcase
 end
endmodule
