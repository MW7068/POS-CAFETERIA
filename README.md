# Mama Oli | Estructura Inicial

Esta etapa crea exactamente el esquema de la consigna. Los archivos de las
celulas son placeholders, no contienen una aplicacion terminada.

```powershell
python -B -m src.main
python -B -m unittest discover -s tests -v
```

La prueba disponible valida existencia de archivos, NO reglas del POS. No
presentar este resultado como pruebas de dominio, servicios o persistencia.

## Responsabilidades

| Integrante | Rutas exclusivas |
| --- | --- |
| 1 GitMaster | .github/, src/__init__.py, src/main.py, tests/, docs, .gitignore |
| 2 Dominio | src/domain/ |
| 3 Servicios | src/services/__init__.py y app_service.py |
| 4 Datos | src/services/data_manager.py |
| 5 Interfaz | src/ui/ |

Acordar los contratos incluidos fuera de CSW en el paquete. Los datos seran
JSON local y usuarios demostrativos; GUI Tkinter conserva cli_interface.py.
Cada responsable aporta exclusivamente sus rutas a traves de su rama y PR.
El GitMaster consolida README, architecture, pruebas y main SOLO al integrar.
El reparto de cinco debe confirmarse porque el PDF original menciona siete.

La plantilla PR requiere prompt real de IA, prueba local y revision. Los
prompts simulados propuestos fuera de CSW no son evidencia efectiva.
