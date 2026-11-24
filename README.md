# Painel Oncológico Integrado

Painel Streamlit de oncologia. A página inicial usa as tabelas oficiais do INCA de **estimativas anuais de incidência 2026–2028**, com recortes nacionais por sexo e localização primária e dados das 27 UFs por localização primária.

Esses números são estimativas publicadas, não contagens de pacientes diagnosticados ou tratados. O painel informa a edição, o ano de referência, a atualização na fonte e a data de consulta. Não transforma totais agregados em pacientes fictícios.

## Rodar
```
pip install -r requirements.txt
streamlit run app.py
```
O ícone da aba fica em `assets/icon.png`.

## Dados oficiais e atualização

- Fonte: [INCA — Brasil, estimativa dos casos novos](https://www.gov.br/inca/pt-br/assuntos/cancer/numeros/estimativa/estado-capital/brasil).
- Consulta à fonte na primeira visita, com cache de até 24 horas e botão **Consultar fonte novamente**. Não há atualização em segundo plano sem acessos ao app.
- Se a consulta falhar, utiliza `data/inca_2026.json`, uma cópia verificada com procedência, data de coleta e hash do HTML. Um aviso identifica essa situação; a data da cópia não é alterada.
- Os valores `**` e `-` permanecem ausentes, nunca zero. Totais e subtotais não são somados aos tipos individuais. As taxas nacionais são reproduzidas da fonte, sem usar os denominadores aproximados da demonstração.
- O importador valida edição, número de categorias, cobertura das UFs e conciliação do total estadual com o nacional. Mudanças de edição/formato exigem revisão; o painel mantém a cópia anterior com aviso.

Para renovar a cópia distribuída no deploy, execute e publique o JSON atualizado:

```bash
python scripts/update_official_data.py
```

Os testes rodam sem acesso à internet:

```bash
python -m unittest discover -s tests -v
```

## Deploy no Streamlit Community Cloud

1. Envie o código, a pasta `assets/` e a pasta `data/` para o GitHub, incluindo `official_data.py` e `official_dashboard.py`.
2. Entre em https://share.streamlit.io com sua conta do GitHub e clique em **Create app**.
3. Selecione o repositório `felipegutdeveloper/DashboardPETConco`, branch `main` e arquivo principal `app.py`.
4. Em **Advanced settings**, selecione Python **3.12** (versão validada localmente).
5. Clique em **Deploy** e aguarde a instalação das dependências de `requirements.txt`.

O painel inicia na visão oficial do INCA; não precisa de CSV nem de secrets. A demonstração sintética só aparece quando selecionada explicitamente.

## Dados reais
Na barra lateral, selecione **CSV de casos** para usar dados individuais próprios. Esse modo não gera casos ou hospitais sintéticos e só exibe hospitais quando um arquivo correspondente é carregado. Carregue:
- **CSV de casos** (1 linha por caso). Obrigatórias: ano, mes, regiao, sexo, idade, segmento, tipo, atendimento, tratamento, tratado, dias_dx_trat, dist_km, estadio, meses, obito, desfecho. Opcionais: fila_regulador, fila_consulta, custo_hosp, custo_amb.
- **CSV de hospitais** (opcional): hospital, regiao, esfera, habilitacao, segmento, tipo, ocupacao.

Regiões: Norte, Nordeste, Centro-Oeste, Sudeste, Sul. `segmento`: Adulto ou Pediátrico.

## Limitações conhecidas
- A integração oficial atual cobre estimativas de incidência; tratamento (PAINEL-Oncologia), mortalidade observada (SIM), hospitais (CNES), seguimento/ICCC-3, filas e custos ainda não foram integrados. As oito abas originais são preservadas; indicadores ainda sem base aparecem como indisponíveis. Consulte **Cobertura e fontes dos dados** no rodapé. Os dados dessas fontes não são intercambiáveis e não oferecem, necessariamente, seguimento individual vinculável.
- As estimativas por localização primária não permitem separar adultos e crianças nem produzir classificação ICCC-3, sobrevida ou evolução anual observada.
- No modo de demonstração, população por região e fração adulto/pediátrico (`POP`, `SH`) são aproximações. O cálculo de taxas com esses denominadores fica desabilitado no modo CSV.
- A projeção do modo CSV/demonstração é tendência linear simples, só ilustrativa; não é a estimativa oficial do INCA.
- Abas de fila e custo do modo CSV dependem de colunas opcionais.
