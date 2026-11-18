"""Validaciones en código: detectan lecturas sospechosas sin depender del modelo."""
import re, unicodedata
from datetime import date
from .schemas import DocExtraction

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
CURP_RE = re.compile(r"^[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d$")
TYPOS_DOMINIO = {"gmial.com": "gmail.com", "gamil.com": "gmail.com", "gmail.con": "gmail.com",
                 "gmai.com": "gmail.com", "hotmial.com": "hotmail.com", "hotmail.con": "hotmail.com",
                 "hotmal.com": "hotmail.com", "outlok.com": "outlook.com", "yaho.com": "yahoo.com",
                 "yahoo.com.mx.": "yahoo.com.mx", "gmail.com.mx": "gmail.com", "hotmai.com": "hotmail.com",
                 "outlook.con": "outlook.com", "yahoo.con": "yahoo.com", "gmal.com": "gmail.com", "gmil.com": "gmail.com",
                 "gmaill.com": "gmail.com", "gnail.com": "gmail.com", "gmail.co": "gmail.com", "gmail.cm": "gmail.com",
                 "gmail.om": "gmail.com", "gmail": "gmail.com", "hotmaill.com": "hotmail.com", "hotmil.com": "hotmail.com",
                 "homail.com": "hotmail.com", "hotmail.co": "hotmail.com", "hotmail.cm": "hotmail.com", "hotmail": "hotmail.com",
                 "outlook.co": "outlook.com", "outlook": "outlook.com", "iclod.com": "icloud.com", "icloud.con": "icloud.com",
                 "live.con": "live.com", "yahoo.com.m": "yahoo.com.mx", "prodigy.net.m": "prodigy.net.mx"}

# --- CURP: dígito verificador oficial (RENAPO) y claves de estado ---
CURP_DIC = "0123456789ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"
CURP_EDOS = set("AS BC BS CC CL CM CS CH DF DG GT GR HG JC MC MN MS NT NL OC PL QT QR SP SL SR TC TS TL VZ YN ZS NE".split())
_A_LETRA = {"0": "O", "1": "I", "2": "Z", "4": "A", "5": "S", "6": "G", "7": "T", "8": "B"}
_A_DIGITO = {"O": "0", "D": "0", "Q": "0", "U": "0", "I": "1", "L": "1", "Z": "2", "S": "5", "B": "8", "G": "6", "T": "7", "A": "4"}


def digito_curp(c: str) -> int:
    return (10 - sum(CURP_DIC.index(ch) * (18 - i) for i, ch in enumerate(c[:17])) % 10) % 10


def curp_valida(c: str | None) -> bool:
    return bool(c and CURP_RE.match(c) and c[11:13] in CURP_EDOS and int(c[17]) == digito_curp(c))


def reparar_curp(c: str) -> str:
    """Corrige confusiones letra/número según la posición (cada posición de la CURP es solo letra o solo número)."""
    r = [(_A_LETRA.get(ch, ch) if (i <= 3 or 10 <= i <= 15) else _A_DIGITO.get(ch, ch) if (4 <= i <= 9 or i == 17) else ch)
         for i, ch in enumerate(c)]
    if len(r) == 18 and r[16].isalpha() and "".join(r[4:6]).isdigit() and int("".join(r[4:6])) > date.today().year % 100:
        r[16] = _A_DIGITO.get(r[16], r[16])          # nacido en 19xx: ahí va un dígito
    return "".join(r)


# --- Código postal → estado (SEPOMEX: los dos primeros dígitos) ---
CP_EDO = [(1, 16, "CDMX"), (20, 20, "AGS"), (21, 22, "BC"), (23, 23, "BCS"), (24, 24, "CAMP"), (25, 27, "COAH"), (28, 28, "COL"),
          (29, 30, "CHIS"), (31, 33, "CHIH"), (34, 35, "DGO"), (36, 38, "GTO"), (39, 41, "GRO"), (42, 43, "HGO"), (44, 49, "JAL"),
          (50, 57, "MEX"), (58, 61, "MICH"), (62, 62, "MOR"), (63, 63, "NAY"), (64, 67, "NL"), (68, 71, "OAX"), (72, 75, "PUE"),
          (76, 76, "QRO"), (77, 77, "QROO"), (78, 79, "SLP"), (80, 82, "SIN"), (83, 85, "SON"), (86, 86, "TAB"), (87, 89, "TAMPS"),
          (90, 90, "TLAX"), (91, 96, "VER"), (97, 97, "YUC"), (98, 99, "ZAC")]
NOMBRE_EDO = {"CDMX": "Ciudad de México", "AGS": "Aguascalientes", "BC": "Baja California", "BCS": "Baja California Sur",
              "CAMP": "Campeche", "COAH": "Coahuila", "COL": "Colima", "CHIS": "Chiapas", "CHIH": "Chihuahua", "DGO": "Durango",
              "GTO": "Guanajuato", "GRO": "Guerrero", "HGO": "Hidalgo", "JAL": "Jalisco", "MEX": "Estado de México",
              "MICH": "Michoacán", "MOR": "Morelos", "NAY": "Nayarit", "NL": "Nuevo León", "OAX": "Oaxaca", "PUE": "Puebla",
              "QRO": "Querétaro", "QROO": "Quintana Roo", "SLP": "San Luis Potosí", "SIN": "Sinaloa", "SON": "Sonora",
              "TAB": "Tabasco", "TAMPS": "Tamaulipas", "TLAX": "Tlaxcala", "VER": "Veracruz", "YUC": "Yucatán", "ZAC": "Zacatecas"}
_EDO_RE = [("AGS", r"\bAGUASCALIENTES\b|\bAGS\b"), ("BCS", r"\bBAJA CALIFORNIA SUR\b|\bB\.? ?C\.? ?S\b"),
           ("BC", r"\bBAJA CALIFORNIA\b(?! SUR)"), ("CAMP", r"\bCAMPECHE\b|\bCAMP\b"), ("COAH", r"\bCOAHUILA\b|\bCOAH\b"),
           ("COL", r"\bCOLIMA\b"), ("CHIS", r"\bCHIAPAS\b|\bCHIS\b"), ("CHIH", r"\bCHIHUAHUA\b|\bCHIH\b"),
           ("DGO", r"\bDURANGO\b|\bDGO\b"), ("GTO", r"\bGUANAJUATO\b|\bGTO\b"), ("GRO", r"\bGUERRERO\b|\bGRO\b"),
           ("HGO", r"\bHIDALGO\b|\bHGO\b"), ("JAL", r"\bJALISCO\b|\bJAL\b"), ("MICH", r"\bMICHOACAN\b|\bMICH\b"),
           ("MOR", r"\bMORELOS\b|\bMOR\b"), ("NAY", r"\bNAYARIT\b|\bNAY\b"), ("NL", r"\bNUEVO LEON\b|\bN\.? ?L\b"),
           ("OAX", r"\bOAXACA\b|\bOAX\b"), ("PUE", r"\bPUEBLA\b|\bPUE\b"), ("QROO", r"\bQUINTANA ROO\b|\bQ\.? ?ROO\b"),
           ("QRO", r"\bQUERETARO\b|\bQRO\b"), ("SLP", r"\bSAN LUIS POTOSI\b|\bS\.? ?L\.? ?P\b"), ("SIN", r"\bSINALOA\b"),
           ("SON", r"\bSONORA\b"), ("TAB", r"\bTABASCO\b|\bTAB\b"), ("TAMPS", r"\bTAMAULIPAS\b|\bTAMPS\b"),
           ("TLAX", r"\bTLAXCALA\b|\bTLAX\b"), ("VER", r"\bVERACRUZ\b|\bVER\b"), ("YUC", r"\bYUCATAN\b|\bYUC\b"),
           ("ZAC", r"\bZACATECAS\b|\bZAC\b")]
_ALCALDIAS = r"\b(IZTAPALAPA|COYOACAN|TLALPAN|GUSTAVO A\.? MADERO|AZCAPOTZALCO|IZTACALCO|TLAHUAC|XOCHIMILCO|MILPA ALTA|MAGDALENA CONTRERAS|CUAJIMALPA)\b"


def estado_de_cp(cp: str) -> str | None:
    n = int(str(cp)[:2])
    return next((e for a, b, e in CP_EDO if a <= n <= b), None)


def estado_de_texto(t: str | None) -> str | None:
    """Estado que menciona un domicilio; None si no menciona ninguno o es ambiguo."""
    s = _sin_acentos(t or "").upper()
    cdmx = bool(re.search(r"\bCDMX\b|\bC\.D\.M\.X\b|CIUDAD DE MEXICO|\bCD\.? DE MEXICO|\bD\.? ?F\b|DISTRITO FEDERAL", s))
    s = re.sub(r"CIUDAD DE MEXICO|\bCD\.? DE MEXICO|MEXICO,? D\.? ?F", " ", s)
    s = re.sub(r"MIGUEL HIDALGO|DOLORES HIDALGO|HIDALGO DEL PARRAL|CIUDAD HIDALGO|VICENTE GUERRERO|JOSE MARIA MORELOS|MORELOS Y PAVON|VALLE DE GUADALUPE", " ", s)
    hallados = {e for e, rx in _EDO_RE if re.search(rx, s)}
    if cdmx:
        hallados.add("CDMX")
    if re.search(r"\bESTADO DE MEXICO\b|\bEDO\.? ?(DE )?MEX|\bEDOMEX\b|\bMEX\b|\bMEXICO\b", s):
        hallados.add("MEX")
    if not hallados and re.search(_ALCALDIAS, s):
        hallados.add("CDMX")
    return hallados.pop() if len(hallados) == 1 else None


def cp_no_cuadra(cp: str | None, muni: str | None) -> str | None:
    """Problema si el CP no existe o no es del estado que dice el domicilio."""
    if not re.fullmatch(r"\d{5}", cp or ""):
        return None
    e1 = estado_de_cp(cp)
    if not e1:
        return f"el CP {cp} no existe (ningún CP de México empieza con {cp[:2]})"
    e2 = estado_de_texto(muni)
    if e2 and e2 != e1:
        return f"el CP {cp} es de {NOMBRE_EDO[e1]}, pero el domicilio dice '{muni}' ({NOMBRE_EDO[e2]}); revisa el CP y el estado"
    return None


def _fecha_ok(s: str | None) -> bool:
    try:
        y, m, d = map(int, (s or "").split("-"))
        return 1900 < y <= date.today().year and bool(date(y, m, d))
    except Exception:
        return False


def fecha_desde_curp(curp: str) -> str | None:
    """La CURP trae la fecha de nacimiento: posiciones 5-10 (AAMMDD); el carácter 17 indica el siglo."""
    if not curp or not CURP_RE.match(curp):
        return None
    aa, mm, dd = curp[4:6], curp[6:8], curp[8:10]
    siglo = "19" if curp[16].isdigit() else "20"
    return f"{siglo}{aa}-{mm}-{dd}"


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def curp_vs_nombre(curp: str, nombre: str) -> bool:
    """Letras 1, 3 y 4 de la CURP = iniciales de apellido paterno, materno y nombre.
    Revisión flexible: solo exige que esas letras sean iniciales de alguna palabra del nombre."""
    palabras = re.sub(r"[^A-ZÑ ]", " ", _sin_acentos(nombre).upper()).split()
    iniciales = {("X" if w[0] == "Ñ" else w[0]) for w in palabras}
    return all(c == "X" or c in iniciales for c in (curp[0], curp[2], curp[3]))


def _digitos(x) -> str:
    return re.sub(r"\D", "", str(x or ""))


_MONTO_RE = re.compile(r"(?<![\d.,])\d{1,3}(?:[,\s]?\d{3})*\.\d{2}(?!\d)")


def monto_en_texto(monto: float, texto: str) -> bool:
    """¿Aparece ese monto exacto (con centavos) en el texto? Compara números completos, no pedazos."""
    for m in _MONTO_RE.findall(texto or ""):
        try:
            if abs(float(re.sub(r"[,\s]", "", m)) - monto) < 0.005:
                return True
        except ValueError:
            pass
    return False


def corregir_correo(correo: str) -> tuple[str, str | None]:
    c = re.sub(r"\.{2,}", ".", correo.strip().replace(" ", "").lower().replace(",", ".")).rstrip(".")
    if "@" in c:
        usuario, dom = c.rsplit("@", 1)
        arreglo = TYPOS_DOMINIO.get(dom) or (dom[:-4] + ".com" if dom.endswith(".con") else None)
        if arreglo:
            return f"{usuario}@{arreglo}", f"dominio '{dom}' parece error de dedo; lo cambié a {arreglo}"
    return c, None


RFC_RE = re.compile(r"^[A-ZÑ&]{4}\d{6}([A-Z0-9]{3})?$")


def fecha_desde_rfc(rfc: str) -> str | None:
    if not re.match(r"^[A-ZÑ&]{4}\d{6}", rfc or ""):
        return None
    yy = int(rfc[4:6])
    return f"{19 if yy > date.today().year % 100 else 20}{rfc[4:6]}-{rfc[6:8]}-{rfc[8:10]}"


def revisar_identidad(i, p: list[str]) -> None:
    """CURP (dígito verificador, corrección letra/número), fecha de nacimiento y RFC de la INE o la solicitud."""
    if i.curp:
        i.curp = re.sub(r"[\s-]", "", i.curp).upper()
        if len(i.curp) == 18 and not curp_valida(i.curp):
            r = reparar_curp(i.curp)
            if r != i.curp and curp_valida(r):
                p.append(f"CURP: se leyó '{i.curp}' y la corregí a {r} (confusión entre letra y número; así sí pasa el dígito verificador)")
                i.curp = r
        if not CURP_RE.match(i.curp):
            p.append(f"CURP '{i.curp}' no tiene formato válido")
        else:
            if i.curp[11:13] not in CURP_EDOS:
                p.append(f"CURP {i.curp}: '{i.curp[11:13]}' no es una clave de estado válida; algún carácter está mal leído")
            elif int(i.curp[17]) != digito_curp(i.curp):
                p.append(f"la CURP {i.curp} no pasa el dígito verificador (con esos 17 caracteres terminaría en {digito_curp(i.curp)}): algún carácter está mal leído")
            fc = fecha_desde_curp(i.curp)
            if i.fecha_nacimiento and fc != i.fecha_nacimiento:
                p.append(f"fecha de nacimiento {i.fecha_nacimiento} no coincide con la CURP ({fc})")
            elif not i.fecha_nacimiento:
                i.fecha_nacimiento = fc
            if i.nombre_completo and not curp_vs_nombre(i.curp, i.nombre_completo):
                p.append(f"la CURP {i.curp} no corresponde a las iniciales del nombre '{i.nombre_completo}'")
    if i.fecha_nacimiento and not _fecha_ok(i.fecha_nacimiento):
        p.append(f"fecha de nacimiento '{i.fecha_nacimiento}' no es válida")
    elif i.fecha_nacimiento:
        y, m, dd = map(int, i.fecha_nacimiento.split("-"))
        hoy = date.today()
        edad = hoy.year - y - ((hoy.month, hoy.day) < (m, dd))
        if edad < 18 or edad > 85:
            p.append(f"la edad calculada ({edad} años) es poco común; revisa la fecha de nacimiento")
    rfc = getattr(i, "rfc", None)
    if rfc:
        i.rfc = rfc = re.sub(r"[\s-]", "", rfc).upper()
        if not RFC_RE.match(rfc):
            p.append(f"RFC '{rfc}' no tiene formato válido (4 letras, 6 números de la fecha y 3 de homoclave)")
        else:
            fr = fecha_desde_rfc(rfc)
            if i.fecha_nacimiento and _fecha_ok(i.fecha_nacimiento) and fr != i.fecha_nacimiento:
                p.append(f"el RFC {rfc} dice nacimiento {fr}, pero la fecha de nacimiento es {i.fecha_nacimiento}")
            elif not i.fecha_nacimiento and _fecha_ok(fr):
                i.fecha_nacimiento = fr
            if i.curp and len(i.curp) >= 10 and i.curp[:10] != rfc[:10]:
                p.append(f"el RFC {rfc} y la CURP {i.curp} no coinciden en los primeros 10 caracteres")


def validar(d: DocExtraction) -> list[str]:
    """Revisa y normaliza en el lugar. Regresa lista de problemas encontrados."""
    p = []
    if d.ine:
        i = d.ine
        revisar_identidad(i, p)
        if i.vigencia and i.vigencia < date.today().year:
            p.append(f"la INE venció en {i.vigencia}")
        if i.cp and (x := cp_no_cuadra(i.cp.strip(), i.municipio_estado)):
            p.append(x)
    if d.solicitud:
        s = d.solicitud
        revisar_identidad(s, p)
        if s.correo:
            s.correo, aviso = corregir_correo(s.correo)
            if aviso:
                p.append(aviso)
            if not EMAIL_RE.match(s.correo):
                p.append(f"correo '{s.correo}' no tiene formato válido")
        if s.telefono_celular:
            dig = re.sub(r"\D", "", s.telefono_celular)
            if len(dig) == 12 and dig.startswith("52"):
                dig = dig[2:]
            if len(dig) == 13 and (dig.startswith("521") or dig.startswith("044") or dig.startswith("045")):
                dig = dig[3:]
            s.telefono_celular = dig
            if len(dig) != 10:
                p.append(f"celular '{dig}' no tiene 10 dígitos")
            elif dig[0] in "01":
                p.append(f"celular {dig} empieza con {dig[0]}; en México ningún número empieza así, revisa el primer dígito")
        if s.cp and not re.fullmatch(r"\d{5}", s.cp.strip()):
            p.append(f"CP '{s.cp}' no tiene 5 dígitos")
        elif s.cp and (x := cp_no_cuadra(s.cp.strip(), s.municipio_estado)):
            p.append(x)
    if d.cotizacion:
        c = d.cotizacion
        if c.anio and not (2000 <= c.anio <= date.today().year + 2):
            p.append(f"año del auto '{c.anio}' fuera de rango")
        if c.precio is not None and not (50_000 <= c.precio <= 10_000_000):
            p.append(f"precio ${c.precio:,.0f} fuera de rango normal")
    if d.comprobante_domicilio:
        c = d.comprobante_domicilio
        if c.cp and not re.fullmatch(r"\d{5}", c.cp.strip()):
            p.append(f"CP del comprobante '{c.cp}' no tiene 5 dígitos")
        elif c.cp and (x := cp_no_cuadra(c.cp.strip(), c.municipio_estado)):
            p.append(x)
        if c.fecha_emision and not _fecha_ok(c.fecha_emision):
            p.append(f"fecha del comprobante '{c.fecha_emision}' no es válida")
    if d.estado_cuenta:
        e = d.estado_cuenta
        if e.periodo_fin and not _fecha_ok(e.periodo_fin):
            p.append(f"fecha de corte '{e.periodo_fin}' no es válida")
        if e.total_depositos_abonos is not None and e.total_depositos_abonos < 0:
            p.append("total de abonos negativo")
        si, ab, ca, sf = e.saldo_inicial, e.total_depositos_abonos, e.total_retiros_cargos, e.saldo_final
        if None not in (si, ab, ca, sf):
            calc = si + ab - ca
            if abs(calc - sf) > max(1.0, 0.005 * max(abs(sf), 1)):
                p.append(f"los saldos no cuadran: inicial {si:,.2f} + abonos {ab:,.2f} - cargos {ca:,.2f} = {calc:,.2f}, "
                         f"pero el saldo final dice {sf:,.2f} (error de lectura o documento alterado)")
        if e.total_depositos_abonos is not None and e.evidencia_total and not monto_en_texto(e.total_depositos_abonos, e.evidencia_total):
            p.append(f"el total {e.total_depositos_abonos:,.2f} no coincide con el renglón citado: '{e.evidencia_total}'")
    return p
