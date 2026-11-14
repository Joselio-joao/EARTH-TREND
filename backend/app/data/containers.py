"""Contentores que o carregador entrega ao motor de análise."""
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Cube:
    """Grelha lat/lon ao longo do tempo (um passo por mês)."""
    ym: list                      # [(ano, mês), ...] ordenado
    lats: np.ndarray              # (y,) crescente
    lons: np.ndarray              # (x,) crescente
    values: np.ndarray            # (tempo, y, x); NaN = em falta
    unit: object = None           # atributo 'units' do ficheiro (None se não existir)
    files: list = field(default_factory=list)    # [{"name", "modified"}]
    meta: dict = field(default_factory=dict)     # atributos globais selecionados
    masked_invalid: int = 0       # valores fora de gama anulados (ex.: preenchimentos negativos)


@dataclass
class Series:
    """Série já agregada para uma região (por exemplo, exportada do Giovanni)."""
    ym: list
    values: np.ndarray            # (tempo,)
    unit: object = None
    files: list = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    masked_invalid: int = 0
