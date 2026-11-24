"""Abas com recortes independentes das bases públicas de assistência e mortalidade."""
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from health_sources import DATA_DIR, UF_NAMES, UNKNOWN
from official_data import REGIONS, STATE_REGION

AGE_ORDER = ['0–4', '5–9', '10–14', '15–19', '20–39', '40–59', '60–79', '80+', 'Ignorada']
TIME_LABELS = {'ate_30': 'Até 30 dias', 'de_31_a_60': '31 a 60 dias',
               'mais_60': 'Mais de 60 dias', 'sem_informacao': 'Sem informação de tratamento'}


@st.cache_data(max_entries=1)
def load_health_data():
    hospitals = json.loads((DATA_DIR / 'hospitais.json').read_text())
    access = json.loads((DATA_DIR / 'acesso_oncologia.json').read_text())
    mortality = json.loads((DATA_DIR / 'mortalidade_sim.json').read_text())
    deaths = pd.read_csv(DATA_DIR / 'mortalidade_sim.csv.gz', dtype={'cid3': str})
    return hospitals, access, mortality, deaths


def fmt(value):
    return f'{value:,.0f}'.replace(',', '.')


def source_caption(metadata, description):
    date = pd.Timestamp(metadata['consultado_em']).strftime('%d/%m/%Y às %H:%M')
    st.caption(f'{description} · Coleta: {date} (Brasília). Cópia publicada com o painel; atualização por nova importação.')
    st.markdown(f"[Consultar fonte oficial]({metadata['fonte']})")


def geography(frame, key):
    x = frame.copy()
    if 'estado' not in x:
        x['estado'] = x.uf.map(UF_NAMES).fillna(UNKNOWN)
        x['regiao'] = x.estado.map(STATE_REGION).fillna(UNKNOWN)
    a, b = st.columns(2)
    regions = a.multiselect('Regiões', list(REGIONS) + ([UNKNOWN] if UNKNOWN in set(x.regiao) else []),
                            default=list(REGIONS) + ([UNKNOWN] if UNKNOWN in set(x.regiao) else []), key=key + '_regions')
    x = x[x.regiao.isin(regions)]
    states = b.multiselect('UFs (vazio = todas das regiões selecionadas)', sorted(x.uf.unique()), key=key + '_ufs')
    if states:
        x = x[x.uf.isin(states)]
    return x


def show(fig, key, height=380):
    st.plotly_chart(fig.update_layout(height=height, margin=dict(l=0, r=0, t=40, b=0)), key='chart_' + key)


def render_structure(metadata):
    st.subheader('Estrutura de atenção')
    source_caption(metadata, metadata['referencia'])
    st.caption('Os filtros desta aba são próprios. Habilitação não informa ocupação, vagas ou disponibilidade em tempo real.')
    x = geography(pd.DataFrame(metadata['hospitais']), 'hospital')
    segment = st.selectbox('Habilitação pediátrica', ['Todas', 'Com oncologia pediátrica explícita'], key='hospital_ped')
    if segment != 'Todas':
        x = x[x.pediatria]
    search = st.text_input('Buscar hospital ou município', key='hospital_search').strip()
    if search:
        x = x[x.hospital.str.contains(search, case=False, regex=False) | x.municipio.str.contains(search, case=False, regex=False)]
    if x.empty:
        st.info('Nenhum estabelecimento encontrado com esses filtros.')
        return
    metrics = [('Estabelecimentos listados', x.cnes.nunique()), ('UNACON', x[x.categoria == 'UNACON'].cnes.nunique()),
               ('CACON', x[x.categoria == 'CACON'].cnes.nunique()), ('Com habilitação pediátrica', x[x.pediatria].cnes.nunique())]
    for col, (label, value) in zip(st.columns(4), metrics):
        col.metric(label, fmt(value))
    a, b = st.columns(2)
    with a:
        show(px.pie(x, names='categoria', hole=.45, title='Estabelecimentos por categoria'), 'hospital_category')
    with b:
        g = x.groupby(['regiao', 'categoria']).size().reset_index(name='estabelecimentos')
        show(px.bar(g, x='regiao', y='estabelecimentos', color='categoria',
                    labels={'regiao': 'Região', 'estabelecimentos': 'Estabelecimentos', 'categoria': 'Categoria'},
                    title='Distribuição da rede habilitada'), 'hospital_regions')
    st.dataframe(x[['cnes', 'hospital', 'estado', 'municipio', 'habilitacao']].rename(columns={
        'cnes': 'CNES', 'hospital': 'Estabelecimento', 'estado': 'Estado', 'municipio': 'Município', 'habilitacao': 'Habilitação'}),
        hide_index=True, column_config={'CNES': st.column_config.TextColumn()})
    st.caption(metadata['cobertura'] + ' UNACON/CACON são contados por CNES distinto; unidades de complexos aparecem separadamente. '
               'Natureza jurídica, ocupação e serviços por tipo de tumor não constam desta planilha.')
    st.download_button('Baixar estabelecimentos do recorte (CSV)', x.to_csv(index=False), 'hospitais_recorte.csv', 'text/csv', key='hosp_download')


def render_access(metadata, pediatric=False):
    key = 'ped_access' if pediatric else 'access'
    st.subheader('Câncer infantil e adolescente (ICCC-3)' if pediatric else 'Acesso ao tratamento')
    if pediatric:
        st.info('Disponível: casos de 0 a 19 anos e intervalo até o primeiro tratamento informado no SUS. '
                'Este recorte por idade não é uma classificação ICCC-3; grupos por morfologia e sobrevida permanecem indisponíveis.')
    frame = pd.DataFrame(metadata['dados'])
    years = sorted(frame.ano.unique())
    year = st.selectbox('Ano do diagnóstico', years, index=years.index(2025) if 2025 in years else len(years)-1, key=key+'_year')
    segment = '0–19 anos' if pediatric else st.selectbox('Faixa etária — acesso', ['Todas as idades', '0–19 anos'], key=key+'_segment')
    query = next(q for q in metadata['consultas'] if q['ano'] == year and q['segmento'] == segment)
    source_caption(query | {'fonte': metadata['fonte']}, f"Diagnósticos de {year} · Atualização na fonte: {query['atualizado_na_fonte']} · {segment}")
    st.caption('Filtros próprios desta aba. Grupo monitorado: Neoplasias Malignas (Lei nº 12.732/12), ambos os sexos. '
               'Não é a totalidade estimada pelo INCA nem uma base de saúde suplementar.')
    if year == max(years):
        st.warning('Ano corrente: diagnóstico e tratamento ainda sujeitos a atualização. Não compare esse total diretamente com anos completos.')
    x = geography(frame[(frame.ano == year) & (frame.segmento == segment)], key)
    if x.empty:
        st.info('Nenhum registro com os filtros selecionados.')
        return
    counts = x[list(TIME_LABELS) + ['casos']].sum()
    informed = int(counts.ate_30 + counts.de_31_a_60 + counts.mais_60)
    timely = (counts.ate_30 + counts.de_31_a_60) / informed * 100 if informed else None
    metrics = [('Casos na tabulação', fmt(counts.casos)), ('Com tempo de tratamento informado', fmt(informed)),
               ('Até 60 dias, entre tempos informados', f'{timely:.1f}%' if timely is not None else '—'),
               ('Sem informação de tratamento', fmt(counts.sem_informacao))]
    for col, (label, value) in zip(st.columns(4), metrics):
        col.metric(label, value)
    st.caption('O percentual usa apenas as três faixas de tempo informado como denominador. '
               'Sem informação de tratamento não significa que o paciente não foi tratado. '
               'As faixas são reproduzidas da tabulação oficial; não permitem calcular o tempo médio em dias.')
    buckets = pd.DataFrame([{'Faixa': label, 'Casos': int(counts[column])} for column, label in TIME_LABELS.items()])
    a, b = st.columns(2)
    with a:
        show(px.bar(buckets, x='Faixa', y='Casos', title='Intervalo entre diagnóstico e primeiro tratamento informado'), key+'_buckets')
    with b:
        g = x.groupby('regiao')[list(TIME_LABELS)].sum().reset_index()
        g['com_tempo'] = g.ate_30 + g.de_31_a_60 + g.mais_60
        g['percentual'] = ((g.ate_30 + g.de_31_a_60) / g.com_tempo.where(g.com_tempo > 0) * 100)
        show(px.bar(g, x='regiao', y='percentual', labels={'regiao': 'Região', 'percentual': '% até 60 dias'},
                    title='Até 60 dias entre casos com tempo informado'), key+'_regions')
    st.dataframe(x[['uf', 'ate_30', 'de_31_a_60', 'mais_60', 'sem_informacao', 'casos']].rename(columns={
        'uf': 'UF de residência', **TIME_LABELS, 'casos': 'Casos na tabulação'}), hide_index=True)
    st.caption('Distância percorrida, tempo médio exato e comparação SUS × suplementar ainda não estão disponíveis nesta integração.')
    st.download_button('Baixar acesso do recorte (CSV)', x.to_csv(index=False), f'acesso_{year}.csv', 'text/csv', key=key+'_download')


def render_mortality(metadata, deaths):
    st.subheader('Desfecho')
    years = sorted(deaths.ano.unique())
    # Prefere ano sem indicação de preliminar; dados mais recentes continuam selecionáveis.
    complete = [m['ano'] for m in metadata['anos'] if m['situacao'] == 'Sem indicação de preliminar no catálogo']
    default = max(complete or years)
    year = st.selectbox('Ano do óbito', years, index=years.index(default), key='mortality_year')
    resource = next(m for m in metadata['anos'] if m['ano'] == year)
    source_caption(metadata, f"{resource['nome_recurso']} · {resource['situacao']}")
    st.caption(f"Atualização do recurso no catálogo: {resource['atualizado_no_catalogo']}.")
    st.caption(f"Último mês com registro no arquivo: {resource['ultimo_mes_com_registro']:02d}/{year}. "
               'A presença de um mês não garante completude. Filtros próprios desta aba; os filtros de incidência do INCA não são aplicados.')
    if resource['situacao'] != 'Sem indicação de preliminar no catálogo':
        st.warning('Base preliminar/prévia, sujeita a revisões e sub-registro. O arquivo disponível não representa um ano completo; '
                   'não interprete diferenças em relação a anos completos como queda de mortalidade.')
    x = geography(deaths[deaths.ano == year], 'mortality')
    a, b = st.columns(2)
    sexes = a.multiselect('Sexo — óbitos', ['Masculino', 'Feminino', 'Ignorado'], default=['Masculino', 'Feminino', 'Ignorado'], key='mortality_sex')
    ages = b.multiselect('Faixa etária — óbitos', AGE_ORDER, default=AGE_ORDER, key='mortality_age')
    causes = st.multiselect('Causa básica (CID-10, categoria de três caracteres)', sorted(x.cid3.unique()), key='mortality_causes',
                            help='Exemplos: C50 mama; C61 próstata; C34 brônquios e pulmão. Categorias não são grupos ICCC-3.')
    x = x[x.sexo.isin(sexes) & x.faixa_etaria.isin(ages)]
    if causes:
        x = x[x.cid3.isin(causes)]
    if x.empty:
        st.info('Nenhum óbito com os filtros selecionados.')
        return
    st.metric('Óbitos por câncer registrados — recorte selecionado', fmt(x.obitos.sum()))
    st.caption('Causa básica CID-10 C00–C97, óbitos não fetais e local de residência. '
               'Não é percentual de óbitos entre os casos estimados pelo INCA nem óbitos no seguimento de uma coorte.')
    g = x.groupby('cid3', as_index=False).obitos.sum().nlargest(20, 'obitos').sort_values('obitos')
    show(px.bar(g, x='obitos', y='cid3', orientation='h', labels={'obitos': 'Óbitos', 'cid3': 'Causa básica (CID-10)'},
                title='Óbitos por categoria CID-10 — até 20 maiores grupos'), 'mortality_causes_chart', height=440)
    a, b = st.columns(2)
    with a:
        g = x.groupby(['faixa_etaria', 'sexo'], as_index=False).obitos.sum()
        show(px.bar(g, x='faixa_etaria', y='obitos', color='sexo', barmode='group',
                    category_orders={'faixa_etaria': AGE_ORDER}, labels={'faixa_etaria': 'Faixa etária', 'obitos': 'Óbitos', 'sexo': 'Sexo'},
                    title='Óbitos por idade e sexo'), 'mortality_age_chart')
    with b:
        g = x.groupby('regiao', as_index=False).obitos.sum()
        show(px.bar(g, x='regiao', y='obitos', labels={'regiao': 'Região', 'obitos': 'Óbitos'},
                    title='Óbitos por região de residência'), 'mortality_region_chart')
    monthly = x.groupby('mes', as_index=False).obitos.sum()
    show(px.line(monthly, x='mes', y='obitos', markers=True, labels={'mes': 'Mês do óbito', 'obitos': 'Óbitos'},
                 title=f'Distribuição mensal dos registros disponíveis — {year}'), 'mortality_month_chart')
    st.info('Sobrevida, cura, recorrência e associação entre tratamento e desfecho exigem uma base de seguimento vinculada; '
            'não podem ser calculadas com estes agregados do SIM.')
    st.download_button('Baixar óbitos agregados do recorte (CSV)', x.to_csv(index=False), f'obitos_cancer_{year}.csv', 'text/csv', key='mortality_download')
