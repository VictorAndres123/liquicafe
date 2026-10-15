"""Motor de plantillas compartido por las vistas y por la página de error."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.presentation.formato import numero, pesos

plantillas = Jinja2Templates(directory=Path(__file__).parent / "templates")
plantillas.env.filters["pesos"] = pesos
plantillas.env.filters["numero"] = numero
