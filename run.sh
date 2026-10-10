#!/usr/bin/env bash
# Quickstart script for Controle de Quilometragem Veicular

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================================="
echo "  Iniciando Controle de Quilometragem Veicular"
echo "=========================================================="

# Create venv if not present
if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual Python (venv)..."
    python3 -m venv venv
    echo "Instalando dependências..."
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
fi

echo "Iniciando servidor local..."
echo "Acesse a aplicação em: http://localhost:5050"
echo "Pressione Ctrl+C para encerrar o servidor."
echo "=========================================================="

./venv/bin/python3 app.py
