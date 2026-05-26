import hashlib


def md5_of_string(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest()


def md5_of_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
