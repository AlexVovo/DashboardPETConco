"""Visualização de dados agregados oficiais, sem criar pacientes artificiais."""
import json

import pandas as pd
import plotly.express as px
import streamlit as st

from official_data import REGIONS, TOTAL, WITHOUT_SKIN, fetch_source, read_snapshot


@st.cache_data(ttl=86400, max_entries=1)
def load_official():
    try:
        return fetch_source(), None
    except Exception as exc:
        # A cópia mantém a data real da coleta e nunca é apresentada como consulta nova.
        return read_snapshot(), f'{type(exc).__name__}: {exc}'


def fmt(value):
    return f'{value:,.0f}'.replace(',', '.')


def render_official():
    st.title('Painel Oncológico Integrado')
    st.caption('Fonte oficial: INCA · Estimativa de incidência 2026–2028')
    st.info('Estimativas anuais de novos casos de câncer. Não representam contagens de diagnósticos '
            'registrados, atendimentos ou pacientes em acompanhamento.')
    if st.sidebar.button('Consultar fonte novamente'):
        load_official.clear()
    with st.spinner('Consultando as tabelas oficiais do INCA…'):
        data, error = load_official()
    if error:
        st.warning('Não foi possível consultar a fonte agora. Exibindo a cópia verificada incluída no projeto, '
                   'com a data de consulta indicada abaixo.')
        with st.expander('Detalhes da consulta'):
            st.text(error)
    consulted = pd.Timestamp(data['consultado_em']).strftime('%d/%m/%Y às %H:%M (%Z)')
    st.caption(f"Ano de referência: {data['ano_referencia']} · Atualização informada pelo INCA: "
               f"{data['atualizado_na_fonte'] or 'não informada'} · Consulta: {consulted}")
    st.markdown(f"[Consultar tabelas e notas metodológicas no INCA]({data['fonte']})")

    national = pd.DataFrame(data['nacional'])
    states = pd.DataFrame(data['estados'])
    national_tab, states_tab, coverage_tab = st.tabs(['Brasil: tipos e sexo', 'Estados e regiões', 'Cobertura e fontes'])
    with national_tab:
        sex = st.selectbox('Sexo — dados nacionais', ['Total', 'Homens', 'Mulheres'])
        subset = national[national.sexo == sex]
        total = subset.loc[subset.tipo == TOTAL, 'casos'].iloc[0]
        no_skin = subset.loc[subset.tipo == WITHOUT_SKIN, 'casos'].iloc[0]
        a, b = st.columns(2)
        a.metric('Novos casos estimados por ano', fmt(total))
        b.metric('Exceto pele não melanoma, por ano', fmt(no_skin))
        include_skin = st.checkbox('Incluir pele não melanoma no gráfico', value=False)
        detail = subset[~subset.tipo.isin([TOTAL, WITHOUT_SKIN])].copy()
        if not include_skin:
            detail = detail[detail.tipo != 'Pele não Melanoma']
        measure = st.selectbox('Indicador nacional', ['Casos estimados', 'Taxa bruta', 'Taxa ajustada'])
        field = {'Casos estimados': 'casos', 'Taxa bruta': 'taxa_bruta', 'Taxa ajustada': 'taxa_ajustada'}[measure]
        plot = detail.dropna(subset=[field]).sort_values(field)
        st.plotly_chart(px.bar(plot, x=field, y='tipo', orientation='h',
                              labels={field: measure, 'tipo': 'Localização primária'},
                              title=f'{measure} por localização primária — Brasil ({sex.lower()})',
                              color_discrete_sequence=['#1F6F78']).update_layout(height=650))
        st.caption('Taxas por 100 mil habitantes, reproduzidas da fonte. Para tumores específicos de sexo, '
                   'o denominador é a população do sexo correspondente. Taxas ajustadas por idade não devem ser somadas. '
                   'Valores não aplicáveis ou não publicados são omitidos do gráfico.')
        st.dataframe(detail.rename(columns={'tipo': 'Localização primária', 'sexo': 'Sexo', 'casos': 'Casos estimados/ano',
                                            'taxa_bruta': 'Taxa bruta/100 mil', 'taxa_ajustada': 'Taxa ajustada/100 mil'}),
                     hide_index=True)

    with states_tab:
        regions = st.multiselect('Regiões', list(REGIONS), default=list(REGIONS))
        options = sorted(states[states.regiao.isin(regions)].estado.unique())
        selected_states = st.multiselect('Estados (vazio = todos das regiões selecionadas)', options)
        categories = sorted(states.tipo.unique())
        kind = st.selectbox('Localização primária ou total — estados', categories,
                            index=categories.index('Todas as neoplasias malignas'))
        subset = states[states.regiao.isin(regions) & (states.tipo == kind)]
        if selected_states:
            subset = subset[subset.estado.isin(selected_states)]
        if subset.empty:
            st.info('Selecione pelo menos uma região para visualizar os dados.')
        else:
            missing = subset.casos.isna().sum()
            if missing:
                st.warning(f'{missing} UF(s) com valor suprimido/não divulgado (**). Esses valores são desconhecidos; '
                           'não são tratados como zero nem incluídos em um total regional.')
            else:
                st.metric('Casos estimados por ano — recorte selecionado', fmt(subset.casos.sum()))
            plot = subset.dropna(subset=['casos']).sort_values('casos')
            st.plotly_chart(px.bar(plot, x='casos', y='estado', color='regiao', orientation='h',
                                  labels={'casos': 'Casos estimados/ano', 'estado': 'Estado', 'regiao': 'Região'},
                                  title=f'{kind} — estimativa anual por UF').update_layout(height=650))
            grouped = subset.groupby('regiao').casos.agg(lambda x: x.sum() if x.notna().all() else float('nan')).reset_index()
            st.dataframe(grouped.rename(columns={'regiao': 'Região', 'casos': 'Casos estimados/ano'}), hide_index=True)
            st.dataframe(subset[['estado', 'regiao', 'tipo', 'casos', 'valor_publicado']].rename(columns={
                'estado': 'Estado', 'regiao': 'Região', 'tipo': 'Localização primária',
                'casos': 'Casos estimados/ano', 'valor_publicado': 'Valor na fonte'}), hide_index=True)
        st.caption('Dados estaduais para ambos os sexos. Não há filtro etário ou de sexo nesta tabela. '
                   'Categorias de total incluem os tipos individuais: não devem ser somadas a eles. '
                   'Arredondamentos e valores suprimidos podem produzir diferenças entre somas e totais publicados.')

    with coverage_tab:
        st.markdown('A integração atual contém as tabelas nacionais por sexo e localização primária e as tabelas '
                    'das 27 UFs. A estimativa anual vale para o triênio indicado; não é uma série histórica '
                    'nem uma medição em tempo real. A classificação por localização primária não corresponde '
                    'a uma classificação de câncer infantil por ICCC-3.')
        st.dataframe(pd.DataFrame([
            {'Indicador': 'Incidência estimada', 'Fonte': 'INCA 2026–2028', 'Situação': 'Integrado'},
            {'Indicador': 'Diagnósticos e início do tratamento', 'Fonte': 'PAINEL-Oncologia / DATASUS', 'Situação': 'Ainda não integrado'},
            {'Indicador': 'Óbitos observados', 'Fonte': 'SIM / DATASUS', 'Situação': 'Ainda não integrado'},
            {'Indicador': 'Hospitais habilitados', 'Fonte': 'CNES e habilitações', 'Situação': 'Ainda não integrado'},
            {'Indicador': 'Seguimento, estadiamento e ICCC-3', 'Fonte': 'Registros de câncer compatíveis', 'Situação': 'Ainda não integrado'},
            {'Indicador': 'Fila de regulação e custos', 'Fonte': 'Regulação / SIH / SIA', 'Situação': 'Ainda não integrado'},
        ]), hide_index=True)
        st.markdown('[Fontes de saúde do DATASUS](https://datasus.saude.gov.br/informacoes-de-saude-tabnet/)')
        st.caption('O painel consulta o INCA na primeira visita e reutiliza a consulta por até 24 horas. '
                   'O botão na barra lateral permite uma nova consulta. Se a edição ou o formato mudar, '
                   'a importação é interrompida e a cópia verificada é exibida com aviso.')
    st.download_button('Baixar dados e metadados oficiais (JSON)',
                       data=json.dumps(data, ensure_ascii=False, indent=2),
                       file_name='inca_estimativa_2026.json', mime='application/json')
