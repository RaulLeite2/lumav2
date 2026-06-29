from __future__ import annotations

from enum import Enum

from discord import app_commands


class ErrorCode(str, Enum):
    INTERNAL = "INT-000"
    MISSING_PERMISSIONS = "AUTH-403"
    RATE_LIMITED = "RATE-429"
    BAD_ARGUMENTS = "VAL-400"


class ErrorCatalog:
    _MESSAGES = {
        "pt": {
            ErrorCode.INTERNAL: "Ocorreu um erro interno. Tenta novamente em alguns segundos.",
            ErrorCode.MISSING_PERMISSIONS: "Voce nao tem permissao para executar este comando.",
            ErrorCode.RATE_LIMITED: "Muitas tentativas em pouco tempo. Aguarde e tente novamente.",
            ErrorCode.BAD_ARGUMENTS: "Os parametros enviados estao invalidos. Revise e tente novamente.",
        },
        "en": {
            ErrorCode.INTERNAL: "An internal error occurred. Please try again in a few seconds.",
            ErrorCode.MISSING_PERMISSIONS: "You do not have permission to run this command.",
            ErrorCode.RATE_LIMITED: "Too many attempts in a short time. Please wait and try again.",
            ErrorCode.BAD_ARGUMENTS: "The provided parameters are invalid. Please review and try again.",
        },
        "es": {
            ErrorCode.INTERNAL: "Ocurrio un error interno. Intentalo de nuevo en unos segundos.",
            ErrorCode.MISSING_PERMISSIONS: "No tienes permisos para ejecutar este comando.",
            ErrorCode.RATE_LIMITED: "Demasiados intentos en poco tiempo. Espera e intentalo de nuevo.",
            ErrorCode.BAD_ARGUMENTS: "Los parametros enviados son invalidos. Revisa e intenta de nuevo.",
        },
    }

    @classmethod
    def from_exception(cls, error: Exception) -> ErrorCode:
        if isinstance(error, app_commands.MissingPermissions):
            return ErrorCode.MISSING_PERMISSIONS
        if isinstance(error, app_commands.CommandOnCooldown):
            return ErrorCode.RATE_LIMITED
        if isinstance(error, app_commands.CheckFailure):
            return ErrorCode.MISSING_PERMISSIONS
        if isinstance(error, (app_commands.TransformerError, app_commands.CommandInvokeError)):
            return ErrorCode.BAD_ARGUMENTS
        return ErrorCode.INTERNAL

    @classmethod
    def user_message(cls, code: ErrorCode, lang: str) -> str:
        normalized_lang = lang if lang in cls._MESSAGES else "pt"
        return cls._MESSAGES[normalized_lang].get(code, cls._MESSAGES["pt"][ErrorCode.INTERNAL])
