"""Configuración del backend, leída del entorno y del `.env` en la raíz del proyecto."""
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[2]


class Ajustes(BaseSettings):
    model_config = SettingsConfigDict(env_file=RAIZ / ".env", extra="ignore")

    database_url: str
    # La URL y el modelo del servidor de IA solo viven en la configuración.
    llm_base_url: str
    llm_model: str
    llm_api_key: str = "no-se-necesita"
    # "vllm": servidor local. "deepseek": API de DeepSeek (el contenido académico sale del servidor).
    llm_proveedor: Literal["vllm", "deepseek"] = "vllm"
    # False solo en desarrollo, si un antivirus inspecciona HTTPS con una raíz que Python 3.13 rechaza.
    llm_tls_estricto: bool = True
    llm_max_concurrencia: int = 4
    llm_timeout_s: float = 120
    llm_timeout_revisor_s: float = 240
    lease_s: int = 360
    agentes_dir: Path = Path("agentes")
    # Carpeta del modelo entrenado. Sin ella la generación no usa el razonador.
    razonador_ruta: Path | None = None
    api_origen: str = "https://localhost:5173"
    auth_secreto: SecretStr | None = Field(default=None, min_length=32)
    entorno: Literal["desarrollo", "produccion"] = "produccion"
    # Entrar sin autenticar contra el SGA (solo desarrollo); el ingreso normal usa el SGA.
    acceso_prueba: bool = False
    api_json_max_bytes: int = Field(default=1024 * 1024, ge=1, le=4 * 1024 * 1024)
    api_json_timeout_s: float = Field(default=30, gt=0, le=120)
    # Proveedor del SGA: "real" espera el adaptador de TI; "simulado" (solo desarrollo) lee los fixtures
    # de `sga_simulado_dir`, relativa a la raíz del proyecto.
    sga_proveedor: Literal["simulado", "real"] = "real"
    sga_simulado_dir: Path | None = None
    sga_timeout_s: float = Field(default=15, gt=0, le=120)
    # Presupuesto de la sincronización dentro del ingreso: el proxy corta la petición a los 65 s.
    sga_sincronizacion_max_s: float = Field(default=45, gt=0, lt=65)
    administradores: list[str] = Field(default_factory=list)
    proxies_confiables: list[str] = Field(default_factory=list)
    limite_ip_minuto: int = Field(default=600, ge=1, le=100000)
    limite_usuario_minuto: int = Field(default=120, ge=1, le=100000)
    limite_ingresar_ip_minuto: int = Field(default=60, ge=1, le=100000)
    limite_ingresar_usuario_minuto: int = Field(default=20, ge=1, le=100000)
    limite_generar_correo_hora: int = Field(default=30, ge=1, le=100000)
    limite_editar_correo_minuto: int = Field(default=30, ge=1, le=100000)
    auditoria_retencion_dias: int = Field(default=30, ge=1, le=365)

    @field_validator("sga_simulado_dir", mode="before")
    @classmethod
    def sga_dir_vacio_es_apagado(cls, valor):
        return None if isinstance(valor, str) and not valor.strip() else valor

    @field_validator("sga_simulado_dir")
    @classmethod
    def sga_dir_desde_la_raiz(cls, valor):
        # Relativa a la raíz y no a la carpeta desde la que se arranca uvicorn (backend/).
        return valor if valor is None or valor.is_absolute() else RAIZ / valor

    @field_validator("razonador_ruta", mode="before")
    @classmethod
    def ruta_vacia_es_apagado(cls, valor):
        # El compose pasa la variable vacía cuando no hay modelo; Path("") sería la carpeta actual.
        return None if isinstance(valor, str) and not valor.strip() else valor

    @field_validator("administradores")
    @classmethod
    def admins_validos(cls, valores):
        from app.auth.servicio import AuthError, normalizar_correo
        try:
            return sorted({normalizar_correo(v) for v in valores})
        except AuthError:
            raise ValueError("ADMINISTRADORES solo admite correos institucionales") from None

    @field_validator("proxies_confiables")
    @classmethod
    def proxies_validos(cls, valores):
        from ipaddress import ip_network
        redes = [ip_network(v) for v in valores]
        if any(r.prefixlen == 0 for r in redes):
            raise ValueError("No se permite confiar en todos los proxies")
        return [str(r) for r in redes]

    @model_validator(mode="after")
    def https_en_produccion(self):
        if self.entorno == "produccion" and not self.api_origen.startswith("https://"):
            raise ValueError("API_ORIGEN requiere HTTPS en producción")
        if self.entorno == "produccion" and not self.llm_tls_estricto:
            raise ValueError("LLM_TLS_ESTRICTO=false solo se permite en desarrollo")
        if self.entorno == "produccion" and self.acceso_prueba:
            raise ValueError("ACCESO_PRUEBA no se permite en producción")
        if self.entorno == "produccion" and self.sga_proveedor == "simulado":
            raise ValueError("SGA_PROVEEDOR=simulado no se permite en producción")
        if self.sga_proveedor == "simulado" and (
                self.sga_simulado_dir is None or not (self.sga_simulado_dir / "usuarios.json").is_file()):
            raise ValueError("SGA_SIMULADO_DIR debe ser una carpeta con usuarios.json "
                             "(relativa a la raíz, p. ej. backend/tests/fixtures/sga)")
        return self

    @field_validator("api_origen")
    @classmethod
    def origen_exacto(cls, valor: str) -> str:
        url = urlsplit(valor)
        # Evaluar port también detecta números fuera de rango o no numéricos.
        url.port
        if (url.scheme not in {"http", "https"} or not url.hostname
                or url.username is not None or url.password is not None
                or url.path or url.query or url.fragment or "*" in valor):
            raise ValueError("API_ORIGEN debe ser un origen HTTP(S) exacto, sin ruta")
        return valor


@lru_cache
def ajustes() -> Ajustes:
    return Ajustes()
