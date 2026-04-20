import numpy as np


def validate_column_eigenvectors(u: np.ndarray) -> None:
    gram = u.conj().T @ u
    np.testing.assert_allclose(gram, np.eye(gram.shape[0]), atol=1e-10)


def build_projector(u: np.ndarray) -> np.ndarray:
    validate_column_eigenvectors(u)
    return u @ u.conj().T


def project_operator(x: np.ndarray, u: np.ndarray) -> np.ndarray:
    validate_column_eigenvectors(u)
    return u.conj().T @ x @ u
