from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from stockflow.auth import criar_token, hash_senha, verificar_senha
from stockflow.models import Usuario
from stockflow.usuario_repo import UsuarioRepo
from stockflow.api.deps import get_current_user
from stockflow.api.schemas import UsuarioIn, UsuarioOut, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UsuarioOut, status_code=201)
def register(dados: UsuarioIn):
    """Auto-cadastro: sempre cria com role='cliente'."""
    if UsuarioRepo.buscar_por_email(dados.email):
        raise HTTPException(409, "Email já cadastrado")
    u = Usuario(
        nome=dados.nome,
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        role="cliente",
    )
    u.id = UsuarioRepo.inserir(u)
    return UsuarioOut.from_model(u)


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends()):
    """Login OAuth2 (username = email, password = senha)."""
    u = UsuarioRepo.buscar_por_email(form.username)
    if not u or not u.ativo or not verificar_senha(form.password, u.senha_hash):
        raise HTTPException(401, "Email ou senha inválidos")
    token, expira = criar_token(u.email, u.role)
    return TokenOut(access_token=token, expires_in=expira)


@router.get("/me", response_model=UsuarioOut)
def me(user: Usuario = Depends(get_current_user)):
    return UsuarioOut.from_model(user)
