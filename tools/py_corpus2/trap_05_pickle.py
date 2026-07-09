import pickle

def load_model(path):
    with open(path, "rb") as fh:
        return pickle.load(fh)
