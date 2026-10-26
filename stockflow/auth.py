"""Senhas (PBKDF2-SHA256) e JWT (HS256)."""
import hashlib
import os
import secrets
import warnings
from datetime import datetime, timedelta, timezone
from typing import Tuple

import jwt

# carrega .env se existir (python-dotenv vem como dep do uvicorn[standard])
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ⚠️ em produção, defina STOCKFLOW_SECRET_KEY (>= 32 bytes) e NUNCA use o fallback
SECRET_KEY = os.getenv("STOCKFLOW_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_hex(32)
    warnings.warn(
        "STOCKFLOW_SECRET_KEY não definida — gerando chave efêmera. "
        "Defina no .env para evitar este aviso.",
        RuntimeWarning,
        stacklevel=2,
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 8 * 60       # 8 horas
PBKDF2_ROUNDS = 260_000                     # OWASP 2023 p/ PBKDF2-SHA256


# ---------- senhas ----------
def hash_senha(senha: str) -> str:
    if not senha:
        raise ValueError("Senha vazia.")
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    )
    return f"pbkdf2_sha256${salt}${h.hex()}"


def verificar_senha(senha: str, armazenada: str) -> bool:
    try:
        alg, salt, h_hex = armazenada.split("$")
    except ValueError:
        return False
    if alg != "pbkdf2_sha256":
        return False
    calc = hashlib.pbkdf2_hmac(
        "sha256", senha.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ROUNDS
    )
    return secrets.compare_digest(calc.hex(), h_hex)


# ---------- JWT ----------
def criar_token(sub: str, role: str) -> Tuple[str, int]:
    """Devolve (token, expira_em_segundos)."""
    agora = datetime.now(timezone.utc)
    expira = agora + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": sub,
        "role": role,
        "iat": int(agora.timestamp()),
        "exp": int(expira.timestamp()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM), \
        ACCESS_TOKEN_EXPIRE_MINUTES * 60


def decodificar_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
