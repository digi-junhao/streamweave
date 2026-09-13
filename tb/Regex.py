"""
Testbench for handwritten_pattern -- streaming "GET" matcher.

A golden model computes expected match positions, so the tests are not limited
to strings whose answers were worked out by hand. Covers Steps 6-7 of the
project guide: the zoo, then the same zoo under bursty in_valid.
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

ALPHABET = "GETX "
CLK_PERIOD_NS = 10


# --------------------------------------------------------------- golden model
def golden(text):
    """Expected (index, char) pairs where match should be high.

    Mirrors the RTL: match is combinational on the CURRENT state and the
    CURRENT byte, so it is evaluated before the state transition.
    """
    IDLE, G, GE = 0, 1, 2
    state, hits = IDLE, []
    for i, ch in enumerate(text):
        if state == GE and ch == "T":
            hits.append((i, ch))
        if state == IDLE:
            state = G if ch == "G" else IDLE
        elif state == G:
            state = GE if ch == "E" else (G if ch == "G" else IDLE)
        elif state == GE:
            state = G if ch == "G" else IDLE
    return hits


# -------------------------------------------------------------- test plumbing
def read_match(dut):
    """Read match as a clean 0/1, failing loudly if it is x or z."""
    v = dut.match.value
    if not v.is_resolvable:
        raise AssertionError(f"match is unresolvable ({v!s}) -- expected 0 or 1")
    return int(v)


async def reset_dut(dut):
    dut.reset.value = 1
    dut.in_valid.value = 0
    dut.in_byte.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.reset.value = 0
    await Timer(1, unit="ns")


async def setup(dut):
    """Start a clock, then reset.

    Each test starts its own clock on purpose: cocotb cancels tasks started by
    a test when that test ends, so a clock cannot be shared between tests.
    """
    cocotb.start_soon(Clock(dut.clk, CLK_PERIOD_NS, unit="ns").start())
    await reset_dut(dut)


async def feed(dut, text, gap_prob=0.0):
    """Drive text one byte per valid cycle. Returns observed match positions.

    gap_prob: chance of an idle cycle (in_valid low) before each byte. During a
    gap in_byte is scrambled -- if the DUT reads it while in_valid is low, that
    is the bug being hunted.
    """
    hits = []
    for i, ch in enumerate(text):
        while random.random() < gap_prob:
            dut.in_valid.value = 0
            dut.in_byte.value = random.randrange(256)
            await Timer(1, unit="ns")
            assert read_match(dut) == 0, (
                f"match asserted during an idle cycle, before byte {i} of {text!r}"
            )
            await RisingEdge(dut.clk)

        dut.in_valid.value = 1
        dut.in_byte.value = ord(ch)
        await Timer(1, unit="ns")           # combinational match settles
        if read_match(dut):
            hits.append((i, ch))
        await RisingEdge(dut.clk)           # state advances here

    dut.in_valid.value = 0
    dut.in_byte.value = 0
    return hits


async def check(dut, text, gap_prob=0.0, note=""):
    await reset_dut(dut)
    got = await feed(dut, text, gap_prob)
    want = golden(text)
    assert got == want, (
        f"{note}fed {text!r} (gap_prob={gap_prob}): expected {want}, got {got}"
    )


# ------------------------------------------------------------------- the zoo
ZOO = [
    ("",        "empty input"),
    ("G",       "partial: one byte"),
    ("GE",      "partial: two bytes, no match yet"),
    ("GET",     "the basic match"),
    ("GEX",     "near miss on the third byte"),
    ("GX",      "near miss on the second byte"),
    ("XXGET",   "match after a junk prefix"),
    ("GETXX",   "match then junk"),
    ("GGET",    "overlap: repeated G must not drop to Idle"),
    ("GGGET",   "overlap: three Gs in a row"),
    ("GEGET",   "overlap from state GE -- the bug that hid from 4 of 5 tests"),
    ("GETGET",  "two separate matches"),
    ("GETGETG", "two matches then a trailing partial"),
    ("GEGEGET", "repeated near-misses before a real match"),
    ("TEG",     "the bytes of GET in the wrong order"),
    ("G E T",   "correct bytes with spaces -- must not match"),
    ("get",     "lowercase -- ASCII is case sensitive, must not match"),
]


# ------------------------------------------------------------------ the tests
@cocotb.test()
async def test_zoo_continuous(dut):
    """Step 6: every hand-picked case, in_valid high every cycle."""
    await setup(dut)
    for text, note in ZOO:
        await check(dut, text, gap_prob=0.0, note=f"[{note}] ")
    dut._log.info(f"zoo passed: {len(ZOO)} cases, continuous input")


@cocotb.test()
async def test_zoo_bursty(dut):
    """Step 7: same zoo at gap_prob=0.3. Verdicts must be identical."""
    await setup(dut)
    for text, note in ZOO:
        await check(dut, text, gap_prob=0.3, note=f"[{note}, bursty] ")
    dut._log.info(f"zoo passed: {len(ZOO)} cases, bursty input")


@cocotb.test()
async def test_random_continuous(dut):
    """Random strings against the golden model -- finds what the zoo missed."""
    await setup(dut)
    for _ in range(60):
        n = random.randrange(1, 15)
        text = "".join(random.choice(ALPHABET) for _ in range(n))
        await check(dut, text, gap_prob=0.0, note="[random] ")


@cocotb.test()
async def test_random_bursty(dut):
    """Random strings with random gaps -- both hard cases combined."""
    await setup(dut)
    for _ in range(60):
        n = random.randrange(1, 15)
        text = "".join(random.choice(ALPHABET) for _ in range(n))
        await check(dut, text, gap_prob=0.3, note="[random bursty] ")


@cocotb.test()
async def test_state_holds_across_long_gap(dut):
    """A gap of any length must be invisible: GE + 20 idle cycles + T matches."""
    await setup(dut)

    for ch in "GE":                        # walk to state GE
        dut.in_valid.value = 1
        dut.in_byte.value = ord(ch)
        await RisingEdge(dut.clk)

    dut.in_valid.value = 0
    for _ in range(20):                    # long idle stretch, garbage on the bus
        dut.in_byte.value = random.randrange(256)
        await Timer(1, unit="ns")
        assert read_match(dut) == 0, "match fired during a long idle gap"
        await RisingEdge(dut.clk)

    dut.in_valid.value = 1                 # the T finally arrives
    dut.in_byte.value = ord("T")
    await Timer(1, unit="ns")
    assert read_match(dut) == 1, "state did not hold across the gap"

    await RisingEdge(dut.clk)
    dut.in_valid.value = 0


@cocotb.test()
async def test_reset_clears_progress(dut):
    """Reset mid-pattern must discard partial progress."""
    await setup(dut)

    for ch in "GE":                        # walk to state GE
        dut.in_valid.value = 1
        dut.in_byte.value = ord(ch)
        await RisingEdge(dut.clk)

    await reset_dut(dut)                   # wipe it

    dut.in_valid.value = 1                 # a bare T must not match now
    dut.in_byte.value = ord("T")
    await Timer(1, unit="ns")
    assert read_match(dut) == 0, "reset did not clear the GE state"

    await RisingEdge(dut.clk)
    dut.in_valid.value = 0