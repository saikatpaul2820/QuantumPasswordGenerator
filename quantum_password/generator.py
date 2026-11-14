"""Password engine: turns a stream of random bits into secure passwords."""
from __future__ import annotations

import math
import string
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .quantum_source import BitSource

LOWERCASE = string.ascii_lowercase
UPPERCASE = string.ascii_uppercase
DIGITS = string.digits
DEFAULT_SYMBOLS = "!@#$%^&*()-_=+[]{};:,.<>?/"
AMBIGUOUS = "Il1|O0o"

MIN_LENGTH = 1
MAX_LENGTH = 1024
RECOMMENDED_MIN_LENGTH = 12


class PasswordConfigError(ValueError):
    """Raised for invalid password options."""


def _dedupe(chars: str) -> str:
    return "".join(dict.fromkeys(chars))


@dataclass(frozen=True)
class PasswordOptions:
    length: int = 16
    lowercase: bool = True
    uppercase: bool = True
    digits: bool = True
    symbols: bool = True
    custom_symbols: Optional[str] = None
    exclude_ambiguous: bool = False
    exclude_chars: str = ""

    def character_sets(self) -> List[str]:
        """Validate and return the active character sets (after exclusions)."""
        if isinstance(self.length, bool) or not isinstance(self.length, int):
            raise PasswordConfigError("Length must be an integer.")
        if not MIN_LENGTH <= self.length <= MAX_LENGTH:
            raise PasswordConfigError(f"Length must be between {MIN_LENGTH} and {MAX_LENGTH}.")

        symbol_pool = self.custom_symbols if self.custom_symbols is not None else DEFAULT_SYMBOLS
        for ch in symbol_pool + self.exclude_chars:
            if not ch.isprintable() or ch.isspace() or ord(ch) > 126:
                raise PasswordConfigError(
                    f"Unsupported character {ch!r}: use printable, non-space ASCII only."
                )

        removed = set(self.exclude_chars) | (set(AMBIGUOUS) if self.exclude_ambiguous else set())
        selected = [
            (self.lowercase, "lowercase letters", LOWERCASE),
            (self.uppercase, "uppercase letters", UPPERCASE),
            (self.digits, "digits", DIGITS),
            (self.symbols, "symbols", _dedupe(symbol_pool)),
        ]
        sets: List[str] = []
        for enabled, label, chars in selected:
            if not enabled:
                continue
            kept = "".join(c for c in chars if c not in removed)
            if not kept:
                raise PasswordConfigError(f"No {label} remain after applying exclusions.")
            sets.append(kept)

        if not sets:
            raise PasswordConfigError("Select at least one character set.")
        if self.length < len(sets):
            raise PasswordConfigError(
                f"Length {self.length} is too short to include one character from each of "
                f"the {len(sets)} selected sets."
            )
        return sets


def estimate_entropy_bits(options: PasswordOptions) -> float:
    """Approximate entropy (bits) = length * log2(alphabet size)."""
    alphabet = _dedupe("".join(options.character_sets()))
    return options.length * math.log2(len(alphabet))


class BitPool:
    """Buffers bits from a :class:`BitSource` and hands them out as integers."""

    def __init__(self, source: BitSource, chunk_bits: int = 1024) -> None:
        self.source = source
        self.chunk_bits = chunk_bits
        self._buf = ""
        self.bits_consumed = 0

    def take(self, n: int) -> int:
        if n == 0:
            return 0
        if len(self._buf) < n:
            self._buf += self.source.generate_bits(max(n - len(self._buf), self.chunk_bits))
        bits, self._buf = self._buf[:n], self._buf[n:]
        self.bits_consumed += n
        return int(bits, 2)


class PasswordGenerator:
    """Generates unbiased passwords from any :class:`BitSource`."""

    def __init__(self, source: BitSource) -> None:
        self.source = source
        self._pool = BitPool(source)

    @property
    def bits_consumed(self) -> int:
        return self._pool.bits_consumed

    def random_below(self, n: int) -> int:
        """Uniform integer in [0, n) via rejection sampling (no modulo bias)."""
        if n <= 0:
            raise ValueError("n must be positive")
        if n == 1:
            return 0
        k = (n - 1).bit_length()
        while True:
            value = self._pool.take(k)
            if value < n:
                return value

    def choice(self, chars: Sequence[str]) -> str:
        return chars[self.random_below(len(chars))]

    def shuffle(self, items: list) -> None:
        """Fisher-Yates shuffle driven by the bit source."""
        for i in range(len(items) - 1, 0, -1):
            j = self.random_below(i + 1)
            items[i], items[j] = items[j], items[i]

    def generate(self, options: Optional[PasswordOptions] = None) -> str:
        options = options or PasswordOptions()
        sets = options.character_sets()
        alphabet = _dedupe("".join(sets))

        chars = [self.choice(s) for s in sets]  # guarantee one of each selected set
        chars += [self.choice(alphabet) for _ in range(options.length - len(sets))]
        self.shuffle(chars)  # hide the positions of the guaranteed characters
        return "".join(chars)

    def generate_many(self, count: int, options: Optional[PasswordOptions] = None) -> List[str]:
        if count < 1:
            raise ValueError("count must be >= 1")
        return [self.generate(options) for _ in range(count)]
