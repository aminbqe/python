// 8N1 UART, idle high. start is accepted only when busy is low.
module lab_uart_tx #(
    parameter integer CLOCK_HZ = 50000000,
    parameter integer BAUD = 115200
)(
    input wire clk,
    input wire start,
    input wire [7:0] data,
    output wire tx,
    output reg busy = 1'b0
);
    localparam integer DIVISOR = CLOCK_HZ / BAUD;
    reg [31:0] ticks = 0;
    reg [3:0] bit_index = 0;
    reg [9:0] frame = 10'b1111111111;
    assign tx = busy ? frame[0] : 1'b1;
    always @(posedge clk) begin
        if (!busy) begin
            if (start) begin
                frame <= {1'b1, data, 1'b0};
                ticks <= DIVISOR - 1;
                bit_index <= 0;
                busy <= 1'b1;
            end
        end else if (ticks == 0) begin
            if (bit_index == 9) begin
                busy <= 1'b0;
            end else begin
                frame <= {1'b1, frame[9:1]};
                bit_index <= bit_index + 1'b1;
                ticks <= DIVISOR - 1;
            end
        end else ticks <= ticks - 1'b1;
    end
endmodule
