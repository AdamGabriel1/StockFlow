from typing import Optional, Tuple

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from stockflow.auth import decodificar_token
from stockflow.carrinho_repo import CarrinhoRepo
from stockflow.models import Carrinho, Usuario
from stockflow.usuario_repo import UsuarioRepo

# tokenUrl aponta para o endpoint de login (Swagger usa isso)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_CRED_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciais inválidas ou expiradas",
    headers={"WWW-Authenticate": "Bearer"},
)


# ---------- carrinho ----------
def get_cart_pair(
    x_cart_id: str = Header(..., alias="X-Cart-Id"),
) -> Tuple[str, Carrinho]:
    car = CarrinhoRepo.buscar(x_cart_id)
    if car is None:
        raise HTTPException(
            status_code=404,
            detail="Carrinho não encontrado. Crie um novo via POST /carrinho.",
        )
    return x_cart_id, car


def get_carrinho(
    x_cart_id: str = Header(..., alias="X-Cart-Id"),
) -> Carrinho:
    return get_cart_pair(x_cart_id)[1]


# ---------- autenticação ----------
def get_current_user(token: str = Depends(oauth2_scheme)) -> Usuario:
    try:
        payload = decodificar_token(token)
    except Exception:
        raise _CRED_EXC
    sub = payload.get("sub")
    if not sub:
        raise _CRED_EXC
    user = UsuarioRepo.buscar_por_email(sub)
    if user is None or not user.ativo:
        raise _CRED_EXC
    return user


def get_current_admin(user: Usuario = Depends(get_current_user)) -> Usuario:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores",
        )
    return user

# Schemas "gêmeos": um obrigatório (401), outro opcional (retorna None se ausente/inválido)
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/auth/login", auto_error=False
)


def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme_optional),
) -> Optional[Usuario]:
    if not token:
        return None
    try:
        payload = decodificar_token(token)
    except Exception:
        return None
    sub = payload.get("sub")
    if not sub:
        return None
    user = UsuarioRepo.buscar_por_email(sub)
    if user is None or not user.ativo:
        return None
    return user