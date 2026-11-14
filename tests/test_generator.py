import collections
import string

import pytest

from quantum_password import (
    PasswordConfigError, PasswordGenerator, PasswordOptions, SecretsBitSource,
    create_bit_source, estimate_entropy_bits,
)
from quantum_password.generator import AMBIGUOUS, DEFAULT_SYMBOLS


@pytest.fixture
def gen():
    return PasswordGenerator(SecretsBitSource())


def test_length_and_charsets(gen):
    for _ in range(50):
        pw = gen.generate(PasswordOptions(length=12))
        assert len(pw) == 12
        assert any(c in string.ascii_lowercase for c in pw)
        assert any(c in string.ascii_uppercase for c in pw)
        assert any(c in string.digits for c in pw)
        assert any(c in DEFAULT_SYMBOLS for c in pw)


def test_digits_only(gen):
    pw = gen.generate(PasswordOptions(length=30, lowercase=False, uppercase=False, symbols=False))
    assert pw.isdigit()


def test_exclusions(gen):
    pw = gen.generate(PasswordOptions(length=200, exclude_ambiguous=True, exclude_chars="xyz"))
    assert not set(pw) & (set(AMBIGUOUS) | set("xyz"))


@pytest.mark.parametrize("kwargs", [
    {"length": 0}, {"length": 5000}, {"length": 2.5},
    {"lowercase": False, "uppercase": False, "digits": False, "symbols": False},
    {"length": 3},                                      # fewer chars than selected sets
    {"custom_symbols": "ab c"},                         # whitespace
    {"custom_symbols": "\u00e9"},                       # non-ASCII
    {"exclude_chars": string.digits},                   # digit set emptied
])
def test_invalid_options(kwargs):
    with pytest.raises(PasswordConfigError):
        PasswordOptions(**kwargs).character_sets()


def test_random_below_uniform(gen):
    counts = collections.Counter(gen.random_below(6) for _ in range(6000))
    assert set(counts) == set(range(6))
    assert all(800 < v < 1200 for v in counts.values())


def test_shuffle_is_permutation(gen):
    items = list(range(50))
    gen.shuffle(items)
    assert sorted(items) == list(range(50))


def test_entropy():
    opts = PasswordOptions(length=10, uppercase=False, symbols=False)  # 36-char alphabet
    assert estimate_entropy_bits(opts) == pytest.approx(10 * 5.169925, rel=1e-4)


def test_quantum_source_if_available():
    pytest.importorskip("qiskit")
    src = create_bit_source("quantum", n_qubits=8, allow_fallback=False)
    bits = src.generate_bits(1000)
    assert len(bits) == 1000 and set(bits) <= {"0", "1"}
    assert 400 < bits.count("1") < 600
    hybrid = PasswordGenerator(create_bit_source("hybrid", 8, allow_fallback=False))
    assert len(hybrid.generate(PasswordOptions(length=20))) == 20


def test_every_backend_if_available():
    pytest.importorskip("qiskit")
    from quantum_password import quantum_source as qs
    ok = 0
    for name, factory in qs._CANDIDATES:
        try:
            runner = factory()
        except Exception:
            continue
        out = runner(qs.build_circuit(4), 10)
        assert len(out) == 10 and all(len(s.replace(" ", "")) == 4 for s in out), name
        ok += 1
    assert ok >= 1


def test_fallback_when_no_backend(monkeypatch):
    pytest.importorskip("qiskit")
    from quantum_password import quantum_source as qs
    monkeypatch.setattr(qs, "_CANDIDATES", [("broken", lambda: (_ for _ in ()).throw(ImportError("x")))])
    with pytest.warns(RuntimeWarning):
        assert isinstance(create_bit_source("hybrid"), SecretsBitSource)
    with pytest.raises(qs.QuantumBackendError):
        create_bit_source("hybrid", allow_fallback=False)
