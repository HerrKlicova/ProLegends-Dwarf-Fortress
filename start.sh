#!/usr/bin/env bash
# Arranque para Linux y macOS. El equivalente de start.bat.
set -e
cd "$(dirname "$0")"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

echo
echo " ================================================================"
echo "   ProLegends"
echo "   Explorador del archivo de leyendas de Dwarf Fortress"
echo " ================================================================"
echo

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo " [ERROR] No se ha encontrado Python 3. Instalalo y vuelve a intentarlo."
  exit 1
fi

if [ ! -x "venv/bin/python" ]; then
  echo " Creando el entorno de Python (solo la primera vez)..."
  "$PY" -m venv venv
fi
VPY="venv/bin/python"

echo " Comprobando dependencias..."
"$VPY" -m pip install --upgrade pip --quiet --disable-pip-version-check
"$VPY" -m pip install -r requirements.txt --quiet --disable-pip-version-check

if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
fi

echo
echo " Ordenando los exports por mundo y fecha ..."
"$VPY" -m app.cli ordenar --aplicar

echo
echo " Buscando exports nuevos ..."
"$VPY" -m app.cli importar

echo
exec "$VPY" -m app.cli servidor --abrir
