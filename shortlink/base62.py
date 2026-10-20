ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
BASE = len(ALPHABET)


def encode(value: int) -> str:
    if value <= 0:
        raise ValueError("ID must be positive")
    chars = []
    while value:
        value, remainder = divmod(value, BASE)
        chars.append(ALPHABET[remainder])
    return "".join(reversed(chars))


def decode(code: str) -> int:
    if not code or len(code) > 11 or (len(code) > 1 and code[0] == "0"):
        raise ValueError("Invalid short code")
    value = 0
    for char in code:
        if char not in ALPHABET:
            raise ValueError("Invalid short code")
        value = value * BASE + ALPHABET.index(char)
        if value > 2**63 - 1:
            raise ValueError("Invalid short code")
    if value <= 0:
        raise ValueError("Invalid short code")
    return value
