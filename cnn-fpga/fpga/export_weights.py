"""Convert the NumPy model saved by main.py into fixed-point VHDL constants."""

from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / "segmentation_model.npz"
OUTPUT = Path(__file__).resolve().parent / "cnn_weights_pkg.vhd"
WEIGHT_SCALE = 1 << 12  # Q12


def q_weight(values):
    """Quantize float weights to signed 16-bit Q12."""
    return np.clip(np.rint(values * WEIGHT_SCALE), -32768, 32767).astype(np.int16)


def vhdl_vector(values, width):
    return ", ".join(f"to_signed({int(value)}, {width})" for value in values)


model = np.load(MODEL)
w1 = q_weight(model["weights_1"])
w2 = q_weight(model["weights_2"])

# Biases use Q12.  The VHDL engine shifts them left by 8 to align with
# feature(Q8) * weight(Q12), which is accumulated as Q20.
b1 = np.rint(model["bias_1"] * WEIGHT_SCALE).astype(np.int32)
b2 = np.rint(model["bias_2"] * WEIGHT_SCALE).astype(np.int32)

lines = [
    "library ieee;",
    "use ieee.std_logic_1164.all;",
    "use ieee.numeric_std.all;",
    "",
    "package cnn_weights_pkg is",
    "    constant FEATURE_COUNT : natural := 100;",
    "    constant HIDDEN_COUNT  : natural := 32;",
    "    constant CLASS_COUNT   : natural := 4;",
    "    subtype weight_t is signed(15 downto 0);",
    "    subtype bias_t   is signed(31 downto 0);",
    "    type weight_1_t is array (0 to FEATURE_COUNT - 1, 0 to HIDDEN_COUNT - 1) of weight_t;",
    "    type bias_1_t   is array (0 to HIDDEN_COUNT - 1) of bias_t;",
    "    type weight_2_t is array (0 to HIDDEN_COUNT - 1, 0 to CLASS_COUNT - 1) of weight_t;",
    "    type bias_2_t   is array (0 to CLASS_COUNT - 1) of bias_t;",
    "",
    "    constant WEIGHTS_1 : weight_1_t := (",
]
lines.extend(f"        {i} => ({vhdl_vector(row, 16)}){',' if i < 99 else ''}" for i, row in enumerate(w1))
lines.append("    );")
lines.append(f"    constant BIAS_1 : bias_1_t := ({vhdl_vector(b1, 32)});")
lines.append("    constant WEIGHTS_2 : weight_2_t := (")
lines.extend(f"        {i} => ({vhdl_vector(row, 16)}){',' if i < 31 else ''}" for i, row in enumerate(w2))
lines.append("    );")
lines.append(f"    constant BIAS_2 : bias_2_t := ({vhdl_vector(b2, 32)});")
lines.append("end package;")
OUTPUT.write_text("\n".join(lines) + "\n", encoding="ascii")
print(f"Wrote {OUTPUT}")
