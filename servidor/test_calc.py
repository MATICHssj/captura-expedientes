from app.calc import armar_resumen, formato_whatsapp
from app.schemas import *

def ec(fin, tot, banco="BBVA"):
    return DocExtraction(tipo="estado_cuenta", estado_cuenta=EstadoCuenta(banco=banco, periodo_fin=fin, total_depositos_abonos=tot))

def test_promedio_ultimos_3_y_direccion_de_solicitud():
    docs = [ec("2026-05-31", 10000), ec("2026-06-30", 20000), ec("2026-07-31", 30000), ec("2026-01-31", 999999),
            DocExtraction(tipo="ine", ine=INE(nombre_completo="JUAN PEREZ", fecha_nacimiento="1990-02-03", colonia="CENTRO", cp="06000")),
            DocExtraction(tipo="solicitud", solicitud=Solicitud(correo="a@b.com", telefono_celular="5512345678", calle_numero="Reforma 10", colonia="Centro")),
            DocExtraction(tipo="cotizacion", cotizacion=Cotizacion(marca="Nissan", modelo="Versa", anio=2026, precio=350000))]
    r = armar_resumen(docs)
    assert r["promedio_abonos"] == 20000
    assert "Reforma 10" in r["direccion"] and "solicitud" in r["direccion_fuente"]
    print(formato_whatsapp(r))

def test_sin_datos():
    assert armar_resumen([])["promedio_abonos"] is None


# ---- lectura robusta ----
import io
from PIL import Image, ImageDraw, ImageFilter
from app.preprocess import calidad_baja, preparar_imagen
from app.validators import fecha_desde_curp, validar


def _foto(w, h, borrosa=False):
    img = Image.new("RGB", (w, h), "white")
    dr = ImageDraw.Draw(img)
    for y in range(20, h, 40):
        dr.text((20, y), "JUAN PEREZ LOPEZ  calle 5 de mayo 123", fill="black")
    if borrosa:
        img = img.filter(ImageFilter.GaussianBlur(12))
    b = io.BytesIO(); img.save(b, "JPEG"); return b.getvalue()


def test_preprocesado_tamanos():
    orig, realz, _ = preparar_imagen(_foto(800, 1000))
    assert max(Image.open(io.BytesIO(orig)).size) == 1400       # agrandada
    orig, _, _ = preparar_imagen(_foto(5000, 3000))
    assert max(Image.open(io.BytesIO(orig)).size) == 2400       # reducida
    assert len(orig) < 4_500_000


def test_detecta_foto_mala():
    assert calidad_baja(_foto(300, 400)) is not None
    assert "borrosa" in calidad_baja(_foto(1200, 1600, borrosa=True))
    assert calidad_baja(_foto(1200, 1600)) is None


def test_curp_y_validaciones():
    assert fecha_desde_curp("PELJ900203HDFRPN08") == "1990-02-03"
    d = DocExtraction(tipo="ine", ine=INE(curp="PELJ900203HDFRPN08", fecha_nacimiento="1990-02-08"))
    assert any("no coincide" in p for p in validar(d))
    d = DocExtraction(tipo="ine", ine=INE(curp="pelj 900203hdfrpn08"))
    assert validar(d) == [] and d.ine.fecha_nacimiento == "1990-02-03"   # la saca de la CURP
    s = DocExtraction(tipo="solicitud", solicitud=Solicitud(correo="Juan.Perez @Gmial.com", telefono_celular="+52 (55) 1234-5678"))
    p = validar(s)
    assert s.solicitud.correo == "juan.perez@gmail.com" and s.solicitud.telefono_celular == "5512345678"
    assert any("gmial" in x for x in p)


def test_correcciones_manuales():
    docs = [DocExtraction(tipo="solicitud", solicitud=Solicitud(correo="mal@x"))]
    r = armar_resumen(docs, {"correo": "bien@gmail.com", "precio": "420000"})
    assert r["correo"] == "bien@gmail.com" and r["auto"].precio == 420000


# ---- verificaciones nuevas ----
from app.validators import curp_vs_nombre, monto_en_texto


def test_curp_vs_nombre_y_vigencia_y_edad():
    assert curp_vs_nombre("HERG880714MDFRZD05", "MARÍA GUADALUPE HERNÁNDEZ RUIZ")
    assert not curp_vs_nombre("PELJ900203HDFRPN09", "MARÍA GUADALUPE HERNÁNDEZ RUIZ")
    assert curp_vs_nombre("NUXA900101HDFXXX01", "Ana Núñez")            # X = sin dato / Ñ
    d = DocExtraction(tipo="ine", ine=INE(curp="PELJ900203HDFRPN09", nombre_completo="ANA LOPEZ RUIZ", vigencia=2020))
    p = validar(d)
    assert any("iniciales" in x for x in p) and any("venció" in x for x in p)
    d = DocExtraction(tipo="ine", ine=INE(curp="PELJ150203HDFRPNA9", nombre_completo="JUAN PEREZ LOPEZ"))
    assert any("edad" in x for x in validar(d))                         # nacido en 2015: menor de edad


def test_saldos_cuadran_y_evidencia():
    ok = EstadoCuenta(saldo_inicial=10000, total_depositos_abonos=31250.40, total_retiros_cargos=25100, saldo_final=16150.40,
                      evidencia_total="Depósitos / Abonos (+)  $31,250.40")
    assert validar(DocExtraction(tipo="estado_cuenta", estado_cuenta=ok)) == []
    mal = ok.model_copy(update={"saldo_final": 19150.40})
    assert any("no cuadran" in x for x in validar(DocExtraction(tipo="estado_cuenta", estado_cuenta=mal)))
    cita = ok.model_copy(update={"evidencia_total": "Depósitos / Abonos (+) 37,250.40"})
    assert any("renglón citado" in x for x in validar(DocExtraction(tipo="estado_cuenta", estado_cuenta=cita)))
    assert monto_en_texto(1500, "Abonos $ 1,500.00") and not monto_en_texto(1500.5, "Abonos 1,500.00")


def test_total_verificado_contra_texto_del_pdf():
    from app.extractor import _verificar_contra_pdf
    texto = "BBVA Resumen del periodo " + "relleno " * 60 + " Depósitos / Abonos 31,250.40"
    bien = DocExtraction(tipo="estado_cuenta", estado_cuenta=EstadoCuenta(total_depositos_abonos=31250.40))
    mal = DocExtraction(tipo="estado_cuenta", estado_cuenta=EstadoCuenta(total_depositos_abonos=37250.40))
    _verificar_contra_pdf([bien, mal], texto)
    assert bien.dudas == [] and "no aparece en el texto del PDF" in mal.dudas[0]


def test_monto_completo_no_pedazos():
    assert not monto_en_texto(1500, "Abonos 21,500.00")
    assert monto_en_texto(1500, "Abonos $1500.00 y otros")
    assert monto_en_texto(1234567.89, "Total 1,234,567.89")
    assert monto_en_texto(1234567.89, "Total 1 234 567.89")


def test_comprobante_domicilio():
    from app.schemas import ComprobanteDomicilio
    d = DocExtraction(tipo="comprobante_domicilio", descripcion="Recibo CFE",
                      comprobante_domicilio=ComprobanteDomicilio(titular="ANA", cp="0951", fecha_emision="2026-02-30"))
    p = validar(d)
    assert any("CP del comprobante" in x for x in p) and any("fecha del comprobante" in x for x in p)
    ok = DocExtraction(tipo="comprobante_domicilio", comprobante_domicilio=ComprobanteDomicilio(cp="09510", fecha_emision="2026-10-20"))
    assert validar(ok) == []


def test_guia_en_instrucciones():
    import os
    os.environ.setdefault("ANTHROPIC_API_KEY", "prueba")
    from app import extractor
    assert "comprobante_domicilio" in extractor.SYSTEM and "IDMEX" in extractor.SYSTEM and "{" not in extractor.SYSTEM


# ---- verificaciones de lectura: dígito verificador, letra/número, CP vs estado ----
from app.validators import curp_valida, reparar_curp, estado_de_texto, cp_no_cuadra


def test_curp_digito_verificador_y_reparacion():
    assert curp_valida("PELJ900203HDFRPN08") and not curp_valida("PELJ900203HDFRPN09")
    d = DocExtraction(tipo="ine", ine=INE(curp="PELJ9OO2O3HDFRPN08"))   # O en vez de 0
    p = validar(d)
    assert d.ine.curp == "PELJ900203HDFRPN08" and any("corregí" in x for x in p)
    d = DocExtraction(tipo="ine", ine=INE(curp="PELJ900203HDFRPN09"))
    assert any("dígito verificador" in x for x in validar(d))


def test_cp_contra_estado():
    assert estado_de_texto("Iztapalapa, CDMX") == "CDMX" and estado_de_texto("Ecatepec, Edo. Méx.") == "MEX"
    assert estado_de_texto("Zapopan, Jal.") == "JAL" and estado_de_texto("Guerrero, Tamaulipas") is None
    assert estado_de_texto("Miguel Hidalgo, CDMX") == "CDMX" and estado_de_texto("Col. Centro") is None
    assert "Jalisco" in cp_no_cuadra("44510", "Iztapalapa, CDMX") and cp_no_cuadra("09510", "Iztapalapa, CDMX") is None
    s = DocExtraction(tipo="solicitud", solicitud=Solicitud(cp="44510", municipio_estado="Iztapalapa, CDMX", telefono_celular="044 55 1234 5678", correo="ANA,LOPEZ@GMAIL.CON"))
    p = validar(s)
    assert any("Jalisco" in x for x in p) and s.solicitud.telefono_celular == "5512345678" and s.solicitud.correo == "ana.lopez@gmail.com"


def test_solicitud_rfc_curp_y_fecha():
    s = DocExtraction(tipo="solicitud", solicitud=Solicitud(nombre_completo="ERIKA LESLIE LEDESMA MARTINEZ", rfc="leme921213je4", curp="LEME921213MDFRR01"))
    p = validar(s)
    assert s.solicitud.fecha_nacimiento == "1992-12-13" and s.solicitud.rfc == "LEME921213JE4"
    assert any("CURP" in x and "formato" in x for x in p)          # a la CURP le falta un carácter
    s = DocExtraction(tipo="solicitud", solicitud=Solicitud(rfc="LEME921213JE4", fecha_nacimiento="1992-12-31"))
    assert any("RFC" in x and "1992-12-13" in x for x in validar(s))
