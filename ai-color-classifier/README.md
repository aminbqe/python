# 🎨 Tiny RGB Color Classifier

A small, from-scratch NumPy project that learns to classify images as **red**, **green**, or **blue** using their average RGB color. No machine-learning framework required. 🧠

## ✨ What it does

- 🧪 Trains a three-class linear classifier on sample RGB feature vectors
- 📉 Uses softmax and cross-entropy loss with gradient descent
- 💾 Prints the learned weights and bias values
- 🖼️ Loads `test.png`, extracts its mean RGB features, and predicts its dominant color class

## 📁 Files

- `main.py` — trains the classifier and prints the learned parameters
- `trained.py` — runs inference with the saved trained parameters
- `test.png` — image used for the prediction example

## 🚀 Run it

Install the dependencies:

```bash
pip install numpy pillow
```

Train the model:

```bash
python main.py
```

Classify the included image:

```bash
python trained.py
```

## 🧩 How the prediction works

The image is normalized to RGB values between 0 and 1. Its average red, green, and blue channel values form a three-element feature vector. The saved linear model scores each color class and returns the label with the highest score.

> [!NOTE]
> This is an educational classifier built for simple color-dominance examples. It is not intended for general image recognition.
