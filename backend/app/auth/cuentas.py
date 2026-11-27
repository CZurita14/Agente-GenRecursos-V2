"""Cuentas locales de la etapa de pruebas: las crea un administrador, sin verificar el correo.

Solo se aceptan correos @indoamerica.edu.ec y @uti.edu.ec (`normalizar_correo`). La clave se guarda
como hash PBKDF2; la inicial la cambia el docente en su primer ingreso. Restablecer la clave o
desactivar la cuenta cierra sus sesiones abiertas. Ningún mensaje lleva la clave.
"""
from contextlib import closing

from app.auth.servicio import AuthError, normalizar_correo
from app.control.clave import hashear, verificar

CLAVE_MIN, CLAVE_MAX = 10, 128


def validar_clave(clave: str) -> str:
    if not CLAVE_MIN <= len(clave) <= CLAVE_MAX or clave.strip() != clave:
        raise AuthError(422, f"La clave debe tener entre {CLAVE_MIN} y {CLAVE_MAX} caracteres, sin espacios al inicio ni al final")
    return clave


def correo_institucional(valor: str) -> str:
    try:
        return normalizar_correo(valor)
    except AuthError:
        raise AuthError(422, "Solo se permiten correos @indoamerica.edu.ec o @uti.edu.ec") from None


class ServicioCuentas:
    def __init__(self, conexion):
        self.conexion = conexion

    def _conn(self):
        conn = self.conexion()
        conn.autocommit = True
        return conn

    def listar(self) -> list[dict]:
        with closing(self._conn()) as conn:
            return conn.execute(
                "select c.correo,c.nombre,c.activa,c.cambiar_clave,c.creada,c.creada_por,d.ultimo_ingreso,"
                "(select count(*) from materia_sga m where m.correo=c.correo) materias "
                "from cuenta_local c left join docente d on d.correo=c.correo order by c.creada desc,c.correo"
            ).fetchall()

    def crear(self, correo: str, nombre: str, clave: str, administrador: str) -> dict:
        correo = correo_institucional(correo)
        hash_ = hashear(validar_clave(clave))
        with closing(self._conn()) as conn:
            fila = conn.execute(
                "insert into cuenta_local (correo,nombre,clave_hash,creada_por) values (%s,%s,%s,%s) "
                "on conflict (correo) do nothing returning correo",
                (correo, " ".join(nombre.split())[:200], hash_, administrador)).fetchone()
        if fila is None:
            raise AuthError(422, "Ya existe una cuenta con ese correo")
        return {"correo": correo}

    def restablecer(self, correo: str, clave: str) -> None:
        """Nueva clave inicial: el docente deberá cambiarla al entrar. Cierra sus sesiones."""
        hash_ = hashear(validar_clave(clave))
        with closing(self._conn()) as conn, conn.transaction():
            fila = conn.execute("update cuenta_local set clave_hash=%s,cambiar_clave=true,actualizada=now() "
                                "where correo=%s returning correo", (hash_, correo)).fetchone()
            if fila is None:
                raise AuthError(404, "No existe esa cuenta")
            conn.execute("delete from auth_sesion where correo=%s", (correo,))

    def activar(self, correo: str, activa: bool) -> None:
        with closing(self._conn()) as conn, conn.transaction():
            fila = conn.execute("update cuenta_local set activa=%s,actualizada=now() where correo=%s returning correo",
                                (activa, correo)).fetchone()
            if fila is None:
                raise AuthError(404, "No existe esa cuenta")
            if not activa:
                conn.execute("delete from auth_sesion where correo=%s", (correo,))

    def estado(self, correo: str) -> dict | None:
        """None si el correo no tiene cuenta local activa."""
        with closing(self._conn()) as conn:
            return conn.execute("select cambiar_clave from cuenta_local where correo=%s and activa",
                                (correo,)).fetchone()

    def cambiar_clave(self, correo: str, actual: str, nueva: str) -> None:
        validar_clave(nueva)
        if nueva == actual:
            raise AuthError(422, "La clave nueva debe ser distinta de la actual")
        with closing(self._conn()) as conn, conn.transaction():
            fila = conn.execute("select clave_hash from cuenta_local where correo=%s and activa for update",
                                (correo,)).fetchone()
            if fila is None:
                raise AuthError(404, "Tu cuenta no usa clave local")
            if not verificar(actual, fila["clave_hash"]):
                raise AuthError(422, "La clave actual no es correcta")
            conn.execute("update cuenta_local set clave_hash=%s,cambiar_clave=false,actualizada=now() where correo=%s",
                         (hashear(nueva), correo))
