import os
os.environ.setdefault("ANTHROPIC_API_KEY", "prueba")
os.environ["COOKIE_SECURE"] = "0"
import pytest
from fastapi.testclient import TestClient
from app import db
from app.schemas import DocExtraction, EstadoCuenta

JPG = b"\xff\xd8\xff\xe0" + b"0" * 2000
PDF = b"%PDF-1.4 " + b"0" * 2000


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    from app import web
    web._fallos.clear()
    db.iniciar()
    db.crear_cliente("ana@agencia.mx", "Agencia Norte", "secreta123", limite_mes=2)
    llamadas = []

    def falso(data, mime):
        llamadas.append(mime)
        if data.startswith(b"%PDF-1.4 FALLA"):
            raise RuntimeError("api caída")
        return [DocExtraction(tipo="estado_cuenta", estado_cuenta=EstadoCuenta(banco="BBVA", periodo_fin="2026-10-31", total_depositos_abonos=1000))], ["nota"]
    monkeypatch.setattr("app.extractor.extraer_documentos", falso)
    with TestClient(web.app) as c:
        c.llamadas = llamadas
        yield c


def entrar(c, pw="secreta123"):
    return c.post("/api/login", json={"email": "ANA@agencia.mx ", "password": pw})


def test_pagina_y_sin_sesion(cli):
    assert cli.get("/").status_code == 200 and "Captura de Expedientes" in cli.get("/").text
    assert cli.get("/api/me").status_code == 401
    assert cli.post("/api/leer", files={"archivo": ("a.jpg", JPG, "image/jpeg")}).status_code == 401


def test_login_y_uso(cli):
    assert entrar(cli, "mala").status_code == 401
    assert entrar(cli).status_code == 200
    me = cli.get("/api/me").json()
    assert me["empresa"] == "Agencia Norte" and me["uso"] == {"usados": 0, "limite": 2, "mes": db.mes_actual()}
    r = cli.post("/api/leer", files={"archivo": ("edo.pdf", PDF, "application/pdf")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["documentos"][0]["estado_cuenta"]["total_depositos_abonos"] == 1000 and j["uso"]["usados"] == 1
    assert cli.llamadas == ["application/pdf"]


def test_limite_y_devolucion_si_falla(cli):
    entrar(cli)
    assert cli.post("/api/leer", files={"archivo": ("x.pdf", b"%PDF-1.4 FALLA" + b"0" * 100, "application/pdf")}).status_code == 502
    assert cli.get("/api/me").json()["uso"]["usados"] == 0          # el fallo no se cobra
    for _ in range(2):
        assert cli.post("/api/leer", files={"archivo": ("a.jpg", JPG, "image/jpeg")}).status_code == 200
    r = cli.post("/api/leer", files={"archivo": ("a.jpg", JPG, "image/jpeg")})
    assert r.status_code == 402 and "límite" in r.json()["detail"]


def test_tipo_real_del_archivo(cli):
    entrar(cli)
    r = cli.post("/api/leer", files={"archivo": ("virus.pdf", b"MZ\x90\x00" + b"0" * 100, "application/pdf")})
    assert r.status_code == 415
    assert cli.llamadas == []


def test_bloqueo_por_intentos_y_otro_sitio(cli):
    for _ in range(5):
        entrar(cli, "mala")
    assert entrar(cli).status_code == 429                              # bloqueado aunque ahora sea correcta
    r = cli.post("/api/logout", headers={"Origin": "https://sitio-malo.com"})
    assert r.status_code == 403


def test_desactivar_cierra_sesion(cli):
    entrar(cli)
    assert cli.get("/api/me").status_code == 200
    db.actualizar_cliente("ana@agencia.mx", activo=0)
    assert cli.get("/api/me").status_code == 401
    assert entrar(cli).status_code == 401


def test_admin_cli(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "a.db"))
    from app.admin import main
    assert main(["crear", "--email", "b@x.mx", "--empresa", "Agencia Sur", "--limite", "300", "--password", "clave12345"]) == 0
    assert main(["crear", "--email", "b@x.mx", "--empresa", "Otra", "--password", "clave12345"]) == 1
    assert main(["crear", "--email", "c@x.mx", "--empresa", "Corta", "--password", "123"]) == 1
    assert main(["limite", "--email", "b@x.mx", "--limite", "500"]) == 0
    assert main(["desactivar", "--email", "b@x.mx"]) == 0
    main(["listar"])
    out = capsys.readouterr().out
    assert "Agencia Sur" in out and "0/500" in out and "INACTIVO" in out


def test_extractor_varios_documentos_y_segunda_lectura(monkeypatch):
    from app import extractor
    from app.schemas import Solicitud
    monkeypatch.setattr(extractor, "_bloques", lambda data, mime, notas: notas.append("enderecé 2°") or ["bloque"])
    lecturas = [
        [DocExtraction(tipo="estado_cuenta", estado_cuenta=EstadoCuenta(banco="BBVA", periodo_fin="2026-10-31", total_depositos_abonos=100)),
         DocExtraction(tipo="solicitud", solicitud=Solicitud(correo="ana@gmial.com", telefono_celular="5512345678"), dudas=["celular dudoso"])],
        [DocExtraction(tipo="estado_cuenta", estado_cuenta=EstadoCuenta(banco="BBVA", periodo_fin="2026-10-31", total_depositos_abonos=100)),
         DocExtraction(tipo="solicitud", solicitud=Solicitud(correo="ana@gmail.com", telefono_celular="5512345618"))],
    ]
    prompts = []
    monkeypatch.setattr(extractor, "_leer", lambda b, instr: prompts.append(instr) or lecturas[len(prompts) - 1])
    docs, notas = extractor.extraer_documentos(b"x", "image/jpeg")
    assert len(prompts) == 2 and "gmial" in prompts[1]                 # la 2a lectura recibe los problemas
    assert [d.tipo for d in docs] == ["estado_cuenta", "solicitud"] and notas == ["enderecé 2°"]
    sol = docs[1]
    assert sol.solicitud.telefono_celular == "5512345618"
    assert any("1a lectura '5512345678'" in x for x in sol.dudas)       # cambió entre lecturas -> se marca
    assert docs[0].dudas == []


def test_cuenta_beta_desde_variables(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "beta.db"))
    monkeypatch.setenv("BETA_EMAIL", "equipo@beta.mx")
    monkeypatch.setenv("BETA_PASSWORD", "probando2026")
    from app import web
    web._fallos.clear()
    for _ in range(2):                                   # dos arranques: no truena si ya existe
        with TestClient(web.app) as c:
            assert c.post("/api/login", json={"email": "equipo@beta.mx", "password": "probando2026"}).status_code == 200
            assert c.get("/api/me").json()["uso"]["limite"] == 200


def test_busca_de_nuevo_lo_que_falta(monkeypatch):
    from app import extractor
    from app.schemas import Solicitud, INE
    monkeypatch.setattr(extractor, "_bloques", lambda data, mime, notas: ["bloque"])
    completa = Solicitud(nombre_completo="Ana Ruiz", correo="ana@gmail.com", telefono_celular="5512345678", calle_numero="Ermita 2", cp="09510")
    lecturas = [[DocExtraction(tipo="solicitud", solicitud=completa.model_copy(update={"correo": None}))],
                [DocExtraction(tipo="solicitud", solicitud=completa)]]
    prompts = []
    monkeypatch.setattr(extractor, "_leer", lambda b, instr: prompts.append(instr) or lecturas[len(prompts) - 1])
    docs, _ = extractor.extraer_documentos(b"x", "image/jpeg")
    assert len(prompts) == 2 and "falta correo" in prompts[1]
    assert docs[0].solicitud.correo == "ana@gmail.com"
    # el reverso de la INE no trae nombre: no dispara otra búsqueda
    assert extractor.faltantes(DocExtraction(tipo="ine", descripcion="INE reverso", ine=INE())) == []
    assert "curp" in extractor.faltantes(DocExtraction(tipo="ine", descripcion="INE frente", ine=INE(nombre_completo="ANA")))
