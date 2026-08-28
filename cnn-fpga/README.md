# CNN–FPGA Color-Segmentation Project

This project trains a compact NumPy neural network in Python, exports its trained parameters as synthesizable VHDL constants, and evaluates one 5 x 5 RGB patch at a time in FPGA logic.

Despite the folder name, the trained model is a **patch classifier** rather than a conventional convolution layer: Python flattens each 5 x 5 patch into 100 features, then evaluates 100 -> 32 -> 4. The FPGA core implements that same dense network in fixed point. A camera/image wrapper supplies overlapping patches, so the complete system performs per-pixel segmentation.

## Repository layout

| Path | Purpose |
| --- | --- |
| train.py | Generates synthetic labeled images, trains the float model, and creates a mask/overlay for test2.jpg. |
| segmentation_model.npz | Current trained NumPy weights. It is the source of the committed VHDL weight package. |
| test2.jpg | Example image used by the Python inference demonstration. |
| fpga/export_weights.py | Converts the .npz tensors into signed fixed-point VHDL constants. |
| fpga/cnn_weights_pkg.vhd | Generated constants for the current trained model. Add this package before the core. |
| fpga/patch_classifier.vhd | Board-independent inference core. |

Generated images, virtual environments, IDE settings, caches, and FPGA tool build products are excluded by .gitignore.

## 1. Run the Python model

Use Python 3.10+ in this folder:

\`\`\`powershell
cd cnn-fpga
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python train.py
\`\`\`

train.py uses a fixed random seed, builds 150 synthetic 32 x 32 RGB training images, and trains a single-hidden-layer ReLU network. Its classes are:

| Index | Meaning |
| --- | --- |
| 0 | background |
| 1 | red region |
| 2 | green region |
| 3 | blue region |

The script overwrites segmentation_model.npz with newly trained float parameters and writes downloaded_predicted_mask.png plus downloaded_overlay.png. These diagnostic images are not committed.

## 2. Network contract

For every pixel, Python obtains the centered 5 x 5 neighborhood. Each patch pixel contributes four normalized features in this exact order:

\`\`\`text
R, G, B, brightness
\`\`\`

Rows are scanned top-to-bottom and pixels left-to-right, giving 25 x 4 = 100 inputs. The model calculation is:

\`\`\`text
hidden = ReLU(features @ weights_1 + bias_1)    # 100 -> 32
scores = hidden @ weights_2 + bias_2            # 32 -> 4
class  = argmax(scores)
\`\`\`

Python uses floating point during training. The FPGA does inference only; it does not perform back-propagation or update weights.

## 3. Export weights for VHDL

After every training run, regenerate the package from the matching model:

\`\`\`powershell
python fpga\export_weights.py
\`\`\`

The exporter reads segmentation_model.npz and writes fpga/cnn_weights_pkg.vhd. Commit the model archive and the generated package together. This keeps the Python and FPGA implementations traceable to the same trained network.

### Fixed-point format

| Quantity | Format | Meaning |
| --- | --- | --- |
| Input feature | signed Q8 | normalized 1.0 is integer 256 |
| Weight | signed Q12 in 16 bits | round(float_weight * 4096) |
| Bias | signed Q12 in 32 bits | aligned to Q20 before accumulation |
| First-layer product/accumulator | Q20 / signed 40-bit accumulator | Q8 x Q12 with headroom |
| ReLU output | Q8 in 16 bits | Q20 shifted right 12; negatives become zero |

The numerical result is quantized, so bit-for-bit equality with Python float scores is not expected. The intended check is that both implementations choose the same argmax class for representative patches.

## 4. Add the core to an FPGA project

In Vivado, Quartus, or another VHDL-2008-capable tool, add these files in order:

1. fpga/cnn_weights_pkg.vhd
2. fpga/patch_classifier.vhd
3. Your board-specific top level and constraints

The core entity is patch_classifier:

| Signal | Direction | Description |
| --- | --- | --- |
| clk | in | Core clock. |
| rst | in | Synchronous active-high reset. |
| patch_start | in | Pulse high for one clock to begin a patch. |
| feature_valid | in | High when feature_value is valid. |
| feature_value | in | Signed 16-bit Q8 feature. |
| feature_ready | out | High only while the core accepts the next feature. |
| result_valid | out | One-clock pulse when the prediction is available. |
| result_class | out | 2-bit class: 0 background, 1 red, 2 green, 3 blue. |

### Transaction timing

1. Assert patch_start for one clock while the core is idle.
2. Wait for feature_ready = '1'.
3. Send exactly 100 features. On every accepted transfer, set feature_valid = '1' and drive the next Q8 value on feature_value.
4. The core accumulates hidden neurons, evaluates the four scores, then pulses result_valid after the last feature plus its internal 32 hidden-output cycles.
5. Sample result_class on that pulse. Start another patch only after the core returns to idle.

## 5. Build a complete image pipeline

patch_classifier.vhd evaluates one patch. A camera or frame-buffer wrapper converts an image stream into patches:

\`\`\`text
camera / frame buffer
        -> RGB pixel stream
        -> four line buffers + 5 x 5 shift-register window
        -> normalize R,G,B and calculate brightness
        -> serialize 100 Q8 features
        -> patch_classifier
        -> result-class stream / color overlay / memory writer
\`\`\`

Use four previous-line buffers and five pixel registers per line to form a centered 5 x 5 window from a raster stream. At image borders, match Python's edge-padding rule in train.py; otherwise predictions can differ. For each pixel channel use the same normalized range: q8 = round(channel_8bit * 256 / 255). Calculate brightness exactly as Python does before quantizing it, then send the feature order defined above.

The core processes one patch at a time. A high-resolution video design may need buffering and/or parallel cores to reach frame rate. Use synthesis reports to decide whether constant multipliers should use logic, DSP blocks, or a time-multiplexed MAC architecture.

## 6. Verify Python and FPGA agree

Use a VHDL testbench that feeds known patches in the same order and Q8 format as Python. For each patch, record the float scores/class in Python and compare FPGA result_class with Python argmax. Test background, red, green, blue, dark, bright, and border patches. If results differ, first check feature order, Q8 conversion/rounding, edge padding, and whether cnn_weights_pkg.vhd was regenerated from the current segmentation_model.npz.

## Regeneration checklist

\`\`\`text
change model or training data
        -> python train.py
        -> python fpga\export_weights.py
        -> simulate VHDL against Python reference patches
        -> synthesize with regenerated cnn_weights_pkg.vhd
        -> program FPGA and validate image output
\`\`\`
