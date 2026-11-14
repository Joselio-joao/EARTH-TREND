"""Guarda cada análise como um ficheiro JSON em data/results/ (no MVP não há base de dados)."""
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

_ID = re.compile(r"^[0-9a-f]{32}$")


def summary(result):
    trend = result.get("trend") or {}
    mk = trend.get("mann_kendall") or {}
    return {
        "id": result["id"], "created_at": result.get("created_at"),
        "dataset_id": (result.get("dataset") or {}).get("id"),
        "region": (result.get("region") or {}).get("name"),
        "variable": (result.get("variable") or {}).get("label"),
        "period": (result.get("period") or {}).get("analyzed"),
        "scale": result.get("scale_label"), "unit": result.get("unit"),
        "direction": trend.get("direction"), "significant": trend.get("significant"),
        "p_value": mk.get("p_value"),
    }


class ResultStore:
    def __init__(self, directory):
        self.dir = Path(directory)

    @staticmethod
    def new_id():
        return uuid.uuid4().hex

    @staticmethod
    def valid_id(rid):
        return bool(_ID.match(str(rid)))

    def save(self, result):
        rid = result["id"]
        if not self.valid_id(rid):
            raise ValueError("id de resultado inválido")
        self.dir.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(result, fh, ensure_ascii=False, allow_nan=False)
            os.replace(tmp, str(self.dir / ("%s.json" % rid)))
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def load(self, rid):
        """Devolve o resultado, ou None se o id for inválido ou não existir (nunca lê fora da pasta)."""
        if not self.valid_id(rid):
            return None
        path = self.dir / ("%s.json" % rid)
        if not path.is_file():
            return None
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def list(self, limit=20):
        if not self.dir.is_dir():
            return []
        files = sorted(self.dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        out = []
        for p in files:
            try:
                with open(p, encoding="utf-8") as fh:
                    out.append(summary(json.load(fh)))
            except (OSError, ValueError, KeyError):
                continue
        return out
