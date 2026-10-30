# Run in this directory: xtclsh build.tcl (ISE 14.7)
project new ax309_lab.ise
project set family Spartan6
project set device xc6slx9
project set package ftg256
project set speed -2
foreach source {design.v user_logic.v lab_uart_tx.v lab_uart_rx.v lab_bridge.v lab_top.v lab.ucf} {
 xfile add $source
}
project set top lab_top
process run "Generate Programming File"
project close
