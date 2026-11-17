<p align="center"><img src="marca/logo.svg" width="96" alt="Logo de Captura de Expedientes"></p>

# Captura de Expedientes

Herramienta para analistas de crédito automotriz en México. Subes la **INE, la solicitud, la cotización, el
comprobante de domicilio y los estados de cuenta** (fotos o PDF) y te arma la ficha del cliente:

- Nombre completo, fecha de nacimiento, dirección (si la INE no trae calle, la toma de la solicitud), correo y celular
- **Promedio de depósitos/abonos de los últimos 3 estados de cuenta**
- Modelo, año y precio del auto de la cotización
- Comprobante de domicilio: que tenga menos de 3 meses, que el CP coincida y a nombre de quién está

Busca cada dato minuciosamente (con los distintos nombres que usa cada banco y formato, y una segunda búsqueda
si algo falta), lee letra difícil, endereza fotos de lado o chuecas, y **verifica** los datos: que los saldos cuadren, que los meses
sean seguidos, que la CURP corresponda al nombre y la fecha, que la INE esté vigente, avisa de estados de cuenta en $0, etc.

### Qué archivos acepta

- **Fotos**: JPG, PNG, WebP, HEIC de iPhone, JFIF de WhatsApp, TIFF de escáner (varias páginas), aunque no traigan extensión.
  Recorta la mesa o el fondo, corrige la perspectiva de fotos tomadas en ángulo, la endereza y la gira si está de lado.
  Las fotos borrosas o chicas **no se rechazan**: se leen con más cuidado y se marcan para revisar.
- **PDF**: digitales (lee el texto exacto), escaneados, mixtos, formularios llenados en la computadora (lee los campos)
  y **con contraseña** (te la pide en la misma fila; los bancos suelen usar el RFC o la fecha de nacimiento).
  Los PDF largos (expedientes de 20 a 60 páginas) se leen por partes y se juntan.
- **Word (.docx) y Excel (.xlsx)**: lee el texto, las tablas y las fotos pegadas adentro (por ejemplo, una INE escaneada en un Word).
- **ZIP**: lo abre y lee cada archivo de adentro.

### Cómo verifica lo que lee

- **CURP**: revisa el dígito verificador oficial; si una letra y un número se confundieron (O/0, I/1, S/5, B/8) lo corrige por la posición.
- **Código postal contra estado**: avisa si el CP no es del estado que dice el domicilio (ej. CP de Jalisco con domicilio en CDMX).
- **Correo y celular**: corrige dominios mal escritos (gmial, hotmial, .con), quita +52/044 y avisa si el celular empieza con 0 o 1.
- **Doble lectura**: si algo no cuadra o falta, lo vuelve a leer con la hoja ampliada en cuadrantes; si las dos lecturas
  no coinciden, se queda con la que pasa la verificación y te lo indica.

## Cómo usarla

1. Abre la página: **https://matichssj.github.io/captura-expedientes/**
   (o descarga `index.html` y ábrelo con doble clic en Chrome).
2. La primera vez te pide una **clave de API de Anthropic**:
   - Entra a **console.anthropic.com**, crea una cuenta y agrega saldo (con 5–10 USD alcanza para empezar).
   - En **API Keys** crea una clave (empieza con `sk-ant-`), pégala y toca **Guardar**.
3. Arrastra los documentos del cliente. Se leen solos, uno por uno. Si la API está saturada o tu cuenta llega a su
   límite por minuto, la página espera y reintenta sola.

La clave se guarda **solo en tu navegador** y solo se envía a Anthropic. No uses la página con tu clave en
computadoras compartidas (hay un botón para borrarla).

## Cuánto cuesta

Solo pagas lo que lees en tu cuenta de API: aproximadamente **0.05 a 0.15 USD por documento** con el modelo más
preciso (Opus), más o menos la mitad con Sonnet. La página muestra el gasto de cada sesión.

## Privacidad

Los documentos no se guardan en ningún lado: se procesan en tu navegador y se envían a la API de Anthropic solo
para leerlos. Revisa siempre los datos marcados en amarillo antes de usarlos en una solicitud.

## Versión con servidor (opcional)

La carpeta [`servidor/`](servidor/) tiene una versión con usuarios y contraseñas, límite mensual por usuario y la
clave de API del lado del servidor (para que varias personas la usen sin tener su propia clave). Ver
[`servidor/README.md`](servidor/README.md).
