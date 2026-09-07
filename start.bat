@echo off
REM ==================================================================
REM  ProLegends - arranque para Windows.
REM  Doble clic en este fichero y listo: crea el entorno, instala lo
REM  que haga falta, importa los exports nuevos, arranca el servidor
REM  y abre el navegador.
REM ==================================================================
setlocal
cd /d "%~dp0"
title ProLegends - explorador de leyendas de Dwarf Fortress

echo.
echo  ================================================================
echo    ProLegends
echo    Explorador del archivo de leyendas de Dwarf Fortress
echo  ================================================================
echo.

REM --- 1. Localizar Python ------------------------------------------
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo  [ERROR] No se ha encontrado Python en este ordenador.
  echo.
  echo  Instalalo desde https://www.python.org/downloads/
  echo  IMPORTANTE: en el instalador marca la casilla
  echo  "Add python.exe to PATH" antes de darle a Install.
  echo.
  pause
  exit /b 1
)

REM --- 2. Entorno virtual -------------------------------------------
if not exist "venv\Scripts\python.exe" (
  echo  Creando el entorno de Python ^(solo la primera vez^)...
  %PY% -m venv venv
  if errorlevel 1 (
    echo  [ERROR] No se ha podido crear el entorno virtual de Python.
    pause
    exit /b 1
  )
)
set "VPY=%~dp0venv\Scripts\python.exe"

REM --- 3. Dependencias ----------------------------------------------
echo  Comprobando dependencias...
"%VPY%" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%VPY%" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
  echo  [ERROR] No se han podido instalar las dependencias.
  echo  Comprueba que tienes conexion a internet y vuelve a intentarlo.
  pause
  exit /b 1
)

REM --- 4. Fichero de configuracion -----------------------------------
if not exist ".env" if exist ".env.example" (
  copy ".env.example" ".env" >nul
  echo  Creado el fichero .env. Si quieres cronicas narradas, abrelo con
  echo  el Bloc de notas y pon ahi tu clave de Anthropic.
)
if not exist "data\imports" mkdir "data\imports"

REM --- 5. Importar lo que haya nuevo ---------------------------------
echo.
echo  Buscando exports en data\imports ...
"%VPY%" -m app.cli importar

REM --- 6. Servidor y navegador ---------------------------------------
echo.
"%VPY%" -m app.cli servidor --abrir

echo.
echo  El servidor se ha cerrado.
pause
