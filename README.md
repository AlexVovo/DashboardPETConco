# Painel Oncológico Integrado

Painel Streamlit de oncologia com as oito abas originais. A opção **Fontes oficiais** integra estimativas anuais de incidência do INCA 2026–2028, estabelecimentos habilitados do Ministério da Saúde, acesso ao tratamento no PAINEL-Oncologia e mortalidade por câncer no SIM.

Os números de incidência do INCA são estimativas, não contagens de pacientes diagnosticados ou tratados. Cada base tem população, período e filtros próprios; os totais não são vinculados entre si para calcular tratamento ou sobrevida. O painel informa a edição, o período de referência e a data de consulta. Não transforma totais agregados em pacientes fictícios.

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
- No INCA, os valores `**` e `-` permanecem ausentes, nunca zero. Totais e subtotais não são somados aos tipos individuais. As taxas nacionais são reproduzidas da fonte, sem usar os denominadores aproximados da demonstração.
- O importador valida edição, número de categorias, cobertura das UFs e conciliação do total estadual com o nacional. Mudanças de edição/formato exigem revisão; o painel mantém a cópia anterior com aviso.

Para renovar a cópia distribuída no deploy, execute e publique o JSON atualizado:

```bash
python scripts/update_official_data.py
```

### Estrutura, acesso e mortalidade

| Aba | Fonte e cobertura da cópia atual |
|---|---|
| Estrutura | [Lista do Ministério da Saúde](https://www.gov.br/saude/pt-br/composicao/saes/cgcan/hospitais-habilitados), aba `HABILITAÇÃO 2026`: 383 estabelecimentos com CNES, incluindo UNACON, CACON e unidades de complexos hospitalares. A aba de serviços isolados de radioterapia não está incluída. |
| Acesso | [PAINEL-Oncologia](https://tabnet.datasus.gov.br/cgi/dhdat.exe?PAINEL_ONCO/PAINEL_ONCOLOGIABR.def): anos de diagnóstico 2024–2026, grupo `Neoplasias Malignas (Lei nº 12.732/12)`, ambos os sexos, UF de residência e faixas de tempo de tratamento. Fonte atualizada em 15/11/2026. |
| Câncer infantil | O mesmo PAINEL-Oncologia, filtro de 0 a 19 anos. É um subconjunto das linhas de todas as idades, que não deve ser somado a elas. Não equivale a uma classificação ICCC-3. |
| Desfecho | [SIM](https://dadosabertos.saude.gov.br/dataset/sim): óbitos não fetais (`TIPOBITO=2`), causa básica CID-10 C00–C97, UF de residência, sexo, faixa etária, mês e ano. 2024 sem indicação de preliminar no catálogo; 2025 preliminar com registros até setembro; 2026 2ª prévia com registros até agosto. |

Essas três fontes são **cópias publicadas junto com o código**, sem baixar os grandes arquivos do SIM a cada acesso. O botão de consulta do painel atualiza somente o INCA. Para renovar as demais cópias:

```bash
python scripts/update_health_data.py --source all --raw-dir /tmp/petconco-sources
```

Também é possível executar cada importação com `--source hospitals`, `--source oncology` ou `--source mortality`, e escolher os anos com `--years 2024 2025 2026`. `--reuse-downloads` reprocessa arquivos já baixados no diretório informado. Os arquivos brutos ficam fora do repositório; do SIM, somente os agregados e metadados são publicados. A importação do PAINEL-Oncologia usa a rota pública HTTP quando HTTPS está indisponível; a URL usada fica registrada nos metadados.

O importador valida CNES e cobertura territorial, soma das faixas de tempo versus total e soma das UFs versus total publicado. Rejeita respostas de tratamento com ano diferente do solicitado. No SIM, valida causa, tipo de óbito, data e cobertura das UFs; os arquivos de origem e o agregado têm hashes registrados. Uma atualização que falhe não substitui a cópia daquela fonte.

No acesso, o percentual em até 60 dias considera apenas os casos com tempo informado. **Sem informação de tratamento não significa não tratado**; não é possível calcular média exata a partir de faixas de tempo. No SIM, bases parciais não devem ser comparadas como anos completos; ausência de meses e sub-registro são informados na aba.

Os testes rodam sem acesso à internet:

```bash
python -m unittest discover -s tests -v
```

## Deploy no Streamlit Community Cloud

1. Envie o código, `requirements.txt`, a pasta `assets/` e a pasta `data/` para o GitHub, incluindo os módulos `official_*.py` e `health_*.py`.
2. Entre em https://share.streamlit.io com sua conta do GitHub e clique em **Create app**.
3. Selecione o repositório `AlexVovo/DashboardPETConco`, branch `main` e arquivo principal `app.py`.
4. Em **Advanced settings**, selecione Python **3.12** (versão validada localmente).
5. Clique em **Deploy** e aguarde a instalação das dependências de `requirements.txt`.

O painel inicia em **Fontes oficiais**; não precisa de CSV nem de secrets. A demonstração sintética só aparece quando selecionada explicitamente.

## Dados reais
Na barra lateral, selecione **CSV de casos** para usar dados individuais próprios. Esse modo não gera casos ou hospitais sintéticos e só exibe hospitais quando um arquivo correspondente é carregado. Carregue:
- **CSV de casos** (1 linha por caso). Obrigatórias: ano, mes, regiao, sexo, idade, segmento, tipo, atendimento, tratamento, tratado, dias_dx_trat, dist_km, estadio, meses, obito, desfecho. Opcionais: fila_regulador, fila_consulta, custo_hosp, custo_amb.
- **CSV de hospitais** (opcional): hospital, regiao, esfera, habilitacao, segmento, tipo, ocupacao.

Regiões: Norte, Nordeste, Centro-Oeste, Sudeste, Sul. `segmento`: Adulto ou Pediátrico.

## Limitações conhecidas
- Seguimento, sobrevida, cura, recorrência, estadiamento, classificação ICCC-3, ocupação hospitalar, distância percorrida, filas e custos ainda não foram integrados. As oito abas originais são preservadas; indicadores ainda sem base aparecem como indisponíveis. Consulte **Cobertura e fontes dos dados** no rodapé.
- As estimativas por localização primária não permitem separar adultos e crianças nem produzir classificação ICCC-3, sobrevida ou evolução anual observada.
- No modo de demonstração, população por região e fração adulto/pediátrico (`POP`, `SH`) são aproximações. O cálculo de taxas com esses denominadores fica desabilitado no modo CSV.
- A projeção do modo CSV/demonstração é tendência linear simples, só ilustrativa; não é a estimativa oficial do INCA.
- Abas de fila e custo do modo CSV dependem de colunas opcionais.
