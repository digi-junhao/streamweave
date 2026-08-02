module handwritten_pattern(
    input clk,
    input reset,
    input in_valid,
    input [7:0] in_byte,
    output match
);

reg [1:0] state, next_state;

parameter Idle = 2'b00;
parameter G = 2'b01;
parameter GE = 2'b10;

always @(posedge clk, reset)
    if(reset)
        state <= Idle;

    else if(in_valid)
        state <= next_state;

    else
        state <= state;


always @(*)
begin

    next_state = state;
    case (state)

        Idle: next_state = (in_byte == "G") ? G : Idle;
        G: next_state = (in_byte == "E") ? GE : (in_byte == "G") ? G : Idle;
        GE: next_state = (in_byte != "G") ? G : Idle;
        default: next_state = Idle;

    endcase
end   

assign match = in_valid && (state == GE) && (in_byte=="T");

endmodule
