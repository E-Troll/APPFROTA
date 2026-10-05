# Controle de Quilometragem Veicular (App Veículo)

Aplicação Flask para registrar viagens de veículos, controlar saídas, paradas e chegadas com fotos do odômetro, consultar histórico e exportar relatórios em PDF, Excel e CSV.

## Executar localmente

Requer Python 3.8 ou superior. Na raiz do repositório:

```bash
bash run.sh
```

Ou instale manualmente:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

A aplicação local fica em <http://localhost:5050>. O banco e as fotos locais são mantidos na pasta do projeto.

## Deploy na Vercel

O `vercel.json` encaminha as rotas para a aplicação Flask em `api/index.py`. Os assets web ficam em `public/static/` para entrega estática pela Vercel. A função usa `/tmp` para permitir que o SQLite e os uploads funcionem em tempo de execução.

**Importante:** o disco da Vercel é temporário e compartilhado apenas dentro da instância da função. O banco e as fotos podem desaparecer ou não estar disponíveis entre invocações. Para uso real em produção, configure um banco persistente e armazenamento de objetos (por exemplo, Postgres e Vercel Blob) antes de registrar dados importantes.

## Testes

```bash
python -m unittest discover -s tests -v
```

## Funcionalidades

- Registro de viagens, paradas e encerramentos com validação de quilometragem.
- Captura e carimbo de fotos do odômetro.
- Histórico com filtros por mês, status, placa, condutor e finalidade.
- Indicadores e exportação de relatórios em PDF, Excel e CSV.
