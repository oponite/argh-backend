import numpy as np

def mean(values):
    return float(np.mean(values)) if values else 0.0

def std_dev(values):
    val = float(np.std(values))
    return max(val, 1e-6)

def classify_z_score(z):
    az = abs(z)
    if az < 1:
        return "Noise: no identifiable edge"
    if az < 1.5:
        return "Mild edge: watch for in-game deviation"
    if az < 2:
        return "Solid edge: actionable for small initial entry"
    return "Strong disagreement"
