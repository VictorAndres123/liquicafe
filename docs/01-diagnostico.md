# Diagnóstico del problema

> Caso académico. La asociación es ficticia, pero los precios, la tabla de
> factor de rendimiento y las normas citadas son reales y verificables. Las
> cifras de operación son supuestos explícitos (tabla S).

## Contexto

El Huila produjo el 19,65 % del café de Colombia en 2025 y lleva 15 años como
primer productor del país. Pitalito es el municipio con más área sembrada del
departamento: 17.790 hectáreas (Portafolio, 2026).

Cada día la FNC publica el precio por carga de 125 kg de café pergamino seco
(CPS) con factor de rendimiento (FR) 94, más una tabla de precios para FR entre
88 y 100. El FR es la cantidad de CPS necesaria para obtener 70 kg de excelso.

Hoy, en la asociación, el recibidor liquida con calculadora y cuaderno, y la
información se pasa a Excel en la noche. Eso deja cuatro problemas:

- errores de transcripción;
- reclamos, porque el asociado no recibe un desglose;
- ningún historial confiable por productor;
- datos personales sin control de acceso.

**Hallazgo:** la regla intuitiva `precio × 94 / FR` paga 2,86 % de más con
FR 88 y 2,4 % de menos con FR 100. La FNC valora aparte la pasilla, así que el
modelo correcto es `kg_excelso(FR) × precio_excelso + kg_pasilla(FR) × precio_pasilla`.

## Supuestos

| ID | Supuesto |
|---|---|
| S-01 | Asociación con 320 asociados y una bodega en el casco urbano de Pitalito |
| S-02 | ≈ 768 t de CPS al año en ≈ 4.000 entregas. Promedio de 18 por día y picos de 70 en cosecha |
| S-03 | Compras por ≈ $13.600 millones al año (precio del 9 de abril de 2026) |
| S-04 | 3 de cada 100 liquidaciones se corrigen. El cálculo y la transcripción toman ≈ 4 min por entrega |
| S-05 | Personal: recibidor-catador, auxiliar, tesorera y gerente, sin formación en sistemas |
| S-06 | Un PC en la bodega (Windows, 8 GB), un portátil, un router Wi-Fi e internet intermitente |
| S-07 | Bonificación por programa especial de $50.000 por carga y cuota de sostenimiento del 1 % |
| S-08 | El pago se hace por fuera del sistema. No se guardan cuentas bancarias |
| S-09 | Un desarrollador durante 3 semanas. El mantenimiento queda a cargo de un técnico local |
| S-10 | El FR de la muestra se mide con un decimal. La pasilla se interpola entre los FR enteros de la tabla |

## Actores

| Actor | Tipo | Interacción |
|---|---|---|
| Caficultor asociado | Interesado y titular de los datos | Recibe el comprobante |
| Recibidor-catador | Primario | Recibo y liquidación |
| Tesorera | Primario | Pago y reporte diario |
| Gerente | Primario | Precio del día, asociados y anulaciones |
| Junta / revisor fiscal | Interesado | Reportes y auditoría |
| FNC | Sistema externo | Publica el precio (en el MVP se digita) |
| DIAN, SIC | Reguladores | Restricciones normativas |

## Requisitos funcionales

| ID | Requisito | Prioridad | MVP |
|---|---|---|---|
| RF-01 | Registrar asociados con autorización de datos | Must | Sí |
| RF-02 | Registrar el precio del día (FR 94 y pasilla) | Must | Sí |
| RF-03 | Registrar la entrega (kg, humedad, FR, taza) | Must | Sí |
| RF-04 | Liquidar con desglose | Must | Sí |
| RF-05 | Comprobante imprimible con cédula enmascarada | Must | Sí |
| RF-06 | Historial por asociado | Must | Sí |
| RF-07 | Rechazo con motivo en el lenguaje del oficio | Must | Sí |
| RF-08 | Anular sin borrar | Should | Sí |
| RF-09 | Reporte diario | Should | Sí |
| RF-10 | Marcar como pagada | Should | Sí |
| RF-11 | Autenticación y roles | Should | No (deuda declarada) |
| RF-12 | Precio de la FNC automático | Won't | No |
| RF-13 | Documento soporte DIAN (Res. 000167 de 2021) | Won't | No |
| RF-14 | Exportar los datos del titular | Could | No |

## Reglas de negocio

| ID | Regla | Dónde está en el código |
|---|---|---|
| RN-01 | 1 carga = 125 kg | `models.KG_POR_CARGA` |
| RN-02 | kg de excelso = 125 × 70 / FR | `TablaFactorRendimiento.kg_excelso_por_carga` |
| RN-03 | Precio por FR = excelso + pasilla | `TablaFactorRendimiento.precio_kg` |
| RN-04 | Humedad del 10 % al 12 % | `Liquidador.validar_recepcion` |
| RN-05 | FR de 88 a 100 | `Liquidador.validar_recepcion` |
| RN-06 | Descuentos por taza de la FNC | `DescuentoPorTaza` |
| RN-07 | Bonificación por programa especial | `BonificacionProgramaEspecial` |
| RN-08 | Cuota del 1 % sobre el subtotal | `CuotaSostenimiento` |
| RN-09 | Neto = suma de las líneas, redondeado al peso | `Liquidacion.neto`, `a_pesos` |
| RN-10 | Copia de los parámetros en cada liquidación | `Liquidador._copia_de_parametros` y trigger SQL |
| RN-11 | Se anula, no se borra (Ley 962 de 2005, art. 28) | `Liquidacion.anular` y trigger SQL |
| RN-12 | Sin autorización no hay registro (Ley 1581, art. 9) | `ServicioProductores.registrar` |

## Escenarios de calidad (Bass et al., 2021)

| ID | Atributo | Medida de respuesta | Evidencia |
|---|---|---|---|
| QA-01 | Testabilidad | 13 FR de la FNC con error ≤ $1/kg; suite < 10 s; cobertura del dominio ≥ 90 % | `tests/unit/test_tabla_fr.py`, cobertura del 97 % |
| QA-02 | Modificabilidad | Regla nueva sin tocar presentación ni persistencia | `test_agregar_una_regla_nueva_no_toca_otras_capas` |
| QA-03 | No repudio | 100 % de las liquidaciones reconstruibles, 0 borrados | `test_cambiar_parametros_no_altera_liquidaciones_viejas`, triggers |
| QA-04 | Confidencialidad | 0 cédulas completas en la salida | `Cedula.__str__`, pruebas de API y de vistas |
| QA-05 | Disponibilidad | Sin dependencia de internet; 0 liquidaciones a medias | `test_si_falla_la_auditoria_no_queda_liquidacion_a_medias` |
| QA-06 | Usabilidad | ≤ 5 campos, coma decimal, mensajes del oficio | `recibo.html`, `_decimal()` |
| QA-07 | Desplegabilidad | Instalación ≤ 30 min, 0 licencias | README |
| QA-08 | Desempeño | p95 < 300 ms en el PC de la bodega | Prioridad baja |

## Priorización (árbol de utilidad)

1. Testabilidad: importancia Alta, dificultad Media.
2. Modificabilidad: importancia Alta, dificultad Media.
3. No repudio: importancia Alta, dificultad Media.
4. Confidencialidad: importancia Alta, dificultad Baja.
5. Disponibilidad: importancia Alta, dificultad Baja.
6. Usabilidad: importancia Media, dificultad Baja.
7. Desplegabilidad: importancia Media, dificultad Baja.
8. Desempeño: importancia Baja, dificultad Baja.
9. Escalabilidad: importancia Baja. Se trata en la evolución futura.

## Restricciones

- **Técnicas:** un PC con Windows, red local, internet intermitente y
  navegador como cliente.
- **Económicas:** $0 en licencias y hosting.
- **Organizacionales:** un solo desarrollador, un técnico de mantenimiento
  básico y usuarios con poca experiencia digital.
- **Normativas:**
  - Ley 1581 de 2012 y Decreto 1377 de 2013;
  - Decreto 090 de 2018: el RNBD aplica solo a entidades con activos
    superiores a 100.000 UVT;
  - Ley 962 de 2005, art. 28: conservar los papeles 10 años;
  - Resolución DIAN 000167 de 2021: documento soporte.
