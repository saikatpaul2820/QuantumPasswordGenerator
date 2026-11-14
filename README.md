# Quantum Password Generator

A Python-based password generator that uses quantum computing concepts to generate random passwords. The project combines Qiskit, Python's secure random generation, and Streamlit to provide an interactive password-generation experience.

## Features

- **Quantum Random Generation:** Uses Qiskit quantum circuits with Hadamard gates and measurement to generate random bits.
- **Classical Random Generation:** Uses Python's `secrets` module as a secure classical random source.
- **Hybrid Generation:** Combines the available generation approaches.
- **Custom Password Length:** Generate passwords with a selected length.
- **Entropy Estimation:** Calculates an estimated password entropy to help understand password strength.
- **Interactive Web Interface:** Provides a user-friendly interface using Streamlit.
- **Fallback Support:** Uses Python's secure random generator when the quantum backend is unavailable.

## Technologies Used

- Python
- Qiskit
- Streamlit
- Pytest
- Python `secrets` module

## Project Structure

```text
QuantumPasswordGenerator/
│
├── .vscode/
│   ├── launch.json
│   └── settings.json
│
├── quantum_password/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── generator.py
│   └── quantum_source.py
│
├── tests/
│   └── test_generator.py
│
├── app.py
├── requirements.txt
├── pyproject.toml
├── README.md
└── .gitignore
```

## Installation

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
```

### 2. Open the project folder

```bash
cd QuantumPasswordGenerator
```

### 3. Create a virtual environment

```bash
python -m venv .venv
```

### 4. Activate the virtual environment

**Windows:**

```bash
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

### 5. Install dependencies

```bash
python -m pip install -r requirements.txt
```

## Run the Application

Start the Streamlit application using:

```bash
python -m streamlit run app.py
```

The application will open in your browser. If it does not open automatically, use the local URL displayed in your terminal.

## Run Tests

To execute the project's test cases, run:

```bash
python -m pytest -v
```

## How It Works

1. The user selects the desired password-generation options.
2. The application requests random bits from the selected random source.
3. In quantum mode, Qiskit creates a quantum circuit using Hadamard gates and measures the qubits.
4. The generated random bits are converted into password characters.
5. The application generates the password and estimates its entropy.
6. If the quantum backend is unavailable, the application can use Python's `secrets` module as a fallback.

## Quantum Computing Note

The quantum generation implemented in this project uses Qiskit-based quantum circuit execution. It should not be considered proof of execution on a physical quantum computer unless a real quantum hardware backend is configured and used.

## Purpose of the Project

The main purpose of this project is to explore the application of quantum computing concepts in cybersecurity, particularly random number generation and password security.

It demonstrates how quantum circuits, classical cryptographic randomness, and Python-based application development can be combined in a practical project.

## Future Improvements

- Integration with real quantum computing hardware.
- Additional password-strength analysis.
- More customization options.
- Improved user interface.
- Additional security testing.

B.Tech Computer Science Student

## License

This project is intended for educational and learning purposes.
