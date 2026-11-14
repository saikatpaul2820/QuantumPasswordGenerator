"""Quantum bit sources.

The core idea: put ``n`` qubits into the equal superposition state with a
Hadamard gate on every qubit (the "HHH...H" layer) and measure them. Each
measurement outcome is an ``n``-bit string; repeating over many shots yields a
long stream of raw random bits.

Several execution back-ends are probed in order so the project works across
Qiskit generations (0.4x legacy -> 1.x -> 2.x):

1. ``qiskit_aer.AerSimulator``                (fast, recommended)
2. ``qiskit.primitives.StatevectorSampler``   (Qiskit >= 1.0, no extra deps)
3. ``qiskit.providers.basic_provider``        (Qiskit >= 1.0, pure Python)
4. legacy ``Aer`` / ``BasicAer`` ``qasm_simulator`` (Qiskit < 1.0)

If none is available the factory can fall back to the OS CSPRNG.
"""
from __future__ import annotations

import logging
import math
import secrets
import warnings
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Tuple

log = logging.getLogger(__name__)

MIN_QUBITS = 1
MAX_QUBITS = 24

Runner = Callable[[object, int], List[str]]  # (circuit, shots) -> per-shot bitstrings


class QuantumBackendError(RuntimeError):
    """Raised when no usable Qiskit execution backend can be found."""


# --------------------------------------------------------------------------- #
# Circuit
# --------------------------------------------------------------------------- #
def build_circuit(n_qubits: int):
    """Return an ``n_qubits`` circuit: H on every qubit, then measure all."""
    if not MIN_QUBITS <= n_qubits <= MAX_QUBITS:
        raise ValueError(f"n_qubits must be between {MIN_QUBITS} and {MAX_QUBITS}")
    from qiskit import QuantumCircuit

    qc = QuantumCircuit(n_qubits, n_qubits, name="qrng")  # classical register is named "c"
    for q in range(n_qubits):
        qc.h(q)  # |0> -> (|0> + |1>) / sqrt(2)
    qc.barrier()
    qc.measure(range(n_qubits), range(n_qubits))
    return qc


# --------------------------------------------------------------------------- #
# Back-end runners (each returns a callable ``runner(circuit, shots)``)
# --------------------------------------------------------------------------- #
def _memory_runner(backend) -> Runner:
    from qiskit import transpile

    cache: dict = {}  # transpile each circuit once, not on every refill

    def run(qc, shots: int) -> List[str]:
        key = id(qc)
        if key not in cache:
            cache[key] = (qc, transpile(qc, backend))  # keep qc alive so id() stays valid
        tqc = cache[key][1]
        result = backend.run(tqc, shots=shots, memory=True).result()
        return list(result.get_memory())

    return run


def _aer_runner() -> Runner:
    from qiskit_aer import AerSimulator

    return _memory_runner(AerSimulator())


def _sampler_runner() -> Runner:
    from qiskit.primitives import StatevectorSampler  # Qiskit >= 1.0

    sampler = StatevectorSampler()

    def run(qc, shots: int) -> List[str]:
        result = sampler.run([qc], shots=shots).result()
        return list(result[0].data.c.get_bitstrings())

    return run


def _basic_provider_runner() -> Runner:
    from qiskit.providers.basic_provider import BasicSimulator  # Qiskit >= 1.0

    return _memory_runner(BasicSimulator())


def _legacy_aer_runner() -> Runner:
    from qiskit import Aer  # type: ignore  # Qiskit < 1.0

    return _memory_runner(Aer.get_backend("qasm_simulator"))


def _legacy_basicaer_runner() -> Runner:
    from qiskit import BasicAer  # type: ignore  # Qiskit < 1.0

    return _memory_runner(BasicAer.get_backend("qasm_simulator"))


_CANDIDATES: List[Tuple[str, Callable[[], Runner]]] = [
    ("qiskit-aer AerSimulator", _aer_runner),
    ("qiskit StatevectorSampler", _sampler_runner),
    ("qiskit BasicSimulator", _basic_provider_runner),
    ("legacy Aer qasm_simulator", _legacy_aer_runner),
    ("legacy BasicAer qasm_simulator", _legacy_basicaer_runner),
]


def _select_runner(candidates=None) -> Tuple[str, Runner]:
    """Return the first candidate that actually executes a tiny test circuit."""
    errors = []
    for name, factory in candidates or _CANDIDATES:
        try:
            runner = factory()
            probe = runner(build_circuit(2), 2)
            if len(probe) != 2:
                raise RuntimeError("probe returned unexpected number of shots")
            log.debug("Using backend: %s", name)
            return name, runner
        except Exception as exc:  # noqa: BLE001 - any failure => try next backend
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    raise QuantumBackendError(
        "No usable Qiskit backend found. Install with `pip install qiskit qiskit-aer`.\n  "
        + "\n  ".join(errors)
    )


# --------------------------------------------------------------------------- #
# Bit sources
# --------------------------------------------------------------------------- #
class BitSource(ABC):
    """Anything that can emit a string of ``'0'``/``'1'`` characters."""

    name: str = "abstract"

    @abstractmethod
    def generate_bits(self, n: int) -> str:
        """Return exactly ``n`` random bits as a string of 0/1 characters."""


class SecretsBitSource(BitSource):
    """Classical cryptographic fallback based on :mod:`secrets` (OS CSPRNG)."""

    name = "os-csprng"

    def generate_bits(self, n: int) -> str:
        if n <= 0:
            return ""
        return format(secrets.randbits(n), f"0{n}b")


class QuantumBitSource(BitSource):
    """Raw bits from measuring qubits in the |+> state (H|0>)."""

    def __init__(self, n_qubits: int = 16, backend_name: Optional[str] = None) -> None:
        self.n_qubits = n_qubits
        self._circuit = build_circuit(n_qubits)  # validates n_qubits
        backend, self._runner = _select_runner()
        self.name = f"quantum[{backend}]"

    @property
    def circuit(self):
        return self._circuit

    def generate_bits(self, n: int) -> str:
        if n <= 0:
            return ""
        shots = math.ceil(n / self.n_qubits)
        shots_out = self._runner(self._circuit, shots)
        bits = "".join(s.replace(" ", "") for s in shots_out)
        if len(bits) < n or set(bits) - {"0", "1"}:
            raise QuantumBackendError("Backend returned malformed measurement data.")
        bits = bits[:n]
        _monobit_health_check(bits)
        return bits


class HybridBitSource(BitSource):
    """Quantum bits XOR-ed with OS CSPRNG bits.

    The XOR of two independent sources is at least as unpredictable as the
    stronger of the two, so a flawed/biased simulator cannot weaken the result.
    """

    def __init__(self, quantum: BitSource, classical: Optional[BitSource] = None) -> None:
        self.quantum = quantum
        self.classical = classical or SecretsBitSource()
        self.name = f"{quantum.name} XOR {self.classical.name}"

    def generate_bits(self, n: int) -> str:
        if n <= 0:
            return ""
        q = int(self.quantum.generate_bits(n), 2)
        c = int(self.classical.generate_bits(n), 2)
        return format(q ^ c, f"0{n}b")


def _monobit_health_check(bits: str) -> None:
    """Crude sanity test: catches stuck/constant output (6-sigma bound)."""
    n = len(bits)
    if n < 256:
        return
    z = abs(bits.count("1") - n / 2) / (math.sqrt(n) / 2)
    if z > 6:
        raise QuantumBackendError(
            f"Quantum source failed monobit health check (z={z:.1f}); refusing to use it."
        )


def create_bit_source(
    mode: str = "hybrid", n_qubits: int = 16, allow_fallback: bool = True
) -> BitSource:
    """Factory.

    mode: ``"quantum"`` (pure), ``"hybrid"`` (quantum XOR CSPRNG, default),
          ``"classical"`` (CSPRNG only).
    """
    if mode not in {"quantum", "hybrid", "classical"}:
        raise ValueError("mode must be 'quantum', 'hybrid' or 'classical'")
    if mode == "classical":
        return SecretsBitSource()
    try:
        quantum = QuantumBitSource(n_qubits)
    except (ImportError, QuantumBackendError) as exc:
        if not allow_fallback:
            raise QuantumBackendError(str(exc)) from exc
        warnings.warn(
            f"Qiskit unavailable ({exc}); falling back to the OS CSPRNG.",
            RuntimeWarning,
            stacklevel=2,
        )
        return SecretsBitSource()
    return quantum if mode == "quantum" else HybridBitSource(quantum)
