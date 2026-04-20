import numpy as np


def build_standard_spin_matrices(spin: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    try:
        spin_value = float(spin)
    except (TypeError, ValueError) as exc:
        raise ValueError("spin must be a non-negative integer or half-integer") from exc

    two_spin = 2.0 * spin_value
    if (
        not np.isfinite(spin_value)
        or spin_value < 0
        or not np.isclose(two_spin, np.round(two_spin), rtol=0.0, atol=1e-12)
    ):
        raise ValueError("spin must be a non-negative integer or half-integer")

    dim = int(np.round(two_spin)) + 1
    ms = np.linspace(-spin_value, spin_value, dim, dtype=float)
    sz = np.diag(ms).astype(complex)
    sp = np.zeros((dim, dim), dtype=complex)
    for i, m in enumerate(ms[:-1]):
        sp[i + 1, i] = np.sqrt(spin_value * (spin_value + 1.0) - m * (m + 1.0))
    sm = sp.conj().T
    sx = 0.5 * (sp + sm)
    sy = (sp - sm) / (2j)
    return sx, sy, sz


def embed_spin_operators(
    u: np.ndarray,
    w: np.ndarray,
    operator_dict: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    return {name: u @ w @ op @ w.conj().T @ u.conj().T for name, op in operator_dict.items()}
