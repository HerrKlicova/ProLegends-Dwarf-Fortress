#!/bin/bash
# Arranque para macOS. En macOS un fichero .command SI se abre con doble clic
# (uno .sh no), asi que este es el que hay que usar en el Finder.
#
# La primera vez macOS puede decir que no puede abrirlo por venir de internet:
# pulsa este fichero con el boton derecho, elige "Abrir" y confirma. Solo pasa
# una vez.
cd "$(dirname "$0")" || exit 1
exec bash start.sh
