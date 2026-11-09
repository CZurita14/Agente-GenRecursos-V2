"""Operación de Compose con stdlib. Ejecutar desde Windows o Linux con Python 3.12+."""
import argparse
import hashlib
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit


REPO = Path(__file__).resolve().parents[1]
PROTEGIDOS = {"genrecursos", "rootdev", "genrecursos-db"}
LIMITES = {  # Variable opcional → máximo admitido por app/config.py (mínimo 1).
    **{clave: 100000 for clave in (
        "LIMITE_IP_MINUTO", "LIMITE_USUARIO_MINUTO", "LIMITE_CODIGO_IP_HORA", "LIMITE_CODIGO_CORREO_HORA",
        "LIMITE_VERIFICAR_IP_MINUTO", "LIMITE_VERIFICAR_CORREO_MINUTO", "LIMITE_GENERAR_CORREO_HORA",
        "LIMITE_PDF_CORREO_HORA", "LIMITE_EDITAR_CORREO_MINUTO")},
    "AUDITORIA_RETENCION_DIAS": 365,
}
IDENTIFICADOR = re.compile(r"[a-z_][a-z0-9_]{0,62}\Z")
HOST = re.compile(r"(?=.{1,253}\Z)[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\Z")

# Literales fijos: nunca interpolar valores del host en programas de shell o SQL.
PG = 'export PGPASSWORD="$POSTGRES_PASSWORD"; '
DUMP = PG + 'exec pg_dump --format=custom --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"'
EXISTE = PG + '''exec psql -X -A -t --set=ON_ERROR_STOP=1 --username="$POSTGRES_USER" --dbname=postgres --set=target="$1" <<'SQL'
SELECT 1 FROM pg_database WHERE datname = :'target';
SQL
'''
CREAR = PG + '''exec psql -X --set=ON_ERROR_STOP=1 --username="$POSTGRES_USER" --dbname=postgres --set=target="$1" --set=owner="$POSTGRES_USER" <<'SQL'
CREATE DATABASE :"target" OWNER :"owner";
SQL
'''
RESTORE = PG + 'exec pg_restore --exit-on-error --username="$POSTGRES_USER" --dbname="$1"'


class ErrorOperacion(Exception):
    """Mensajes estáticos, aptos para mostrar sin credenciales ni salida de Docker."""


def exigir(condicion, campo):
    if not condicion:
        raise ErrorOperacion(f"Configuración inválida: {campo}.")


def leer_entorno(archivo):
    """Subset explícito de dotenv: líneas KEY=value, sin expansión ni ejecución."""
    datos = {}
    for linea in archivo.read_text(encoding="utf-8-sig").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        if linea.startswith("export "):
            linea = linea[7:].lstrip()
        clave, igual, valor = linea.partition("=")
        clave, valor = clave.strip(), valor.strip()
        exigir(igual and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", clave), "formato del entorno")
        exigir(clave not in datos, "variable duplicada")
        literal = valor.startswith("'")
        if valor.startswith(("'", '"')):
            comilla = valor[0]
            patron = r"'([^']*)'\s*(?:#.*)?" if literal else r'"((?:[^"\\]|\\.)*)"\s*(?:#.*)?'
            match = re.fullmatch(patron, valor)
            exigir(match is not None, "comillas del entorno")
            valor = match.group(1)
            if comilla == '"':
                valor = re.sub(r'\\([\\"nrt])', lambda m: {"n": "\n", "r": "\r", "t": "\t"}.get(m[1], m[1]), valor)
        else:
            valor = re.split(r"\s+#", valor, maxsplit=1)[0].rstrip()
        exigir(literal or "$" not in valor, "expansión no admitida; use valores literales entre comillas simples")
        exigir(not any(c in valor for c in "\x00\r\n"), "valor multilínea no admitido")
        datos[clave] = valor
    return datos


def no_placeholder(valor):
    normal = valor.lower().strip()
    return (bool(normal) and len(set(normal)) > 1
            and not any(token in normal for token in (
                "changeme", "change-me", "change_me", "cambiar", "reemplazar", "placeholder",
                "example", "ejemplo", "your-secret", "your_secret", "your-password", "your_password",
                "password", "contraseña", "replace", "todo", "<", ">",
            )))


def correo_institucional(valor):
    if not isinstance(valor, str) or any(c in valor for c in "\r\n"):
        return False
    correo = valor.strip().lower()
    local, _, dominio = correo.partition("@")
    return (len(correo) <= 254 and 1 <= len(local) <= 64
            and dominio in {"uti.edu.ec", "indoamerica.edu.ec"}
            and re.fullmatch(r"[a-z0-9!#$%&'*+/=?^_`{|}~.-]+", local) is not None
            and not local.startswith(".") and not local.endswith(".") and ".." not in local)


def validar(datos, archivo):
    def v(clave):
        return datos.get(clave, "")

    exigir(v("ENTORNO") in {"produccion", "desarrollo"}, "ENTORNO")
    produccion = v("ENTORNO") == "produccion"
    try:
        origen = urlsplit(v("API_ORIGEN"))
        origen.port
        exigir(origen.scheme in ({"https"} if produccion else {"http", "https"})
               and origen.hostname and HOST.fullmatch(origen.hostname)
               and origen.username is None and origen.password is None
               and not origen.path and not origen.query and not origen.fragment
               and not any(c.isspace() for c in v("API_ORIGEN"))
               and "?" not in v("API_ORIGEN") and "#" not in v("API_ORIGEN"), "API_ORIGEN")
    except ValueError:
        raise ErrorOperacion("Configuración inválida: API_ORIGEN.") from None
    exigir(len(v("AUTH_SECRETO")) >= 32 and no_placeholder(v("AUTH_SECRETO")), "AUTH_SECRETO")
    exigir(len(v("POSTGRES_PASSWORD")) >= 32 and no_placeholder(v("POSTGRES_PASSWORD"))
           and re.fullmatch(r"[A-Za-z0-9_-]+", v("POSTGRES_PASSWORD")), "POSTGRES_PASSWORD")
    exigir(all(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_-]{0,62}", v(campo))
               for campo in ("POSTGRES_DB", "POSTGRES_USER")), "POSTGRES_DB / POSTGRES_USER")
    exigir(v("SMTP_MODO") in ({"smtp"} if produccion else {"smtp", "deshabilitado"}), "SMTP_MODO")
    if v("SMTP_MODO") == "smtp":
        exigir(bool(v("SMTP_HOST")) and bool(v("SMTP_REMITENTE")), "SMTP_HOST / SMTP_REMITENTE")
    try:
        admins = json.loads(v("ADMINISTRADORES") or ("[]" if not produccion else ""))
    except (ValueError, TypeError):
        raise ErrorOperacion("Configuración inválida: ADMINISTRADORES.") from None
    exigir(isinstance(admins, list) and (bool(admins) or not produccion)
           and all(correo_institucional(a) for a in admins), "ADMINISTRADORES")
    try:
        red = ipaddress.ip_network(v("RED_PROXY"), strict=True)
        ip = ipaddress.ip_address(v("IP_PROXY"))
        exigir(red.version == ip.version == 4 and red.prefixlen > 0 and ip in red
               and ip not in {red.network_address, red.broadcast_address}, "RED_PROXY / IP_PROXY")
    except ValueError:
        raise ErrorOperacion("Configuración inválida: RED_PROXY / IP_PROXY.") from None
    try:
        # Docker asigna api/web desde este rango; si incluyera IP_PROXY, otro servicio podría tomarla.
        rango = ipaddress.ip_network(v("RANGO_DINAMICO") or "172.31.250.8/29", strict=True)
        exigir(rango.version == 4 and rango.subnet_of(red) and ip not in rango
               and rango.num_addresses >= 4, "RANGO_DINAMICO")
    except (ValueError, TypeError):
        raise ErrorOperacion("Configuración inválida: RANGO_DINAMICO.") from None
    # Mismos rangos que app/config.py: un valor fuera de rango dejaría la API sin arrancar.
    for clave, maximo in LIMITES.items():
        if clave in datos:
            exigir(re.fullmatch(r"[1-9][0-9]{0,5}", v(clave)) is not None and int(v(clave)) <= maximo, clave)
    exigir(bool(HOST.fullmatch(v("DOMINIO"))), "DOMINIO")
    exigir(bool(v("TLS_DIR")), "TLS_DIR")
    tls = Path(v("TLS_DIR"))
    if not tls.is_absolute():
        tls = archivo.parent / tls
    tls = tls.resolve()
    exigir(tls.is_dir() and all((tls / n).is_file() for n in ("fullchain.pem", "privkey.pem")), "TLS_DIR / certificados")
    datos["TLS_DIR"] = str(tls)


def validar_proyecto(proyecto):
    exigir(proyecto not in PROTEGIDOS and re.fullmatch(r"[a-z0-9][a-z0-9_-]*", proyecto), "proyecto (aislado y no protegido)")


def comando(archivo, proyecto):
    validar_proyecto(proyecto)
    return ["docker", "compose", "--env-file", str(archivo), "--project-name", proyecto,
            "-f", str(REPO / "infra/compose.yaml"), "exec", "-T", "db", "sh", "-c"]


def ejecutar(prefijo, datos, script, *, base=None, entrada=None, salida=None):
    # Los valores del archivo prevalecen sobre variables homónimas del host.
    ambiente = os.environ.copy()
    ambiente.update(datos)
    args = prefijo + [script]
    if base is not None:
        args += ["operar", base]  # $0 fijo y $1 validado; nunca concatenación de shell.
    try:
        return subprocess.run(args, stdin=entrada if entrada is not None else subprocess.DEVNULL,
                              stdout=salida if salida is not None else subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, env=ambiente, shell=False, check=True)
    except (OSError, subprocess.SubprocessError):
        raise ErrorOperacion("Falló la operación de Docker/PostgreSQL; diagnóstico externo restringido requerido.") from None


def huella(stream):
    stream.seek(0)
    digest = hashlib.sha256()
    for bloque in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(bloque)
    stream.seek(0)
    return digest.hexdigest()


def manifiesto(archivo):
    return archivo.with_name(archivo.name + ".sha256")


def respaldo(prefijo, datos, salida):
    """Dos archivos exclusivos; el dump solo aparece completo, después de su manifiesto."""
    firma = manifiesto(salida)
    exigir(not os.path.lexists(salida) and not os.path.lexists(firma), "salida ya existente")
    temporales, publicados = [], []
    completo = False
    try:
        with tempfile.NamedTemporaryFile(prefix=".operar-", dir=salida.parent, delete=False) as dump:
            temporal = Path(dump.name)
            temporales.append(temporal)
            os.chmod(temporal, 0o600)
            ejecutar(prefijo, datos, DUMP, salida=dump)
            dump.flush()
            os.fsync(dump.fileno())
        with temporal.open("rb") as stream:
            digest = huella(stream)
        with tempfile.NamedTemporaryFile(prefix=".operar-", dir=salida.parent, delete=False) as manifest:
            temporal_firma = Path(manifest.name)
            temporales.append(temporal_firma)
            os.chmod(temporal_firma, 0o600)
            manifest.write((digest + "\n").encode("ascii"))
            manifest.flush()
            os.fsync(manifest.fileno())
        # link es atómico y falla si el nombre ya existe (también ante carreras).
        # Requiere un sistema de archivos local que admita enlaces duros.
        for origen, destino in ((temporal_firma, firma), (temporal, salida)):
            os.link(origen, destino)
            publicados.append(destino)
        completo = True
    finally:
        for path in temporales + ([] if completo else publicados):
            path.unlink(missing_ok=True)


def restaurar(prefijo, datos, archivo, base):
    exigir(IDENTIFICADOR.fullmatch(base) and not base.startswith("pg_")
           and base not in {datos["POSTGRES_DB"], "postgres", "template0", "template1"}, "base nueva")
    esperado = manifiesto(archivo).read_text(encoding="ascii").strip()
    exigir(re.fullmatch(r"[a-f0-9]{64}", esperado), "manifiesto SHA-256")
    # Mismo descriptor para verificar y transmitir, sin cargar el archivo en memoria.
    with archivo.open("rb") as stream:
        exigir(hmac.compare_digest(esperado, huella(stream)), "integridad SHA-256")
        resultado = ejecutar(prefijo, datos, EXISTE, base=base, salida=subprocess.PIPE)
        exigir(not resultado.stdout.strip(), "la base de destino ya existe")
        ejecutar(prefijo, datos, CREAR, base=base)
        try:
            ejecutar(prefijo, datos, RESTORE, base=base, entrada=stream)
        except ErrorOperacion:
            raise ErrorOperacion("Restauración fallida: se conserva la base nueva para diagnóstico; no reutilizarla ni conectarla a producción.") from None


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normalmente reproduce argumentos; podrían contener secretos por error.
        raise ErrorOperacion("Argumentos inválidos; consulte --help.")


def main(argv=None):
    parser = Parser(description=__doc__)
    parser.add_argument("--entorno", required=True, type=Path, metavar="FILE")
    parser.add_argument("--proyecto", default="genrecursos-app", metavar="NAME")
    commands = parser.add_subparsers(dest="accion", required=True, parser_class=Parser)
    commands.add_parser("validar", help="Validar sin invocar Docker ni mostrar valores")
    backup = commands.add_parser("respaldo", help="Crear dump custom y manifiesto SHA-256")
    backup.add_argument("--salida", required=True, type=Path, metavar="PATH")
    restore = commands.add_parser("restaurar", help="Restaurar exclusivamente en una base nueva")
    restore.add_argument("--archivo", required=True, type=Path, metavar="PATH")
    restore.add_argument("--base", required=True, metavar="NUEVA")
    try:
        args = parser.parse_args(argv)
        validar_proyecto(args.proyecto)
        archivo = args.entorno.resolve()
        datos = leer_entorno(archivo)
        validar(datos, archivo)
        prefijo = comando(archivo, args.proyecto)
        if args.accion == "respaldo":
            respaldo(prefijo, datos, args.salida.absolute())
        elif args.accion == "restaurar":
            restaurar(prefijo, datos, args.archivo.absolute(), args.base)
        print("Operación completada: " + args.accion + ".")
        return 0
    except ErrorOperacion as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print("No se pudo leer, escribir o verificar los archivos de operación.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Operación interrumpida; revise el destino antes de reintentar.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
