# Painel Oncológico Integrado

Painel Streamlit (câncer adulto e infantil). Sem CSV, roda com dados sintéticos de demonstração.

## Rodar
```
pip install -r requirements.txt
streamlit run app.py
```
O tema fica em `.streamlit/config.toml` (precisa estar nessa pasta para o Streamlit ler).

## Deploy no Streamlit Community Cloud

1. Envie as alterações de `app.py`, `.gitignore` e este README para o GitHub.
2. Entre em https://share.streamlit.io com sua conta do GitHub e clique em **Create app**.
3. Selecione o repositório `felipegutdeveloper/DashboardPETConco`, branch `main` e arquivo principal `app.py`.
4. Em **Advanced settings**, selecione Python **3.12** (versão validada localmente).
5. Clique em **Deploy** e aguarde a instalação das dependências de `requirements.txt`.

O painel inicia com dados sintéticos; não precisa de arquivos CSV nem de secrets para a demonstração.

## Dados reais
Na barra lateral, carregue:
- **CSV de casos** (1 linha por caso). Obrigatórias: ano, mes, regiao, sexo, idade, segmento, tipo, atendimento, tratamento, tratado, dias_dx_trat, dist_km, estadio, meses, obito, desfecho. Opcionais: fila_regulador, fila_consulta, custo_hosp, custo_amb.
- **CSV de hospitais** (opcional): hospital, regiao, esfera, habilitacao, segmento, tipo, ocupacao.

Regiões: Norte, Nordeste, Centro-Oeste, Sudeste, Sul. `segmento`: Adulto ou Pediátrico.

## Limitações conhecidas
- População por região e fração adulto/pediátrico (`POP`, `SH`) são aproximações de demonstração; troque por dados do IBGE para taxas reais.
- Projeção é tendência linear simples, só ilustrativa.
- Abas de fila e custo dependem de colunas opcionais (pode não haver dado público).
