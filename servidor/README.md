# Captura de Expedientes

Tus clientes (agencias / analistas de crédito automotriz) entran con usuario y contraseña, suben INE, solicitud,
cotización y estados de cuenta, y obtienen la ficha del cliente con el promedio de abonos de los últimos 3 meses.
La IA corre con **tu** clave de API (cuenta de empresa en console.anthropic.com); tus clientes no necesitan Claude.

## Qué hay aquí
| Archivo | Qué hace |
|---|---|
| `app/web.py` | Servidor web: login, límite mensual por cliente, endpoint `/api/leer` |
| `app/db.py` | Clientes, sesiones y conteo de uso (SQLite) |
| `app/admin.py` | Dar de alta clientes, cambiar límites, desactivar |
| `app/extractor.py` | Lectura con Claude: doble lectura cuando hay dudas, varios documentos por archivo |
| `app/preprocess.py`, `app/orientacion.py` | Arreglo de fotos: recorte, perspectiva, orientación, inclinación, sombras |
| `app/validators.py` | Validaciones: CURP ↔ fecha, correo, celular, CP, rangos |
| `web/app.html` | La pantalla que usan tus clientes |
| `web/privacidad.html` | **Plantilla** de aviso de privacidad (complétala con un abogado) |
| `app/main.py` | (Opcional) bot de WhatsApp |

## Probar en tu computadora
```
pip install -r requirements.txt
pytest
export ANTHROPIC_API_KEY=sk-ant-...   COOKIE_SECURE=0
python -m app.admin crear --email tu@correo.mx --empresa "Prueba" --limite 50
uvicorn app.web:app --port 8000
```
Abre http://localhost:8000

## Ponerlo en internet (Railway, ~5 USD/mes)
1. Sube esta carpeta a un repositorio de GitHub (privado).
2. En railway.app: *New project → Deploy from GitHub* y elige el repo (usa el `Dockerfile`).
3. **Agrega un Volume montado en `/data`**: ahí vive la base de clientes. Sin volumen se borra en cada actualización.
4. Variables: `ANTHROPIC_API_KEY` (tu clave de empresa). Opcional: `MODEL=claude-sonnet-5-5` para gastar menos.
5. Railway te da un dominio `https://...`; conecta tu propio dominio si quieres.
6. Crea clientes desde la consola de Railway: `python -m app.admin crear --email ... --empresa ... --limite 300`

## Administrar clientes
```
python -m app.admin listar                                   # uso del mes de cada cliente
python -m app.admin crear --email a@b.mx --empresa "X" --limite 300
python -m app.admin limite --email a@b.mx --limite 500        # cambió de plan
python -m app.admin password --email a@b.mx                   # olvidó su contraseña
python -m app.admin desactivar --email a@b.mx                 # no pagó (cierra su sesión al instante)
```
Cobro: al inicio, cobra por transferencia y factura; cuando tengas varios clientes, conecta Stripe o Mercado Pago.

## Privacidad y seguridad
- Los archivos **no se guardan**: se leen en memoria y se descartan. Solo se guarda el conteo de documentos.
- Contraseñas con scrypt; sesiones de 7 días en cookie `HttpOnly`/`Secure`; bloqueo tras 5 intentos fallidos.
- Se revisa el contenido real del archivo (no solo la extensión); máximo 20 MB.
- Si una lectura falla, no se descuenta del límite del cliente.

## Costos aproximados (verifícalos con tus primeros expedientes)
- IA: ~0.05–0.15 USD por documento con el modelo más preciso; menos con `MODEL=claude-sonnet-5-5`.
- Servidor: ~5 USD/mes. Dominio: ~15 USD/año.
