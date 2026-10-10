# Controle de Quilometragem Veicular (App Veículo)

Aplicação Flask para registrar viagens, paradas e chegadas com fotos do odômetro, consultar histórico e exportar relatórios em PDF, Excel e CSV.

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

A aplicação local fica em <http://localhost:5050>. Sem `DATABASE_URL` e sem variáveis Supabase, o app usa SQLite e arquivos locais para desenvolvimento.

## Deploy na Vercel com Supabase

O `vercel.json` encaminha as requisições para o Flask em `api/index.py` e agenda uma limpeza diária. Os assets são servidos de `public/static/`. Em produção, os registros ficam no PostgreSQL do Supabase e as fotos em um bucket Supabase Storage privado.

### Variáveis de ambiente

A integração Supabase da Vercel pode fornecer a URL do PostgreSQL como `POSTGRES_URL`; o app também reconhece `DATABASE_URL`, `SUPABASE_DB_URL`, `SUPABASE_DATABASE_URL`, `POSTGRES_URL_NON_POOLING` e `POSTGRES_PRISMA_URL`. A URL com Session Pooler é recomendada para funções serverless. Configure as variáveis de ambiente para Production, Preview e Development conforme necessário, e faça redeploy após alterações.

O Storage requer `SUPABASE_URL` e uma chave de servidor: `SUPABASE_SERVICE_ROLE_KEY` (ou `SUPABASE_SECRET_KEY` nas chaves novas). Crie no Supabase um bucket **privado** chamado `odometer-photos`. Não exponha essas chaves no frontend, nem as grave em arquivos versionados. A tela e as APIs de consulta não dependem de `CRON_SECRET`; para habilitar a limpeza automática, configure um `CRON_SECRET` forte, que a Vercel envia à rota de cron no cabeçalho de autorização.

O cron diário configurado em `vercel.json` apaga viagens e fotos após 45 dias; a exclusão pode ocorrer na execução diária seguinte. Se `CRON_SECRET` não estiver configurado, a aplicação continua disponível, mas a limpeza automática não poderá ser autenticada.

O processamento converte as imagens para JPEG, limita a maior dimensão a 1280 px e busca comprimi-las a no máximo 220 KiB preservando a leitura do odômetro. O plano gratuito Supabase informa 500 MB de banco e 1 GB de Storage; a capacidade real de fotos depende do tamanho comprimido e do espaço utilizado por outros dados. Consulte [os limites e preços atuais](https://supabase.com/pricing).

Cada viagem/parada guarda no banco o nome da foto e o horário do evento (`start_time`, `stop_time` ou `end_time`); o arquivo JPEG fica no bucket do Supabase em produção e na pasta `uploads/` localmente. O nome e a marca d'água usam o horário informado no formulário, inclusive quando ele vem no formato `datetime-local` sem segundos. Se o registro no banco falhar após o upload, o app tenta remover o arquivo que ficou sem vínculo.

## Testes

Com as dependências de `requirements.txt` instaladas:

```bash
python -m unittest discover -s tests -v
```

## Funcionalidades

- Registro de viagens, paradas e encerramentos com validação de quilometragem.
- Captura e carimbo de fotos do odômetro.
- Histórico com filtros por mês, status, placa, condutor e finalidade.
- Indicadores e exportação de relatórios em PDF, Excel e CSV.
