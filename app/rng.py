import random

def get_rng(seed: int | None = None):
    return random.Random(seed)