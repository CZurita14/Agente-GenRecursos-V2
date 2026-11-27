"""Clave del panel de consumo: solo su hash PBKDF2 vive en la configuración."""
import base64
import hashlib
import hmac
import secrets

ALGORITMO = "pbkdf2_sha256"


def hashear(clave: str, iteraciones: int = 600_000) -> str:
    sal = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, iteraciones)
    return "$".join((ALGORITMO, str(iteraciones), base64.b64encode(sal).decode(), base64.b64encode(dk).decode()))


def verificar(clave: str, hash_: str) -> bool:
    """Comparación en tiempo constante; un hash mal formado nunca valida."""
    try:
        algoritmo, iteraciones, sal, esperado = hash_.split("$")
        if algoritmo != ALGORITMO:
            return False
        dk = hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), base64.b64decode(sal), int(iteraciones))
        return hmac.compare_digest(dk, base64.b64decode(esperado))
    except (ValueError, TypeError):
        return False
