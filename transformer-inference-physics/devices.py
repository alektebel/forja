"""The world's second data module: accelerators.

A device is six measured constants, and every one of them is a pin the
course reads and never derives: the tensor-core peak in flops per
nanosecond at fp16, the memory bandwidth in bytes per nanosecond, the
achieved fractions of both (per-mille — real silicon delivers a fraction
of its data-sheet row, and the fraction is the world's to declare), the
kernel launch cost in ns, and the VRAM in bytes.

The three rows span the board: an 80 GiB `H_CLASS` box, a 40 GiB
`A_CLASS` box, and a 24 GiB `D_CLASS` desktop. Their ridge points differ
by an order of magnitude, which is exactly why the crossover stage needs
a device argument.

The dtype exponents live here: `FLOP_MULT` is the per-dtype multiple of
the fp16 peak (int8 and fp8 run the doubled-narrow compute; int4 rides
the int8 peak). All integers, no floats, no physics package.
"""

from collections import namedtuple

Device = namedtuple(
    "Device",
    ("name", "peak_flop_fp16", "bw_bytes_per_ns", "eff_compute",
     "eff_bandwidth", "launch_ns", "vram_bytes"))

# (name, peak flop/ns at fp16, bytes/ns, eff_c per-mille, eff_m per-mille,
#  launch_ns, vram_bytes)
_ROWS = (
    ("H_CLASS", 989000, 3350, 700, 800, 250, 85899345920),
    ("A_CLASS", 312000, 2039, 650, 750, 300, 42949672960),
    ("D_CLASS", 165000, 1008, 600, 900, 350, 25769803776),
)

DEVICES = dict((r[0], Device(*r)) for r in _ROWS)

DEVICE_NAMES = tuple(r[0] for r in _ROWS)

# every row is a per-mille multiplier of `peak_flop_fp16`; int4 rides the
# int8 row because the course's int4 is a packing rule, not an engine
FLOP_MULT = {"fp16": 1000, "fp8": 2000, "int8": 2000, "int4": 2000}
