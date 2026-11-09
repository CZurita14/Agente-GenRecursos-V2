"""Vista autenticada del borrador técnico; no lo presenta como aviso aprobado."""
from fastapi import APIRouter
from app.config import RAIZ

router = APIRouter()


@router.get("/privacidad")
def privacidad():
    return {"estado": "borrador", "version": "2026-10-27",
            "texto": (RAIZ / "docs/privacidad-borrador.md").read_text(encoding="utf-8")}
