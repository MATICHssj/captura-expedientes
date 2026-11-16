"""Lógica determinista: aquí se hacen las cuentas, NUNCA en el modelo."""
from dataclasses import dataclass, field
from typing import Optional
from .schemas import DocExtraction


@dataclass
class Expediente:
    docs: list[DocExtraction] = field(default_factory=list)


def _first(docs, tipo):
    return [d for d in docs if d.tipo == tipo and getattr(d, tipo) is not None]


def promedio_abonos(estados) -> tuple[Optional[float], int, list[str]]:
    """Promedio de abonos de los 3 estados de cuenta más recientes."""
    avisos = []
    vistos, unicos = set(), []
    for e in estados:
        if e.total_depositos_abonos is None:
            avisos.append(f"Estado de cuenta {e.banco or ''} {e.periodo_fin or ''} sin total de abonos legible.")
            continue
        k = (e.banco, e.periodo_fin)
        if k in vistos:
            continue
        vistos.add(k)
        unicos.append(e)
        # cuadre: si el resumen y la suma de movimientos difieren >2%, avisar
        s = e.suma_abonos_movimientos
        if s and abs(s - e.total_depositos_abonos) / e.total_depositos_abonos > 0.02:
            avisos.append(
                f"{e.banco} {e.periodo_fin}: resumen ${e.total_depositos_abonos:,.2f} vs movimientos ${s:,.2f}. Revisar.")
    unicos.sort(key=lambda e: e.periodo_fin or "", reverse=True)
    ult = unicos[:3]
    if not ult:
        return None, 0, avisos
    if len(ult) < 3:
        avisos.append(f"Solo recibí {len(ult)} estado(s) de cuenta con total; el promedio usa esos.")
    return sum(e.total_depositos_abonos for e in ult) / len(ult), len(ult), avisos


def armar_resumen(docs: list[DocExtraction], correcciones: dict | None = None) -> dict:
    ine = next((d.ine for d in _first(docs, "ine")), None)
    sol = next((d.solicitud for d in _first(docs, "solicitud")), None)
    cot = next((d.cotizacion for d in _first(docs, "cotizacion")), None)
    estados = [d.estado_cuenta for d in _first(docs, "estado_cuenta")]
    avisos = []

    # Dirección: INE primero; si no trae calle, la de la solicitud
    dir_fuente, d = None, None
    if ine and ine.calle_numero:
        d, dir_fuente = ine, "INE"
    elif sol and sol.calle_numero:
        d, dir_fuente = sol, "solicitud (la INE no trae calle)"
    elif ine:
        d, dir_fuente = ine, "INE (sin calle)"
    direccion = None
    if d:
        direccion = ", ".join(x for x in [d.calle_numero, d.colonia, f"CP {d.cp}" if d.cp else None,
                                         d.municipio_estado] if x)

    prom, n_usados, av = promedio_abonos(estados)
    avisos += av
    for doc in docs:
        if not doc.legible:
            avisos.append(f"Un documento ({doc.tipo}) salió ilegible; mándalo de nuevo.")
        avisos += [f"{doc.tipo}: {x}" for x in doc.dudas]

    r = {
        "nombre": (ine.nombre_completo if ine and ine.nombre_completo else sol.nombre_completo if sol else None),
        "fecha_nacimiento": ine.fecha_nacimiento if ine else None,
        "direccion": direccion, "direccion_fuente": dir_fuente,
        "correo": sol.correo if sol else None,
        "celular": sol.telefono_celular if sol else None,
        "promedio_abonos": prom, "n_estados": n_usados,
        "auto": cot, "avisos": avisos,
    }
    for campo, valor in (correcciones or {}).items():
        if campo in ("modelo", "anio", "precio"):
            from .schemas import Cotizacion
            r["auto"] = (r["auto"] or Cotizacion()).model_copy(
                update={campo: int(valor) if campo == "anio" else float(valor) if campo == "precio" else valor})
        else:
            r[campo] = valor
            if campo == "direccion":
                r["direccion_fuente"] = "corregida a mano"
    return r


def formato_whatsapp(r: dict) -> str:
    n = lambda v: v if v else "— no proporcionado"
    L = ["*RESUMEN DE EXPEDIENTE*",
         f"👤 Nombre: {n(r['nombre'])}",
         f"🎂 Nacimiento: {n(r['fecha_nacimiento'])}",
         f"🏠 Dirección: {n(r['direccion'])}" + (f" _(fuente: {r['direccion_fuente']})_" if r['direccion_fuente'] else ""),
         f"📧 Correo: {n(r['correo'])}",
         f"📱 Celular: {n(r['celular'])}"]
    p = r["promedio_abonos"]
    L.append(f"💰 Promedio abonos ({r['n_estados']} edos. cta.): " + (f"${p:,.2f}" if p is not None else "— no proporcionado"))
    c = r["auto"]
    if c:
        pr = f"${c.precio:,.2f}" if c.precio else "—"
        L.append(f"🚗 Auto: {' '.join(str(x) for x in [c.marca, c.modelo, c.anio] if x) or '—'} | Precio: {pr}")
    else:
        L.append("🚗 Auto: — no proporcionado")
    if r["avisos"]:
        L.append("\n⚠️ *Revisar:*")
        L += [f"• {a}" for a in r["avisos"]]
    return "\n".join(L)


def faltantes(docs: list[DocExtraction]) -> list[str]:
    ok = [d for d in docs if d.legible]
    tipos = [d.tipo for d in ok]
    f = []
    if "ine" not in tipos: f.append("INE")
    if "solicitud" not in tipos: f.append("Solicitud")
    if "cotizacion" not in tipos: f.append("Cotización")
    ests = {(d.estado_cuenta.banco, d.estado_cuenta.periodo_fin) for d in ok
            if d.tipo == "estado_cuenta" and d.estado_cuenta}
    if len(ests) < 3: f.append(f"Estados de cuenta (faltan {3 - len(ests)})")
    return f
