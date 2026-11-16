"""Validaciones en código: detectan lecturas sospechosas sin depender del modelo."""
import re, unicodedata
from datetime import date
from .schemas import DocExtraction

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
CURP_RE = re.compile(r"^[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d$")
TYPOS_DOMINIO = {"gmial.com": "gmail.com", "gamil.com": "gmail.com", "gmail.con": "gmail.com",
                 "gmai.com": "gmail.com", "hotmial.com": "hotmail.com", "hotmail.con": "hotmail.com",
                 "hotmal.com": "hotmail.com", "outlok.com": "outlook.com", "yaho.com": "yahoo.com",
                 "yahoo.com.mx.": "yahoo.com.mx", "gmail.com.mx": "gmail.com"}


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
    c = correo.strip().replace(" ", "").lower()
    if "@" in c:
        usuario, dom = c.rsplit("@", 1)
        if dom in TYPOS_DOMINIO:
            return f"{usuario}@{TYPOS_DOMINIO[dom]}", f"dominio '{dom}' parece error de dedo; lo cambié a {TYPOS_DOMINIO[dom]}"
    return c, None


def validar(d: DocExtraction) -> list[str]:
    """Revisa y normaliza en el lugar. Regresa lista de problemas encontrados."""
    p = []
    if d.ine:
        i = d.ine
        if i.curp:
            i.curp = i.curp.replace(" ", "").upper()
            if not CURP_RE.match(i.curp):
                p.append(f"CURP '{i.curp}' no tiene formato válido")
            else:
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
        if i.vigencia and i.vigencia < date.today().year:
            p.append(f"la INE venció en {i.vigencia}")
    if d.solicitud:
        s = d.solicitud
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
            s.telefono_celular = dig
            if len(dig) != 10:
                p.append(f"celular '{dig}' no tiene 10 dígitos")
        if s.cp and not re.fullmatch(r"\d{5}", s.cp.strip()):
            p.append(f"CP '{s.cp}' no tiene 5 dígitos")
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
