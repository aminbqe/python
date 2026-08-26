# 🎨 Tiny RGB Color Classifier

A small, from-scratch NumPy project that learns to classify images as **red**, **green**, or **blue** using their average RGB color. No machine-learning framework required. 🧠

## ✨ What it does

- 🧪 Trains a three-class linear classifier on sample RGB feature vectors
- 📉 Uses softmax and cross-entropy loss with gradient descent
- 💾 Prints the learned weights and bias values
- 🖼️ Loads `test.png`, extracts its mean RGB features, and predicts its dominant color class

## 🧠 Model idea

The classifier reduces every image to three normalized values:

```text
[mean red, mean green, mean blue]
```

For example, an image with mostly green pixels may become a feature vector similar to:

```text
[0.24, 0.29, 0.24]
```

The model has one score for each class—`red`, `green`, and `blue`. It calculates the scores with a linear layer:

```text
scores = features × weights + bias
```

`weights` is a 3×3 matrix: each input color channel contributes to each of the three output classes. `bias` is a three-value offset, one for each class.

## 🧪 Training data

`main.py` uses six hand-written examples rather than an image dataset:

| Class | RGB feature examples | Label |
| --- | --- | ---: |
| Red | `[0.90, 0.10, 0.15]`, `[0.75, 0.20, 0.10]` | `0` |
| Green | `[0.10, 0.85, 0.20]`, `[0.25, 0.70, 0.15]` | `1` |
| Blue | `[0.10, 0.20, 0.90]`, `[0.20, 0.15, 0.75]` | `2` |

The random generator uses a fixed seed (`30`), so training begins from the same initial weights every time and produces reproducible output.

## 🔄 Training loop, step by step

For each of the 6,100 epochs, `main.py` performs these steps:

1. **Linear scores** — computes one raw score per class for every training example.
2. **Stable softmax** — subtracts each row’s largest score before calling `exp`. This avoids numerical overflow while converting scores into probabilities that sum to 1.
3. **Cross-entropy loss** — selects the probability assigned to the correct class and calculates `-log(probability)`. A confident correct prediction has a small loss.
4. **Gradients** — begins with `probability - one_hot_label`, then calculates how much the weights and bias caused the error.
5. **Gradient descent** — updates the parameters with a learning rate of `0.1`:

   ```text
   weights = weights - learning_rate × weight_gradient
   bias    = bias - learning_rate × bias_gradient
   ```

The script prints the loss every 100 epochs. The decreasing loss shows that the tiny model is fitting the supplied examples.

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

## 🔍 Inference with `trained.py`

`trained.py` contains the final weights and bias printed by `main.py`. It opens `test.png` from the same directory as the script, then:

1. Converts the image to RGB.
2. Normalizes pixel values from `0–255` to `0–1`.
3. Averages the pixels across the image width and height.
4. Calculates class scores using the saved linear model.
5. Uses `numpy.argmax` to return the class with the highest score.

The script prints both the extracted feature vector and the final color prediction.

## ⚙️ Important limitations

- The model learns only from six synthetic RGB examples.
- It looks at average color only; it does not use shapes, edges, or object features.
- It can identify the dominant red/green/blue tendency, but it is not a general-purpose image classifier.
- The weights in `trained.py` are saved manually from the current training output; retraining with changed data requires copying the new values if you want inference to use them.

> [!NOTE]
> This is an educational classifier built for simple color-dominance examples. It is not intended for general image recognition.
