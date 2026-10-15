def load(path):
    # ruleid: except-returns-empty
    try:
        return open(path).read().splitlines()
    except OSError:
        return []


def parse(text):
    # ruleid: except-returns-empty
    try:
        return int(text)
    except:
        return None


def strict(path):
    # ok: except-returns-empty
    return open(path).read()


def handled(path):
    # ok: except-returns-empty
    try:
        return open(path).read()
    except FileNotFoundError:
        raise SystemExit(2)
