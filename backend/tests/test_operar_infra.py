"""Operación aislada: ningún test invoca Docker ni una base real."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def operar():
    spec = importlib.util.spec_from_file_location("operar", ROOT / "infra/operar.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def entorno(tmp_path):
    tls = tmp_path / "tls"
    tls.mkdir()
    for name in ("fullchain.pem", "privkey.pem"):
        (tls / name).write_text("certificado de prueba")
    values = {
        "ENTORNO": "produccion", "API_ORIGEN": "https://recursos.uti.edu.ec",
        "AUTH_SECRETO": "s3guro-aleatorio-" * 4, "SMTP_MODO": "smtp",
        "SMTP_HOST": "smtp.uti.edu.ec", "SMTP_REMITENTE": "recursos@uti.edu.ec",
        "ADMINISTRADORES": '["admin@uti.edu.ec", "otro@indoamerica.edu.ec"]',
        "RED_PROXY": "172.29.8.0/24", "IP_PROXY": "172.29.8.10",
        "RANGO_DINAMICO": "172.29.8.128/25", "TLS_DIR": "tls", "DOMINIO": "recursos.uti.edu.ec",
        "POSTGRES_DB": "recursos", "POSTGRES_USER": "operador",
        "POSTGRES_PASSWORD": "clave-aleatoria-9z7w2q" * 2,
    }
    path = tmp_path / "operacion.env"

    def write(**changes):
        data = values | changes
        path.write_text("\n".join(f"{k}='{v}'" for k, v in data.items()), encoding="utf-8")
        return path

    return write


def invoke(operar, entorno, *args):
    return operar.main(["--entorno", str(entorno()), *args])


@pytest.mark.parametrize("project", ["genrecursos", "rootdev", "genrecursos-db", "../otro", "-otro", ""])
def test_proyectos_protegidos_sin_docker(operar, entorno, monkeypatch, project):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("Docker invocado"))
    assert invoke(operar, entorno, "--proyecto", project, "validar") != 0


def test_validar_no_invoca_docker_ni_revela_secretos(operar, entorno, monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("Docker invocado"))
    assert invoke(operar, entorno, "validar") == 0
    output = capsys.readouterr()
    assert "s3guro" not in output.out + output.err
    assert "clave-aleatoria" not in output.out + output.err


@pytest.mark.parametrize("change", [
    {"API_ORIGEN": "http://recursos.uti.edu.ec"},
    {"API_ORIGEN": "https://recursos.uti.edu.ec/ruta"},
    {"AUTH_SECRETO": "x" * 31}, {"AUTH_SECRETO": "cambiar-por-un-secreto-largo-123456789"},
    {"POSTGRES_PASSWORD": "changeme"}, {"SMTP_MODO": "consola"},
    {"SMTP_MODO": "deshabilitado"}, {"SMTP_HOST": ""}, {"SMTP_REMITENTE": ""},
    {"ADMINISTRADORES": "[]"}, {"ADMINISTRADORES": "{}"},
    {"ADMINISTRADORES": '["user@gmail.com"]'}, {"ADMINISTRADORES": "secreto-malformado"},
    {"RED_PROXY": "0.0.0.0/0"}, {"RED_PROXY": "::/64"},
    {"IP_PROXY": "172.29.9.1"}, {"IP_PROXY": "172.29.8.0"},
    {"IP_PROXY": "172.29.8.255"}, {"IP_PROXY": "172.29.8.10/32"},
    {"RANGO_DINAMICO": "172.29.8.0/25"}, {"RANGO_DINAMICO": "172.29.9.0/25"},
    {"RANGO_DINAMICO": "172.29.8.128/31"}, {"RANGO_DINAMICO": "172.29.8.129/25"},
    {"LIMITE_IP_MINUTO": "0"}, {"LIMITE_IP_MINUTO": "abc"}, {"LIMITE_IP_MINUTO": "100001"},
    {"LIMITE_IP_MINUTO": "-5"}, {"AUDITORIA_RETENCION_DIAS": "366"}, {"LIMITE_PDF_CORREO_HORA": "1.5"},
    {"TLS_DIR": "inexistente"}, {"DOMINIO": "https://host/ruta"},
    {"POSTGRES_PASSWORD": "a" * 31}, {"POSTGRES_PASSWORD": "valid-" * 8 + "@"},
    {"POSTGRES_USER": "user@db"}, {"POSTGRES_DB": "db/name"},
])
def test_validacion_falla_sin_valores_sensibles(operar, entorno, capsys, change):
    assert operar.main(["--entorno", str(entorno(**change)), "validar"]) == 1
    out = capsys.readouterr()
    assert "secreto-malformado" not in out.out + out.err


def test_limites_admitidos(operar, entorno):
    """Con NAT institucional se sube la cuota por IP; los límites son opcionales."""
    assert operar.main(["--entorno", str(entorno(LIMITE_IP_MINUTO="5000", AUDITORIA_RETENCION_DIAS="90")), "validar"]) == 0


def test_desarrollo_sin_smtp(operar, entorno):
    assert operar.main(["--entorno", str(entorno(ENTORNO="desarrollo", SMTP_MODO="deshabilitado", SMTP_HOST="", SMTP_REMITENTE="", ADMINISTRADORES="[]")), "validar"]) == 0


def fake_docker(monkeypatch, *, exists=False, failure=None):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        script = args[args.index("-c") + 1]
        if failure and failure in script:
            raise subprocess.CalledProcessError(1, args, stderr=b"PASSWORD-SECRETO")
        if "pg_dump" in script:
            kwargs["stdout"].write(b"PGDMP-synthetic-backup")
        if "pg_restore" in script:
            assert kwargs["stdin"].read() == b"PGDMP-synthetic-backup"
        return subprocess.CompletedProcess(args, 0, stdout=b"1\n" if exists else b"", stderr=b"")

    monkeypatch.setattr(subprocess, "run", run)
    return calls


def test_respaldo_stream_manifest_permisos_y_argumentos(operar, entorno, tmp_path, monkeypatch):
    calls = fake_docker(monkeypatch)
    monkeypatch.setenv("POSTGRES_PASSWORD", "override-host-no-usar")
    path = tmp_path / "copia.dump"
    assert invoke(operar, entorno, "respaldo", "--salida", str(path)) == 0
    assert path.read_bytes() == b"PGDMP-synthetic-backup"
    assert Path(str(path) + ".sha256").read_text().strip() == hashlib.sha256(path.read_bytes()).hexdigest()
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
        assert Path(str(path) + ".sha256").stat().st_mode & 0o777 == 0o600
    args, kwargs = calls[0]
    assert args[:7] == ["docker", "compose", "--env-file", str(entorno()), "--project-name", "genrecursos-app", "-f"]
    assert args[7] == str(ROOT / "infra/compose.yaml")
    assert args[8:12] == ["exec", "-T", "db", "sh"]
    assert "--format=custom" in args[13]
    assert '"$POSTGRES_DB"' in args[13]
    assert "clave-aleatoria" not in repr(args)
    assert kwargs.get("shell", False) is False
    assert kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs["env"]["POSTGRES_PASSWORD"] == "clave-aleatoria-9z7w2q" * 2


@pytest.mark.parametrize("sidecar", [False, True])
def test_respaldo_no_sobrescribe(operar, entorno, tmp_path, monkeypatch, sidecar):
    calls = fake_docker(monkeypatch)
    path = tmp_path / "copia.dump"
    occupied = Path(str(path) + ".sha256") if sidecar else path
    occupied.write_bytes(b"previo")
    assert invoke(operar, entorno, "respaldo", "--salida", str(path)) == 1
    assert occupied.read_bytes() == b"previo"
    assert not calls


def test_respaldo_fallido_limpia_temporales_sin_secretos(operar, entorno, tmp_path, monkeypatch, capsys):
    fake_docker(monkeypatch, failure="pg_dump")
    path = tmp_path / "copia.dump"
    assert invoke(operar, entorno, "respaldo", "--salida", str(path)) == 1
    assert not path.exists()
    assert not list(tmp_path.glob(".operar-*"))
    assert "PASSWORD-SECRETO" not in str(capsys.readouterr())


def archive(tmp_path):
    path = tmp_path / "copia.dump"
    path.write_bytes(b"PGDMP-synthetic-backup")
    Path(str(path) + ".sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "\n")
    return path


@pytest.mark.parametrize("name", ["recursos", "postgres", "template0", "template1", "x;DROP DATABASE recursos", "-x", "x" * 64])
def test_restore_nombre_rechazado_sin_docker(operar, entorno, tmp_path, monkeypatch, name):
    calls = fake_docker(monkeypatch)
    assert invoke(operar, entorno, "restaurar", "--archivo", str(archive(tmp_path)), "--base", name) == 1
    assert not calls


def test_restore_hash_antes_de_docker(operar, entorno, tmp_path, monkeypatch):
    calls = fake_docker(monkeypatch)
    path = archive(tmp_path)
    path.write_bytes(b"alterado")
    assert invoke(operar, entorno, "restaurar", "--archivo", str(path), "--base", "prueba") == 1
    assert not calls


def test_restore_rechaza_existente(operar, entorno, tmp_path, monkeypatch):
    calls = fake_docker(monkeypatch, exists=True)
    assert invoke(operar, entorno, "restaurar", "--archivo", str(archive(tmp_path)), "--base", "prueba") == 1
    assert len(calls) == 1


def test_restore_crea_owner_y_stream_sin_clean(operar, entorno, tmp_path, monkeypatch):
    calls = fake_docker(monkeypatch)
    assert invoke(operar, entorno, "restaurar", "--archivo", str(archive(tmp_path)), "--base", "prueba") == 0
    assert len(calls) == 3
    scripts = [args[13] for args, _ in calls]
    assert "pg_database" in scripts[0]
    assert 'OWNER :"owner"' in scripts[1]
    assert "--exit-on-error" in scripts[2] and "--clean" not in scripts[2]
    assert calls[2][0][-1] == "prueba"
    assert all(kwargs["stderr"] == subprocess.DEVNULL for _, kwargs in calls)


def test_restore_fallido_no_borra_base(operar, entorno, tmp_path, monkeypatch, capsys):
    calls = fake_docker(monkeypatch, failure="pg_restore")
    assert invoke(operar, entorno, "restaurar", "--archivo", str(archive(tmp_path)), "--base", "prueba") == 1
    assert len(calls) == 3
    output = capsys.readouterr()
    assert "conserva" in output.err
    assert "PASSWORD-SECRETO" not in output.err


def test_dotenv_no_ejecuta_y_rechaza_interpolacion(operar, entorno, monkeypatch):
    calls = fake_docker(monkeypatch)
    path = entorno()
    with path.open("a") as stream:
        stream.write("\nOTRA=${POSTGRES_PASSWORD}\n")
    assert operar.main(["--entorno", str(path), "validar"]) == 1
    assert not calls
