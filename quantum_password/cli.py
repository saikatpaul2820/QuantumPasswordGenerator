"""Command-line interface: ``python -m quantum_password`` or ``qpass``."""
from __future__ import annotations

import argparse
import logging
import sys
import warnings
from typing import List, Optional

from . import __version__
from .generator import (
    RECOMMENDED_MIN_LENGTH,
    PasswordConfigError,
    PasswordGenerator,
    PasswordOptions,
    estimate_entropy_bits,
)
from .quantum_source import (
    MAX_QUBITS,
    HybridBitSource,
    QuantumBackendError,
    QuantumBitSource,
    create_bit_source,
)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="qpass",
        description="Generate passwords from measured quantum randomness (Qiskit).",
        epilog="Examples:\n  qpass -l 24\n  qpass -l 16 --no-symbols -n 5\n"
        "  qpass -l 20 --exclude-ambiguous --entropy\n  qpass --mode quantum --show-raw 64",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-l", "--length", type=int, default=16, help="password length (default: 16)")
    p.add_argument("-n", "--count", type=int, default=1, help="how many passwords (default: 1)")
    p.add_argument("--no-lowercase", action="store_true", help="exclude a-z")
    p.add_argument("--no-uppercase", action="store_true", help="exclude A-Z")
    p.add_argument("--no-digits", action="store_true", help="exclude 0-9")
    p.add_argument("--no-symbols", action="store_true", help="exclude special symbols")
    p.add_argument("--symbols-set", metavar="CHARS", help="custom special-character set")
    p.add_argument("--exclude-ambiguous", action="store_true", help="drop look-alikes (Il1|O0o)")
    p.add_argument("--exclude", default="", metavar="CHARS", help="drop these characters")
    p.add_argument(
        "--mode", choices=["hybrid", "quantum", "classical"], default="hybrid",
        help="hybrid = quantum XOR OS CSPRNG (default); quantum = quantum only; "
        "classical = OS CSPRNG only",
    )
    p.add_argument("--qubits", type=int, default=16, help=f"qubits per circuit (1-{MAX_QUBITS})")
    p.add_argument("--strict", action="store_true",
                   help="fail instead of falling back to the OS CSPRNG if Qiskit is unusable")
    p.add_argument("--entropy", action="store_true", help="print estimated entropy to stderr")
    p.add_argument("--show-raw", type=int, metavar="N", help="print N raw bits from the source")
    p.add_argument("--show-circuit", action="store_true", help="draw the quantum circuit")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    if not 1 <= args.count <= 1000:
        print("error: --count must be between 1 and 1000", file=sys.stderr)
        return 2
    if not 1 <= args.qubits <= MAX_QUBITS:
        print(f"error: --qubits must be between 1 and {MAX_QUBITS}", file=sys.stderr)
        return 2
    if args.show_raw is not None and not 1 <= args.show_raw <= 100_000:
        print("error: --show-raw must be between 1 and 100000", file=sys.stderr)
        return 2

    options = PasswordOptions(
        length=args.length,
        lowercase=not args.no_lowercase,
        uppercase=not args.no_uppercase,
        digits=not args.no_digits,
        symbols=not args.no_symbols,
        custom_symbols=args.symbols_set,
        exclude_ambiguous=args.exclude_ambiguous,
        exclude_chars=args.exclude,
    )
    try:
        options.character_sets()  # validate before touching Qiskit
    except PasswordConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.length < RECOMMENDED_MIN_LENGTH:
        print(f"warning: passwords shorter than {RECOMMENDED_MIN_LENGTH} characters are weak.",
              file=sys.stderr)

    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            source = create_bit_source(args.mode, args.qubits, allow_fallback=not args.strict)
        for w in caught:
            print(f"warning: {w.message}", file=sys.stderr)

        q = source.quantum if isinstance(source, HybridBitSource) else source
        if args.show_circuit:
            if isinstance(q, QuantumBitSource):
                print(q.circuit.draw(output="text", fold=120), file=sys.stderr)
            else:
                print("note: no quantum circuit in use for this mode/fallback.", file=sys.stderr)
        if args.show_raw:
            print(f"raw bits [{q.name}]:\n{q.generate_bits(args.show_raw)}", file=sys.stderr)

        generator = PasswordGenerator(source)
        for pw in generator.generate_many(args.count, options):
            print(pw)
        if args.entropy:
            print(f"source: {source.name}\nentropy ~ {estimate_entropy_bits(options):.1f} bits "
                  f"(raw bits consumed: {generator.bits_consumed})", file=sys.stderr)
    except QuantumBackendError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
