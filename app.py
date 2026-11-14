"""Streamlit UI:  streamlit run app.py"""
import warnings

import streamlit as st

from quantum_password import (
    PasswordConfigError, PasswordGenerator, PasswordOptions, QuantumBitSource,
    create_bit_source, estimate_entropy_bits,
)
from quantum_password.quantum_source import HybridBitSource

st.set_page_config(page_title="Quantum Password Generator", page_icon="⚛️")
st.title("⚛️ Quantum Password Generator")
st.caption("Randomness from Hadamard-gated qubits, measured with Qiskit.")


@st.cache_resource
def get_source(mode: str, qubits: int):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        src = create_bit_source(mode, qubits)
    return src, [str(x.message) for x in w]


with st.sidebar:
    st.header("Options")
    length = st.slider("Length", 4, 128, 20)
    count = st.number_input("How many", 1, 20, 1)
    lower = st.checkbox("Lowercase (a-z)", True)
    upper = st.checkbox("Uppercase (A-Z)", True)
    digits = st.checkbox("Digits (0-9)", True)
    symbols = st.checkbox("Symbols", True)
    ambiguous = st.checkbox("Exclude ambiguous (Il1|O0o)", False)
    mode = st.selectbox("Entropy mode", ["hybrid", "quantum", "classical"])
    qubits = st.slider("Qubits per circuit", 1, 20, 16)

opts = PasswordOptions(length=length, lowercase=lower, uppercase=upper, digits=digits,
                       symbols=symbols, exclude_ambiguous=ambiguous)

if st.button("Generate", type="primary"):
    try:
        opts.character_sets()
        source, warns = get_source(mode, qubits)
        for msg in warns:
            st.warning(msg)
        gen = PasswordGenerator(source)
        for pw in gen.generate_many(int(count), opts):
            st.code(pw, language=None)
        st.metric("Estimated entropy", f"{estimate_entropy_bits(opts):.0f} bits")
        st.caption(f"Source: {source.name}")
        q = source.quantum if isinstance(source, HybridBitSource) else source
        if isinstance(q, QuantumBitSource):
            with st.expander("Quantum circuit"):
                st.code(str(q.circuit.draw(output="text", fold=100)), language=None)
    except PasswordConfigError as exc:
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001
        st.error(f"Generation failed: {exc}")
