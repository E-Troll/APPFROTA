# Controle de Quilometragem Veicular (App Veículo)

Aplicação web Flask para registrar viagens de veículos, controlar saídas, paradas e chegadas com fotos do odômetro, consultar histórico e exportar relatórios em PDF, Excel e CSV.

## Estrutura

```text
app.py
 database.py
 requirements.txt
 run.sh
 services/       # processamento de imagens e exportação de relatórios
 static/         # CSS e JavaScript
 templates/      # interface web
 tests/          # testes automatizados
 uploads/        # fotos geradas durante o uso (não versionadas)
```

## Requisitos

- Python 3.8 ou superior.

## Executar

Na raiz do repositório, execute:

```bash
bash run.sh
```

O script cria o ambiente virtual, instala as dependências e inicia o servidor. Para instalação manual:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

A aplicação fica disponível em <http://localhost:5050>. O banco SQLite (`odometro.db`) é criado automaticamente ao iniciar; o banco e as fotos de uso ficam locais e não são incluídos no Git.

## Testes

Com as dependências instaladas no ambiente virtual:

```bash
python -m unittest discover -s tests -v
```

## Funcionalidades

- Registro de viagens, paradas e encerramentos com validação de quilometragem.
- Captura e carimbo de fotos do odômetro.
- Histórico com filtros por mês, status, placa, condutor e finalidade.
- Indicadores e exportação de relatórios em PDF, Excel e CSV.