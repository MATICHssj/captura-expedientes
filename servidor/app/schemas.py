from typing import Literal, Optional
from pydantic import BaseModel, Field


class INE(BaseModel):
    nombre_completo: Optional[str] = Field(None, description="Nombre(s) y apellidos tal como en la credencial")
    fecha_nacimiento: Optional[str] = Field(None, description="YYYY-MM-DD")
    curp: Optional[str] = Field(None, description="CURP de 18 caracteres impresa en la INE")
    calle_numero: Optional[str] = Field(None, description="Calle y número exterior/interior; null si el domicilio no trae calle")
    colonia: Optional[str] = None
    cp: Optional[str] = None
    municipio_estado: Optional[str] = None
    vigencia: Optional[int] = Field(None, description="Año de vigencia impreso en la INE (ej. 2031)")


class Movimiento(BaseModel):
    fecha: Optional[str] = None
    descripcion: Optional[str] = None
    abono: float = 0


class EstadoCuenta(BaseModel):
    banco: Optional[str] = None
    titular: Optional[str] = None
    periodo_inicio: Optional[str] = Field(None, description="YYYY-MM-DD")
    periodo_fin: Optional[str] = Field(None, description="YYYY-MM-DD")
    total_depositos_abonos: Optional[float] = Field(
        None, description="Total de depósitos/abonos del periodo según el RESUMEN del estado de cuenta, en pesos")
    suma_abonos_movimientos: Optional[float] = Field(
        None, description="Suma de los abonos que tú viste en la tabla de movimientos (para cuadrar)")
    cuenta_terminacion: Optional[str] = Field(None, description="Últimos 4 dígitos del número de cuenta o CLABE")
    saldo_inicial: Optional[float] = Field(None, description="Saldo anterior / inicial del periodo, del RESUMEN")
    total_retiros_cargos: Optional[float] = Field(None, description="Total de retiros/cargos del periodo, del RESUMEN")
    saldo_final: Optional[float] = Field(None, description="Saldo final / al corte del periodo, del RESUMEN")
    evidencia_total: Optional[str] = Field(
        None, description="Copia LITERAL del renglón del resumen donde leíste el total de depósitos/abonos")


class Solicitud(BaseModel):
    nombre_completo: Optional[str] = None
    correo: Optional[str] = None
    telefono_celular: Optional[str] = Field(None, description="10 dígitos")
    calle_numero: Optional[str] = None
    colonia: Optional[str] = None
    cp: Optional[str] = None
    municipio_estado: Optional[str] = None
    fecha_nacimiento: Optional[str] = Field(None, description="YYYY-MM-DD, si la solicitud la trae")
    curp: Optional[str] = Field(None, description="Tal cual viene en la solicitud")
    rfc: Optional[str] = Field(None, description="Tal cual viene en la solicitud")


class Cotizacion(BaseModel):
    marca: Optional[str] = None
    modelo: Optional[str] = Field(None, description="Modelo y versión")
    anio: Optional[int] = None
    precio: Optional[float] = Field(None, description="Precio del auto en pesos")
    cliente_nombre: Optional[str] = Field(None, description="Nombre del cliente si aparece en la cotización")


class ComprobanteDomicilio(BaseModel):
    emisor: Optional[str] = Field(None, description="CFE, agua, Telmex, Izzi, predial, etc.")
    titular: Optional[str] = None
    calle_numero: Optional[str] = None
    colonia: Optional[str] = None
    cp: Optional[str] = None
    municipio_estado: Optional[str] = None
    fecha_emision: Optional[str] = Field(None, description="YYYY-MM-DD")


class DocExtraction(BaseModel):
    tipo: Literal["ine", "estado_cuenta", "solicitud", "cotizacion", "comprobante_domicilio", "otro"]
    descripcion: Optional[str] = Field(None, description="Frase corta de qué documento es")
    legible: bool = Field(True, description="False si es imposible leer lo importante")
    ine: Optional[INE] = None
    estado_cuenta: Optional[EstadoCuenta] = None
    solicitud: Optional[Solicitud] = None
    cotizacion: Optional[Cotizacion] = None
    comprobante_domicilio: Optional[ComprobanteDomicilio] = None
    dudas: list[str] = Field(
        default_factory=list,
        description="Campos que leíste con poca certeza (letra difícil, borroso) y por qué")


class Lectura(BaseModel):
    """Un archivo puede traer varios documentos (ej. un PDF con 3 estados de cuenta)."""
    documentos: list[DocExtraction]
