"""Configuração por variáveis de ambiente (ver backend/.env.example). Sem segredos no código."""
import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_DATA = Path(__file__).resolve().parent / "data"

DEFAULT_ORIGINS = [
    "http://localhost:5173", "http://127.0.0.1:5173",   # Vite (npm run dev)
    "http://localhost:4173", "http://127.0.0.1:4173",   # Vite preview / python -m http.server 4173
    "https://joselio-joao.github.io",                    # site publicado no GitHub Pages
]


def _split(value, default):
    if value is None or not value.strip():
        return list(default)
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass
class Settings:
    data_dir: Path = Path(__file__).resolve().parents[1] / "data"
    config_dir: Path = PACKAGE_DATA
    allowed_origins: list = field(default_factory=lambda: list(DEFAULT_ORIGINS))
    min_years: int = 10            # anos mínimos com dados para concluir uma tendência
    max_values: int = 20_000_000   # células x passos de tempo que um pedido pode carregar
    max_concurrent: int = 2        # análises em paralelo (protege a memória do servidor)
    ee_project_id: str = ""
    ee_service_account_json: str = ""

    @property
    def raw_dir(self):
        return Path(self.data_dir) / "raw"

    @property
    def results_dir(self):
        return Path(self.data_dir) / "results"

    @property
    def regions_dir(self):
        return Path(self.data_dir) / "regions"

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        s = cls()
        if env.get("EARTHTREND_DATA_DIR"):
            s.data_dir = Path(env["EARTHTREND_DATA_DIR"])
        s.allowed_origins = _split(env.get("EARTHTREND_ALLOWED_ORIGINS"), DEFAULT_ORIGINS)
        s.min_years = int(env.get("EARTHTREND_MIN_YEARS", s.min_years))
        s.max_values = int(env.get("EARTHTREND_MAX_VALUES", s.max_values))
        s.max_concurrent = int(env.get("EARTHTREND_MAX_CONCURRENT", s.max_concurrent))
        s.ee_project_id = env.get("EARTHTREND_EE_PROJECT_ID", "").strip()
        s.ee_service_account_json = env.get("EARTHTREND_EE_SERVICE_ACCOUNT_JSON", "")
        return s
