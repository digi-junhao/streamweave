import random, cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def adder_random(dut):
    for _ in range(200):
        a, b = random.randint(0,255), random.randint(0,255)
        dut.a.value, dut.b.value = a, b
        await Timer(1, units="ns")
        assert int(dut.y.value) == a + b
