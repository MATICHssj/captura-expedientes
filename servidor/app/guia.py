"""Guía para reconocer documentos. La usan todas las versiones (servidor y páginas web)."""

COMO_RECONOCER = """Cómo reconocer cada tipo:
- "ine": credencial para votar del INE (o la antigua del IFE). Dice "INSTITUTO NACIONAL ELECTORAL" o "INSTITUTO FEDERAL ELECTORAL" y "CREDENCIAL PARA VOTAR"; trae foto, NOMBRE, DOMICILIO, CLAVE DE ELECTOR, CURP, FECHA DE NACIMIENTO y VIGENCIA. El REVERSO (código QR o de barras, huella, firma, renglones que empiezan con "IDMEX") también es "ine" aunque no traiga nombre. En la credencial el nombre viene en renglones: apellido paterno, apellido materno y nombre(s); escríbelo como "NOMBRE(S) APELLIDO_PATERNO APELLIDO_MATERNO". Un pasaporte o una licencia de manejo NO es "ine": es "otro".
- "solicitud": formato de solicitud de crédito automotriz de una financiera, banco o agencia (NR Finance, Crédito Nissan, GM Financial, Toyota Financial, VW Financial, Ford Credit, Santander, BBVA, Banorte, Scotiabank, cajas, etc.) con datos personales, domicilio, empleo e ingresos, referencias; muchas veces llenada a mano.
- "cotizacion": cotización o corrida financiera de un auto: marca, modelo/versión, año modelo, precio, enganche, plazo, mensualidad.
- "estado_cuenta": estado de cuenta BANCARIO (BBVA, Santander, Banorte, Banamex, HSBC, Scotiabank, Inbursa, Azteca, BanCoppel, Nu, Hey Banco, Mercado Pago, etc.) con periodo, saldos y movimientos.
- "comprobante_domicilio": recibo de luz (CFE), agua, teléfono/internet/cable (Telmex, Izzi, Totalplay, Megacable, AT&T, Telcel), gas, predial o constancia de domicilio. Lo importante: titular, domicilio y fecha de emisión (si no hay, la fecha límite de pago o del periodo facturado).
- "otro": cualquier otra cosa (recibo de nómina, pasaporte, licencia, carta, captura de pantalla…).
En TODOS los documentos llena "descripcion" con una frase corta de qué es (ej. "INE frente", "INE reverso", "Recibo CFE bimestral", "Estado de cuenta BBVA octubre 2026").
Si un documento trae el nombre de una persona, NO lo dejes en null: en la INE y la solicitud va en nombre_completo, en el estado de cuenta y el comprobante en titular, y en la cotización en cliente_nombre."""

BUSQUEDA_MINUCIOSA = """Método de trabajo (sé minucioso, no te quedes con la primera lectura):
1. Recorre el documento COMPLETO: todas las páginas e imágenes, de arriba a abajo, incluidos encabezados, pies de página, márgenes, recuadros, sellos, letra pequeña y el reverso.
2. Para cada campo del tipo de documento, busca TODAS sus etiquetas posibles (cada banco y cada formato lo llama distinto):
   - Saldo inicial: "Saldo anterior", "Saldo inicial", "Saldo al inicio del periodo", "Saldo del periodo anterior".
   - Abonos: "Depósitos", "Abonos", "Total de abonos", "Créditos", "Depósitos / Abonos (+)", "Entradas".
   - Cargos: "Retiros", "Cargos", "Total de cargos", "Débitos", "Retiros / Cargos (-)", "Salidas".
   - Saldo final: "Saldo final", "Saldo al corte", "Saldo actual", "Saldo a la fecha de corte", "Saldo nuevo".
   - Periodo: "Periodo", "Fecha de corte", "Del ... al ...", "Periodo del ... al ...".
   - Cuenta: "No. de cuenta", "Cuenta", "CLABE", "Número de tarjeta" (solo los últimos 4 dígitos).
   - Correo: "Correo electrónico", "E-mail", "Email", "Correo".
   - Celular: "Celular", "Tel. celular", "Teléfono móvil", "Cel.", "Móvil", "WhatsApp" (no confundir con teléfono de casa, de oficina ni de referencias).
   - Domicilio: "Domicilio", "Dirección", "Calle", "No. ext.", "No. int.", "Colonia", "C.P.", "Código postal", "Municipio", "Alcaldía", "Estado".
   - Fecha del comprobante: "Fecha de emisión", "Fecha de expedición", "Fecha límite de pago", "Periodo facturado", "Mes de facturación".
   - Precio del auto: "Precio", "Precio de lista", "Precio total", "Valor factura", "Precio unitario" (no confundir con enganche ni mensualidad).
3. En la solicitud, distingue los datos del SOLICITANTE de los del cónyuge, aval, referencias o empresa: toma solo los del solicitante.
4. Si el documento trae varias tablas o resúmenes, usa el RESUMEN del periodo para los totales.
5. Antes de responder, revisa cada campo que dejaste en null y vuelve a buscarlo una vez más en todo el documento. Solo déjalo en null si de verdad no aparece."""

# Datos clave que, si faltan tras la primera lectura, disparan una búsqueda enfocada
CLAVE = {
    "ine": ["nombre_completo", "fecha_nacimiento", "curp", "colonia", "cp"],
    "solicitud": ["nombre_completo", "correo", "telefono_celular", "calle_numero", "cp"],
    "cotizacion": ["modelo", "anio", "precio"],
    "estado_cuenta": ["banco", "titular", "periodo_fin", "saldo_inicial", "total_depositos_abonos", "total_retiros_cargos", "saldo_final"],
    "comprobante_domicilio": ["titular", "calle_numero", "cp", "fecha_emision"],
}

LETRA_A_MANO = """Formularios llenados a mano (solicitudes):
- Separa la ETIQUETA impresa del VALOR escrito: el valor va a la derecha, debajo o sobre la línea o recuadro de su etiqueta. Nunca copies la etiqueta como valor ni tomes el valor del renglón de al lado.
- Si el formato trae un recuadro por letra o número (cuadritos), lee un carácter por recuadro y júntalos.
- Si algo está tachado o sobrescrito, usa lo que quedó al final, no lo tachado; si no se sabe cuál vale, ponlo en "dudas".
- Mucha gente escribe en LETRA DE MOLDE mayúscula: el correo devuélvelo en minúsculas; los nombres, como vienen.
- Celular: 10 dígitos. Quita espacios, guiones, paréntesis, "+52", "044" o "045". Toma el que diga celular, móvil o WhatsApp, no el de casa, oficina o referencias. Las ladas sirven para revisar (55 y 56 CDMX y zona metropolitana, 33 Guadalajara, 81 Monterrey), nunca para inventar dígitos.
- Correo: respeta puntos, guiones, guion bajo y números. Una "@" mal hecha puede parecer una "a" encerrada, "(a)" o "Q". Si el usuario lleva un año o día (ej. lupita88) y hay fecha de nacimiento, úsala solo para desempatar un dígito dudoso y anótalo en "dudas".
- Domicilio: abreviaturas comunes Av., C., Calz., Priv., Cda., And., Mz./Manz. (manzana), Lt. (lote), Edif., Depto., Int., Ext., S/N (sin número), Col., Fracc., U.H. Copia el domicilio como viene; no completes ni corrijas calles ni colonias.
- CURP: 18 caracteres = 4 letras + 6 dígitos (AAMMDD de nacimiento) + H o M + 2 letras del estado + 3 consonantes + 1 letra o dígito + 1 dígito. Usa esa estructura para decidir si un carácter dudoso es letra o número (en las posiciones 5 a 10 solo hay dígitos: O→0, I→1, S→5, B→8).
- Números a mano: el 1 con "gancho" parece 7 sin raya; muchos cruzan el 7; un 4 cerrado parece 9; el 0 puede llevar diagonal; un 5 apurado parece S y un 2 parece Z.

Montos y fechas:
- En México los montos usan coma de miles y punto decimal (31,250.40). Un "-", "CR" o "DB" junto al número indica signo o tipo; los totales del resumen van sin signo.
- Fechas como "14/07/1988", "14-JUL-88" o "14 de julio de 1988" → 1988-07-14. Meses: ENE FEB MAR ABR MAY JUN JUL AGO SEP OCT NOV DIC.
- Si recibes texto exacto extraído del archivo, úsalo para números y nombres (es exacto) y las imágenes para entender el formato.
- Si unas páginas solo continúan un documento que empieza en otra parte del archivo (ej. hojas de movimientos sin el resumen), devuélvelas con descripcion "Continuación de …" y solo los datos que se vean."""
