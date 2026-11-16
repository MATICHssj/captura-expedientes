"""Clientes, sesiones y uso mensual. SQLite: un solo archivo, suficiente para decenas de agencias."""
import hashlib, hmac, os, secrets, sqlite3, time
from contextlib import contextmanager
from datetime import datetime, timezone

SESION_DIAS = 7

ESQUEMA = """
CREATE TABLE IF NOT EXISTS clientes (
  id INTEGER PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  empresa TEXT NOT NULL,
  pass_hash TEXT NOT NULL,
  limite_mes INTEGER NOT NULL DEFAULT 100,
  activo INTEGER NOT NULL DEFAULT 1,
  creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sesiones (
  token_hash TEXT PRIMARY KEY,
  cliente_id INTEGER NOT NULL REFERENCES clientes(id),
  expira REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS uso (
  cliente_id INTEGER NOT NULL REFERENCES clientes(id),
  mes TEXT NOT NULL,
  documentos INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (cliente_id, mes)
);
"""


def ruta() -> str:
    return os.getenv("DB_PATH", "datos.db")


@contextmanager
def conexion():
    c = sqlite3.connect(ruta(), timeout=10)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def iniciar():
    with conexion() as c:
        c.executescript(ESQUEMA)


# ---------- contraseñas ----------
def _hash(password: str, sal: bytes) -> str:
    return hashlib.scrypt(password.encode(), salt=sal, n=2**14, r=8, p=1, dklen=32).hex()


def hash_password(password: str) -> str:
    sal = secrets.token_bytes(16)
    return f"scrypt${sal.hex()}${_hash(password, sal)}"


def password_ok(password: str, guardado: str) -> bool:
    try:
        _, sal, h = guardado.split("$")
        return hmac.compare_digest(_hash(password, bytes.fromhex(sal)), h)
    except Exception:
        return False


# ---------- clientes ----------
def crear_cliente(email: str, empresa: str, password: str, limite_mes: int = 100) -> int:
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres")
    with conexion() as c:
        cur = c.execute("INSERT INTO clientes (email, empresa, pass_hash, limite_mes, creado) VALUES (?,?,?,?,?)",
                        (email.strip().lower(), empresa.strip(), hash_password(password), limite_mes,
                         datetime.now(timezone.utc).isoformat()))
        return cur.lastrowid


def cliente_por_email(email: str):
    with conexion() as c:
        return c.execute("SELECT * FROM clientes WHERE email = ?", (email.strip().lower(),)).fetchone()


def actualizar_cliente(email: str, **campos):
    permitidos = {"empresa", "limite_mes", "activo"}
    sets = {k: v for k, v in campos.items() if k in permitidos and v is not None}
    if "password" in campos and campos["password"]:
        if len(campos["password"]) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        sets["pass_hash"] = hash_password(campos["password"])
    if not sets:
        return
    with conexion() as c:
        n = c.execute(f"UPDATE clientes SET {', '.join(k + ' = ?' for k in sets)} WHERE email = ?",
                      (*sets.values(), email.strip().lower())).rowcount
        if not n:
            raise KeyError(email)
        if campos.get("activo") == 0 or "pass_hash" in sets:   # cierra sus sesiones abiertas
            c.execute("DELETE FROM sesiones WHERE cliente_id = (SELECT id FROM clientes WHERE email = ?)",
                      (email.strip().lower(),))


def listar_clientes():
    mes = mes_actual()
    with conexion() as c:
        return c.execute("""SELECT cl.email, cl.empresa, cl.limite_mes, cl.activo, COALESCE(u.documentos, 0) AS usados
                            FROM clientes cl LEFT JOIN uso u ON u.cliente_id = cl.id AND u.mes = ?
                            ORDER BY cl.empresa""", (mes,)).fetchall()


# ---------- sesiones ----------
def _th(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def crear_sesion(cliente_id: int) -> str:
    token = secrets.token_urlsafe(32)
    with conexion() as c:
        c.execute("DELETE FROM sesiones WHERE expira < ?", (time.time(),))
        c.execute("INSERT INTO sesiones VALUES (?,?,?)", (_th(token), cliente_id, time.time() + SESION_DIAS * 86400))
    return token


def cliente_de_sesion(token: str | None):
    if not token:
        return None
    with conexion() as c:
        return c.execute("""SELECT cl.* FROM sesiones s JOIN clientes cl ON cl.id = s.cliente_id
                            WHERE s.token_hash = ? AND s.expira > ? AND cl.activo = 1""",
                         (_th(token), time.time())).fetchone()


def cerrar_sesion(token: str | None):
    if token:
        with conexion() as c:
            c.execute("DELETE FROM sesiones WHERE token_hash = ?", (_th(token),))


# ---------- uso mensual ----------
def mes_actual() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def usados(cliente_id: int) -> int:
    with conexion() as c:
        r = c.execute("SELECT documentos FROM uso WHERE cliente_id = ? AND mes = ?", (cliente_id, mes_actual())).fetchone()
        return r["documentos"] if r else 0


def reservar_documento(cliente_id: int, limite: int) -> bool:
    """Suma 1 al uso del mes solo si no pasa del límite. Atómico."""
    mes = mes_actual()
    with conexion() as c:
        c.execute("INSERT OR IGNORE INTO uso (cliente_id, mes, documentos) VALUES (?,?,0)", (cliente_id, mes))
        return c.execute("UPDATE uso SET documentos = documentos + 1 WHERE cliente_id = ? AND mes = ? AND documentos < ?",
                         (cliente_id, mes, limite)).rowcount == 1


def devolver_documento(cliente_id: int):
    """Si la lectura falló, no se cobra."""
    with conexion() as c:
        c.execute("UPDATE uso SET documentos = MAX(documentos - 1, 0) WHERE cliente_id = ? AND mes = ?",
                  (cliente_id, mes_actual()))
