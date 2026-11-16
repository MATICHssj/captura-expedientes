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

## Cómo usarla

1. Abre la página: **https://matichssj.github.io/captura-expedientes/**
   (o descarga `index.html` y ábrelo con doble clic en Chrome).
2. La primera vez te pide una **clave de API de Anthropic**:
   - Entra a **console.anthropic.com**, crea una cuenta y agrega saldo (con 5–10 USD alcanza para empezar).
   - En **API Keys** crea una clave (empieza con `sk-ant-`), pégala y toca **Guardar**.
3. Arrastra los documentos del cliente. Se leen solos.

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
