import numpy as np

def mean(values):
    return float(np.mean(values)) if values else 0.0

def std_dev(values):
    val = float(np.std(values))
    return max(val, 1e-6)
