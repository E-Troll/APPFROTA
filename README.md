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

### Configuração necessária

1. Crie um projeto no [Supabase](https://supabase.com/dashboard) e um bucket **privado** chamado `odometer-photos`.
2. No Supabase, copie a connection string PostgreSQL em **Project Settings > Database**. Para funções serverless, prefira a conexão Session Pooler. Configure na Vercel como `DATABASE_URL` e confirme que usa SSL (`sslmode=require`).
3. Adicione na Vercel as variáveis `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY`, além de `DATABASE_URL`. A chave `service_role` é secreta: mantenha-a somente no ambiente de servidor, nunca no frontend ou em arquivos versionados.
4. Gere e configure `CRON_SECRET` na Vercel como segredo forte e aleatório. O cron diário configurado em `vercel.json` exclui viagens e fotos com mais de 45 dias; a remoção ocorre na execução diária após o prazo.
5. Salve as variáveis para os ambientes desejados e faça um novo deploy. O entrypoint valida as variáveis e não usa o disco temporário da Vercel como armazenamento persistente.

O processamento converte as imagens para JPEG, limita a maior dimensão a 1280 px e busca comprimi-las a no máximo 220 KiB sem sacrificar completamente a legibilidade do odômetro. O plano gratuito do Supabase informa 500 MB para o banco e 1 GB para arquivos; a quantidade de fotos depende do tamanho efetivo e do espaço usado por outros dados. Consulte [os limites e preços atuais](https://supabase.com/pricing).

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
