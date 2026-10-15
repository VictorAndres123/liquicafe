# Registro de decisiones de arquitectura

Formato corto: contexto, decisión, alternativas y consecuencias.

## D-01. Patrón en capas cerradas

- **Contexto:** los atributos más importantes son la testabilidad y la
  modificabilidad de la regla de liquidación. Las restricciones son un solo
  desarrollador, presupuesto cero y un solo PC.
- **Decisión:** tres capas lógicas cerradas (presentación, negocio y
  persistencia) en un monolito.
- **Alternativas:**
  - MVC como estilo dominante: no dice dónde vive la regla de dinero;
  - Pipes and Filters: el problema es interactivo y con estado compartido;
  - microservicios: el costo operativo no tiene sentido para un equipo de una
    persona.
- **Consecuencias:** es simple y barato de operar. A cambio es un despliegue
  monolítico, con escalabilidad limitada y algunos *sinkholes* en las
  consultas.

## D-02. La persistencia no conoce el dominio

- **Contexto:** si los repositorios devolvieran `Liquidacion`, la capa de
  persistencia tendría que importar `app.business` y la dependencia apuntaría
  hacia arriba.
- **Decisión:** los repositorios devuelven `dict`, y `app.business.mapeo`
  convierte en ambos sentidos.
- **Alternativa:** arquitectura hexagonal, con puertos definidos en el negocio
  y adaptadores en la persistencia. Invierte la dependencia, pero ya no es el
  patrón clásico en capas.
- **Consecuencias:** hay más código de mapeo, pero la regla se puede verificar
  con import-linter.

## D-03. Reglas de dinero como cadena de ajustes

- **Contexto:** las bonificaciones y los descuentos cambian por decisión de la
  asamblea.
- **Decisión:** la interfaz `Ajuste` y una lista ordenada que el `Liquidador`
  aplica sobre un subtotal. Es la idea de Pipes and Filters, a escala de
  clases.
- **Consecuencias:** una regla nueva es una clase nueva. El orden importa: la
  cuota va de última.

## D-04. Tolerancia de 1 peso por kilo frente a la tabla de la FNC

- **Contexto:** la primera versión de la prueba exigía igualdad exacta y
  fallaron 4 de 13 FR por un peso. Busqué un precio del excelso que
  reprodujera las 13 filas, redondeando y truncando, y no existe.
- **Decisión:** aceptar una tolerancia de 1 peso por kilo ($125 por carga,
  menos del 0,006 %).
- **Consecuencias:** el oráculo sigue siendo el dato oficial, y la tolerancia
  queda documentada en la prueba.

## D-05. Contrato de capas cerradas con `allow_indirect_imports`

- **Contexto:** el contrato `forbidden` de import-linter revisa por defecto
  también las importaciones indirectas. Por eso marcó como violación el camino
  legítimo presentación → negocio → persistencia.
- **Decisión:** prohibir solo el salto directo.
- **Consecuencias:** el contrato expresa exactamente la regla de las capas
  cerradas.

## D-06. SQLite en modo WAL con triggers de inmutabilidad

- **Contexto:** no hay presupuesto ni administrador de base de datos, se
  puede ir la luz y las liquidaciones son soportes contables.
- **Decisión:**
  - SQLite;
  - transacciones explícitas (`BEGIN IMMEDIATE`);
  - kilos y FR guardados como `TEXT` para que `REAL` no meta errores de punto
    flotante;
  - triggers que impiden `DELETE` y cambios en los valores.
- **Consecuencias:** para varias bodegas habrá que migrar a PostgreSQL. La
  capa de persistencia es la única que cambia.
