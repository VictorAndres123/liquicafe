"""LiquiCafé: liquidación de compras de café pergamino seco.

El paquete está organizado en tres capas lógicas cerradas, de arriba hacia abajo:

* ``app.presentation``: HTTP, vistas HTML y API JSON.
* ``app.business``: casos de uso (servicios) y modelo de dominio.
* ``app.persistence``: SQLite, unidad de trabajo y repositorios.

``app.main`` es la raíz de composición: el único módulo que conoce las tres.
"""
