import numpy as np


def write_array(array, filename, dtype=np.float64):
    array = array.astype(dtype)
    array.tofile(filename)


def read_array(filename, dtype=np.float64):
    return np.fromfile(filename, dtype=dtype)

