@echo off
rem Abre el panel del Dropshipping Hunter y enciende el motor en segundo plano (sin ventana negra).
rem Si el motor ya estaba encendido, solo abre el panel. Lo mismo hace el icono "Dropshipping Hunter" del escritorio.
rem El motor tambien arranca solo con Windows (acceso directo en la carpeta Inicio).
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw "%~dp0centinela_local.py") || (start "" python "%~dp0centinela_local.py")
