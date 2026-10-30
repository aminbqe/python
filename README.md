# Python Projects

A small collection of standalone Python experiments.

## Projects

| Folder | Main libraries | What it demonstrates |
| --- | --- | --- |
| `ai-color-classifier` | NumPy, Pillow | Trains a simple softmax RGB color classifier and predicts the dominant color of an image. |
| [`neural-networks`](neural-networks/) | NumPy; optional PyTorch, torchvision and Pillow | AI training, inference, transfer learning, ensembles and grouped validation with a normalized custom nonlinear activation. |
| `cnn-fpga` | NumPy, Pillow, VHDL | Trains a patch-based RGB segmenter in Python and exports fixed-point weights for FPGA inference. |
| `equalizer-simulation` | Turtle, NumPy | Visualizes a grid-based equalization/diffusion-style simulation using animated circles. |
| [`fpga-remote-lab`](fpga-remote-lab/) | FastAPI, WebSockets, pyserial, Verilog | Runs uploaded bitstreams on a physical AX309 FPGA through a Raspberry Pi, with a Persian web panel, password-protected uploads, and a Verilog project converter. [User guide](fpga-remote-lab/docs/USER_GUIDE.md) |

Each project folder has its own README with the algorithm, file roles, inputs, outputs, and run instructions.
