# Controle de Quilometragem Veicular (App Veículo)

Sistema web completo para controle e auditoria de quilometragem de veículos, projetado para rodar em servidor local (`localhost`). Permite o registro detalhado de viagens corporativas ou particulares com captura de fotos do odômetro (com carimbo visual e imutável de data/hora), pausas/paradas intermediárias, encerramento de viagem com cálculo automático de distância e exportação de relatórios em **PDF**, **Excel (.xlsx)** e **CSV**.

---

## 📁 Estrutura de Pastas do Projeto

```text
APP Veiculo/
├── app.py                     # Servidor Flask principal (rotas web, APIs e exports)
├── database.py                # Camada de banco de dados SQLite (tabelas, índices, queries)
├── requirements.txt           # Dependências Python do projeto
├── run.sh                     # Script para iniciar o servidor com um comando
├── README.md                  # Documentação completa
├── services/
│   ├── __init__.py
│   ├── image_service.py       # Processamento de imagem, correção EXIF e carimbo d'água (Pillow)
│   ├── export_excel.py        # Geração de planilhas Excel formatadas com fórmulas (openpyxl)
│   └── export_pdf.py          # Geração de relatórios PDF executivos em Paisagem (ReportLab)
├── static/
│   ├── css/
│   │   └── style.css          # Estilos personalizados, animações de pulso e responsividade
│   └── js/
│       └── app.js             # Lógica reativa SPA, captura de câmera, previews e modais
├── templates/
│   └── index.html             # Interface responsiva moderna (Bootstrap 5 + Icons)
├── tests/
│   ├── __init__.py
│   └── test_app.py            # Suíte completa de testes automatizados unitários e de integração
└── uploads/                   # Diretório de armazenamento das fotos carimbadas do odômetro
    └── .gitkeep
```

---

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python 3 + Flask (leve, robusto e sem dependências externas complexas).
- **Banco de Dados:** SQLite3 (nativo do Python, zero-configuração, com chaves estrangeiras e índices).
- **Processamento de Imagens:** Pillow (PIL) com correção de rotação EXIF de fotos de smartphones e carimbo d'água com selo visual contendo tipo de registro, data/hora, odômetro, condutor e placa.
- **Exportação de Relatórios:**
  - **Excel (.xlsx):** `openpyxl` com cabeçalhos estilizados, larguras de coluna automáticas, formatação numérica, hiperlinks diretos para fotos e fórmula `=SUM(...)` para totais.
  - **PDF (.pdf):** `reportlab` com layout Paisagem A4, cards de KPIs, tabela paginada com numeração dinâmica de páginas ("Página X de Y") e seção de auditoria com links e referências das imagens.
  - **CSV (.csv):** UTF-8 com BOM e delimitador `;` para compatibilidade imediata com Microsoft Excel em português.
- **Frontend:** HTML5, CSS3, JavaScript Vanilla (ES6+), Bootstrap 5.3 e Bootstrap Icons. Interface 100% responsiva (Mobile First) que aciona diretamente a câmera do celular com `capture="environment"`.

---

## 🚀 Funcionalidades Principais

1. **Fluxo Completo de Viagem:**
   - **Saída:** Registro de placa, condutor, modelo, destino, KM inicial e foto do odômetro. O sistema aplica o carimbo com timestamp na imagem e persiste no banco.
   - **Parada:** Botão de pausa para registrar abastecimento, almoço, pedágio ou descarga, exigindo a quilometragem do momento e nova foto carimbada. Validação: $KM_{parada} \ge KM_{anterior}$.
   - **Chegada (Encerramento):** Exige o KM final e foto de chegada. O sistema valida se $KM_{final} \ge KM_{parada}$ e calcula automaticamente a distância total percorrida ($KM_{total} = KM_{final} - KM_{inicial}$).
2. **Painel de Viagem Ativa:**
   - Enquanto uma viagem estiver em andamento, o sistema exibe um card destacado com indicador pulsante, cronômetro de tempo decorrido em tempo real, resumo de paradas realizadas e botões rápidos para adicionar nova parada ou encerrar a viagem.
3. **Gestão Segura de Imagens:**
   - Upload de imagens nos formatos JPG, PNG e WEBP.
   - Ajuste automático de orientação EXIF (para fotos tiradas na vertical ou horizontal em celulares).
   - Carimbo d'água indelével com data, hora, tipo de registro, placa e quilometragem.
   - Servimento seguro pelo endpoint `/uploads/<arquivo>`.
   - Visualizador de fotos integrado (Lightbox) na interface.
4. **Relatórios e Filtros Mensais:**
   - Filtro por mês/ano (`YYYY-MM`) ou geral.
   - Filtro por status (Finalizadas, Em Andamento, Canceladas).
   - Busca em tempo real por placa, motorista ou finalidade.
   - Indicadores numéricos (KPIs): Total de viagens, KM total percorrido, média de KM por viagem e total de veículos ativos.
   - Botões de exportação instantânea para **PDF**, **Excel** e **CSV**.

---

## 💻 Instruções para Instalação e Execução

### Pré-requisitos
- Python 3.8 ou superior instalado na máquina.

### Opção 1: Inicialização Automática (Recomendada)

Abra o terminal na pasta do projeto e execute o script:

```bash
cd "."
bash run.sh
```

O script criará o ambiente virtual (`venv`), instalará as dependências e iniciará o servidor automaticamente.

---

### Opção 2: Inicialização Manual Passo a Passo

Caso prefira executar comando por comando:

1. **Navegue até a pasta do projeto:**
   ```bash
   cd "."
   ```

2. **Crie e ative o ambiente virtual:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Inicie o servidor:**
   ```bash
   python app.py
   ```

5. **Acesse no navegador:**
   Abra no seu navegador de preferência:
   👉 **http://localhost:5050** (ou `http://127.0.0.1:5050`)

---

## 🧪 Como Rodar os Testes Automatizados

O projeto inclui uma suíte completa de testes unitários e de integração que valida uploads, carimbos d'água, cálculos de quilometragem, persistência no SQLite e geração de arquivos PDF, Excel e CSV.

Para executar os testes:

```bash
./venv/bin/python3 -m unittest discover tests -v
```

Resultado esperado:
```text
test_allowed_file (test_app.TestMileageApp) ... ok
test_delete_trip_and_cleanup_files (test_app.TestMileageApp) ... ok
test_exports_excel_pdf_and_csv (test_app.TestMileageApp) ... ok
test_finish_trip_and_distance_calculation (test_app.TestMileageApp) ... ok
test_image_watermarking (test_app.TestMileageApp) ... ok
test_index_route (test_app.TestMileageApp) ... ok
test_serve_uploaded_image (test_app.TestMileageApp) ... ok
test_start_trip_missing_fields (test_app.TestMileageApp) ... ok
test_start_trip_missing_photo (test_app.TestMileageApp) ... ok
test_start_trip_success_and_prevent_duplicate_active (test_app.TestMileageApp) ... ok
test_trip_stop_workflow_and_validations (test_app.TestMileageApp) ... ok

----------------------------------------------------------------------
Ran 11 tests in 0.18s

OK
```
