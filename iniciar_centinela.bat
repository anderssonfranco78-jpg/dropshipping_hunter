@echo off
rem Inicia el Centinela local del Dropshipping Hunter (panel + boton "Actualizar ahora").
rem Doble clic para abrir. Cierra esta ventana para detenerlo.
rem Usa el Python del sistema (necesita: pip install -r requirements.txt).
cd /d "%~dp0"
python centinela_local.py
pause
