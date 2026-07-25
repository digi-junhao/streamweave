SIM ?= verilator
TOPLEVEL_LANG ?= verilog
VERILOG_SOURCES += $(PWD)/../rtl/adder.sv
TOPLEVEL = adder
MODULE = test_adder
EXTRA_ARGS += --trace
	include $(shell cocotb-config --makefiles)/Makefile.sim
