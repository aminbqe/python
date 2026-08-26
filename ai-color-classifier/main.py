import numpy as np
from PIL import Image

X = np.array([
    [0.90, 0.10, 0.15],  # red image
    [0.75, 0.20, 0.10],  # another red image

    [0.10, 0.85, 0.20],  # green image
    [0.25, 0.70, 0.15],  # another green image

    [0.10, 0.20, 0.90],  # blue image
    [0.20, 0.15, 0.75]   # another blue image
])

y = np.array([0, 0, 1, 1, 2, 2])

correct_class = 1

rang = np.random.default_rng(30)
weights = rang.normal(0,0.1,size=(3,3))
#print(weights)
bias = np.zeros(3)
epochs = 6100

for epoch in range(epochs):
    scores = X @ weights + bias

    zi = scores - np.max(scores,axis=1, keepdims=True)
    exp = np.exp(zi)
    probability = exp / np.sum(exp,axis=1, keepdims=True)

    correct = probability[np.arange(len(y)), y]

    sample_losses = -np.log(correct)
    loss = np.mean(sample_losses)

    if epoch % 100 == 0:
        print("Epoch:", epoch, "Loss:", loss)

    score_gradient = probability.copy()
    score_gradient[np.arange(len(y)), y] -= 1
    score_gradient /= len(y)

    weight_gradient = X.T @ score_gradient
    bias_gradient = np.sum(score_gradient, axis=0)

    learning_rate = 0.1

    weights -= learning_rate * weight_gradient
    bias -= learning_rate * bias_gradient

print(weights)
print(bias)





