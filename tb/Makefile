SIM ?= verilator
TOPLEVEL_LANG ?= verilog
VERILOG_SOURCES += $(PWD)/../rtl/handwritten_pattern.sv
TOPLEVEL = handwritten_pattern
MODULE = Regex
EXTRA_ARGS += --trace

include $(shell cocotb-config --makefiles)/Makefile.sim