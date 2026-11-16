"""Administración de clientes desde la terminal.

  python -m app.admin crear  --email ana@agencia.mx --empresa "Agencia Norte" --limite 300
  python -m app.admin listar
  python -m app.admin limite --email ana@agencia.mx --limite 500
  python -m app.admin password --email ana@agencia.mx
  python -m app.admin desactivar --email ana@agencia.mx     (y 'activar')
"""
import argparse, getpass, sys
from . import db


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m app.admin")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("crear"); c.add_argument("--email", required=True); c.add_argument("--empresa", required=True)
    c.add_argument("--limite", type=int, default=100); c.add_argument("--password")
    sub.add_parser("listar")
    l = sub.add_parser("limite"); l.add_argument("--email", required=True); l.add_argument("--limite", type=int, required=True)
    pw = sub.add_parser("password"); pw.add_argument("--email", required=True); pw.add_argument("--password")
    for n in ("activar", "desactivar"):
        sub.add_parser(n).add_argument("--email", required=True)
    a = p.parse_args(argv)
    db.iniciar()
    try:
        if a.cmd == "crear":
            pwd = a.password or getpass.getpass("Contraseña para el cliente (mín. 8): ")
            db.crear_cliente(a.email, a.empresa, pwd, a.limite)
            print(f"Cliente creado: {a.email} ({a.empresa}), {a.limite} documentos/mes")
        elif a.cmd == "listar":
            for r in db.listar_clientes():
                print(f"{r['empresa']:<28} {r['email']:<32} {r['usados']:>5}/{r['limite_mes']:<5} {'activo' if r['activo'] else 'INACTIVO'}")
        elif a.cmd == "limite":
            db.actualizar_cliente(a.email, limite_mes=a.limite); print("Límite actualizado")
        elif a.cmd == "password":
            db.actualizar_cliente(a.email, password=a.password or getpass.getpass("Nueva contraseña: ")); print("Contraseña cambiada")
        else:
            db.actualizar_cliente(a.email, activo=1 if a.cmd == "activar" else 0); print(f"Cliente {a.cmd[:-1]}do")
    except (ValueError, KeyError) as e:
        print("Error:", e if not isinstance(e, KeyError) else f"no existe el cliente {e}", file=sys.stderr)
        return 1
    except Exception as e:
        if "UNIQUE" in str(e):
            print("Error: ya existe un cliente con ese correo", file=sys.stderr); return 1
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
