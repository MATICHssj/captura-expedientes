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
