"""Erros da API. Cada um vira uma resposta JSON {"error": {"code", "message", "details"}}."""


class ApiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self):
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}
