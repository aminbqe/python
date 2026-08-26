from PIL import Image
import numpy as np
from pathlib import Path

weights = np.array([
    [ 5.68534722, -2.89805547, -2.65248818],
    [-3.06171771,  6.03936930, -2.79128314],
    [-2.97926621, -2.76511564,  5.79995677]
])

bias = np.array([-0.06176913, 0.09294680, -0.03117767])

picture = Image.open(Path(__file__).with_name("test.png")).convert("RGB")
pixels = np.asarray(picture, dtype=np.float32) / 255.0
picture_features = pixels.mean(axis=(0, 1))

picture_scores = picture_features @ weights + bias
prediction = np.argmax(picture_scores)

class_names = ["red", "green", "blue"]

print("Features:", picture_features)
print("Prediction:", class_names[prediction])
