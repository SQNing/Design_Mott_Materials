#!/usr/bin/env python3
from dataclasses import dataclass
from typing import Tuple, Union


@dataclass(frozen=True)
class NumberNode:
    value: float
    kind: str = "number"


@dataclass(frozen=True)
class SymbolNode:
    name: str
    multiplier: float = 1.0
    kind: str = "symbol"


@dataclass(frozen=True)
class FactorNode:
    label: str
    site: int
    kind: str = "factor"


@dataclass(frozen=True)
class ProductNode:
    factors: Tuple[FactorNode, ...]
    kind: str = "product"


@dataclass(frozen=True)
class ScaledNode:
    coefficient: Union[NumberNode, SymbolNode]
    expression: ProductNode
    kind: str = "scaled"


@dataclass(frozen=True)
class SumNode:
    terms: Tuple[Union[ProductNode, ScaledNode], ...]
    kind: str = "sum"
