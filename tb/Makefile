SIM ?= verilator
TOPLEVEL_LANG ?= verilog
VERILOG_SOURCES += $(PWD)/../rtl/blinky.sv
TOPLEVEL = blinky
MODULE = test1
EXTRA_ARGS += --trace
	include $(shell cocotb-config --makefiles)/Makefile.sim
