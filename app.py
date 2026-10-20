"""Painel Oncológico Integrado (adulto e infantil).

Fontes previstas: Painel Oncológico (DATASUS), RHC-INCA, SIM e Painel Regulador (SMSPOA).
Rodar:  pip install -r requirements.txt  &&  streamlit run app.py
"""
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Painel Oncológico Integrado", layout="wide")
px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = ["#1F6F78", "#D9822B", "#5B4B8A", "#3E8E41", "#B23A48", "#2E86C1", "#8C6D46", "#6C7A89"]

REG = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
POP = dict(zip(REG, [17.4e6, 54.6e6, 16.3e6, 84.8e6, 29.9e6]))  # população aproximada (demo)
SH = {"Todos": 1.0, "Adulto": .72, "Pediátrico": .28}  # fração da população por segmento (demo)
ADU = {"Mama": .17, "Próstata": .16, "Cólon e reto": .10, "Colo do útero": .08, "Pulmão": .09, "Estômago": .06,
       "Pele (não melanoma)": .20, "Tireoide": .05, "Esôfago": .03, "Fígado": .03, "Linfoma não Hodgkin": .03}
ICCC = {"I Leucemias": .30, "II Linfomas": .12, "III Sistema nervoso central": .20, "IV Sistema simpático": .06,
        "V Retinoblastoma": .03, "VI Tumores renais": .05, "VII Tumores hepáticos": .02, "VIII Tumores ósseos": .06,
        "IX Sarcomas de partes moles": .06, "X Células germinativas": .04, "XI Carcinomas e melanomas": .04, "XII Outros": .02}
HAZ = {"Pulmão": .06, "Esôfago": .06, "Fígado": .07, "Estômago": .04, "Cólon e reto": .02, "Mama": .008, "Próstata": .006,
       "Colo do útero": .015, "Pele (não melanoma)": .002, "Tireoide": .002, "Linfoma não Hodgkin": .015,
       "I Leucemias": .008, "II Linfomas": .006, "III Sistema nervoso central": .015, "IV Sistema simpático": .02,
       "V Retinoblastoma": .003, "VI Tumores renais": .006, "VII Tumores hepáticos": .015, "VIII Tumores ósseos": .015,
       "IX Sarcomas de partes moles": .012, "X Células germinativas": .005, "XI Carcinomas e melanomas": .006}
FAIXAS = ["0-4", "5-9", "10-14", "15-19", "20-39", "40-59", "60-79", "80+"]
CORE = ["ano", "mes", "regiao", "sexo", "idade", "segmento", "tipo", "atendimento", "tratamento", "tratado",
        "dias_dx_trat", "dist_km", "estadio", "meses", "obito", "desfecho"]
HOSP_COLS = ["hospital", "regiao", "esfera", "habilitacao", "segmento", "tipo", "ocupacao"]
OPC = ["fila_regulador", "fila_consulta", "custo_hosp", "custo_amb"]
LAB = {"segmento": "Segmento (adulto × pediatria)", "atendimento": "Atendimento (SUS × suplementar)", "regiao": "Região de residência",
       "tipo": "Tipo de câncer", "sexo": "Sexo", "tratamento": "Tipo de tratamento", "faixa_etaria": "Faixa etária",
       "estadio": "Estadiamento", "ano": "Ano"}


def _p(d):
    v = np.array(list(d.values()), float)
    return v / v.sum()


SIM = {"true", "1", "sim", "s", "verdadeiro", "v", "yes", "y"}
NUM = ["ano", "mes", "idade", "dias_dx_trat", "dist_km", "meses", "obito"]


def prep(x):
    x = x.copy()
    for c in NUM:
        x[c] = pd.to_numeric(x[c], errors="coerce")
    # astype(bool) transformaria qualquer texto ("Não", "False") em True; por isso o mapeamento explícito
    x["tratado"] = x["tratado"].astype(str).str.strip().str.lower().isin(SIM)
    x["faixa_etaria"] = pd.cut(x["idade"], [0, 5, 10, 15, 20, 40, 60, 80, 130], right=False, labels=FAIXAS)
    for c in OPC:
        if c not in x:
            x[c] = np.nan
    return x


@st.cache_data
def gerar_demo(n=40000, seed=7):
    """Casos sintéticos: só para demonstrar o painel. Substitua por dados reais via CSV."""
    r = np.random.default_rng(seed)
    ped = r.random(n) < .12
    tipo = np.where(ped, r.choice(list(ICCC), n, p=_p(ICCC)), r.choice(list(ADU), n, p=_p(ADU)))
    sexo = r.choice(["Feminino", "Masculino"], n)
    sexo = np.where(np.isin(tipo, ["Mama", "Colo do útero"]), "Feminino", np.where(tipo == "Próstata", "Masculino", sexo))
    idade = np.where(ped, r.uniform(0, 19.9, n), np.clip(r.normal(62, 13, n), 20, 95)).astype(int)
    pa = np.linspace(.8, 1.2, 7)
    pa[2] *= .85
    regiao = r.choice(REG, n, p=_p(POP))
    atend = r.choice(["SUS", "Suplementar"], n, p=[.7, .3])
    trat = r.choice(["Cirurgia", "Quimioterapia", "Radioterapia"], n, p=[.4, .4, .2])
    f = pd.Series({"Norte": 1.35, "Nordeste": 1.2, "Centro-Oeste": 1.1, "Sudeste": 1.0, "Sul": .9}).reindex(regiao).to_numpy()
    tratado = r.random(n) > .06 * f
    dias = r.lognormal(np.log(np.where(ped, 30, 48)), .6, n) * f * np.where(atend == "Suplementar", .6, 1)
    dist = (r.lognormal(np.log(np.where(ped, 90, 35)), .8, n) * np.where(trat == "Radioterapia", 1.3, 1)
            * np.where(np.isin(regiao, ["Norte", "Centro-Oeste"]), 1.8, 1))
    est = r.choice(["I", "II", "III", "IV"], n, p=[.2, .3, .28, .22])
    haz = np.array([HAZ.get(t, .01) for t in tipo]) * pd.Series(est).map({"I": .4, "II": .7, "III": 1.2, "IV": 2.5}).to_numpy()
    t = r.exponential(1 / haz)
    cens = r.uniform(12, 60, n)
    obito = (t <= cens).astype(int)
    base = pd.Series(trat).map({"Cirurgia": 9000, "Quimioterapia": 14000, "Radioterapia": 11000}).to_numpy()
    ch = base * pd.Series(est).map({"I": .7, "II": 1, "III": 1.5, "IV": 2.2}).to_numpy() * r.lognormal(0, .3, n)
    fr = r.lognormal(np.log(20), .7, n).round()
    df = pd.DataFrame(dict(
        ano=r.choice(np.arange(2018, 2025), n, p=pa / pa.sum()), mes=r.integers(1, 13, n), regiao=regiao, sexo=sexo,
        idade=idade, segmento=np.where(ped, "Pediátrico", "Adulto"), tipo=tipo, atendimento=atend, tratamento=trat,
        tratado=tratado, dias_dx_trat=np.where(tratado, dias.round(), np.nan), dist_km=dist.round(1), estadio=est,
        meses=np.minimum(t, cens).round(1), obito=obito,
        desfecho=np.where(obito == 1, "Óbito", r.choice(["Cura / sem evidência", "Em seguimento", "Recorrência"], n, p=[.55, .35, .10])),
        fila_regulador=fr, fila_consulta=(fr + r.lognormal(np.log(25), .7, n)).round(),
        custo_hosp=ch.round(), custo_amb=(ch * .4 * r.lognormal(0, .3, n)).round()))
    return prep(df)


@st.cache_data
def gerar_hosp(seed=11, n=320):
    """Hospitais e serviços habilitados sintéticos (substituir por habilitações/CNES)."""
    r = np.random.default_rng(seed)
    h = pd.DataFrame({"hospital": [f"Hospital {i:03d}" for i in range(n)], "regiao": r.choice(REG, n, p=[.05, .2, .08, .45, .22]),
                      "esfera": r.choice(["Federal", "Estadual", "Municipal", "Filantrópico/Privado"], n, p=[.05, .25, .05, .65]),
                      "habilitacao": r.choice(["UNACON", "CACON", "UNACON c/ pediatria", "CACON c/ pediatria"], n, p=[.55, .2, .15, .1])})
    rows = []
    for x in h.itertuples():
        for t in r.choice(list(ADU), r.integers(3, 8), replace=False):
            rows.append((x.hospital, "Adulto", t, float(np.clip(r.normal(.75, .15), .3, 1.05))))
        if "pediatria" in x.habilitacao:
            for t in r.choice(list(ICCC), r.integers(3, 7), replace=False):
                rows.append((x.hospital, "Pediátrico", t, float(np.clip(r.normal(.7, .15), .3, 1.05))))
    s = pd.DataFrame(rows, columns=["hospital", "segmento", "tipo", "ocupacao"])
    return s.merge(h, on="hospital")


def km(x):
    """Kaplan-Meier: retorna (tempos, sobrevida)."""
    g = x.groupby("meses").obito.agg(["sum", "size"]).sort_index()
    risco = len(x) - g["size"].cumsum().shift(fill_value=0)
    s = (1 - g["sum"] / risco).cumprod()
    return [0, *g.index], [1, *s]


def show(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=0, r=0, t=40, b=0), legend_title_text="")
    st.plotly_chart(fig)


# ------------------------------------------------------------------ dados e filtros
st.sidebar.title("Painel Oncológico")
df, demo = gerar_demo(), True
up = st.sidebar.file_uploader("Dados reais (CSV)", type="csv", help="Use o esquema descrito no rodapé da página.")
if up is not None:
    raw = pd.read_csv(up)
    falta = [c for c in CORE if c not in raw.columns]
    if falta:
        st.sidebar.error("Faltam colunas: " + ", ".join(falta))
    else:
        cand = prep(raw).dropna(subset=["ano", "idade", "meses", "obito"])
        cand = cand.assign(ano=cand.ano.astype(int), obito=cand.obito.astype(int))
        fora = sorted(set(cand.regiao.dropna()) - set(REG))
        if cand.empty:
            st.sidebar.error("Nenhuma linha válida: confira ano, idade, meses e obito.")
        elif fora:
            st.sidebar.error("Regiões fora do padrão: " + ", ".join(map(str, fora)) + ". Esperado: " + ", ".join(REG) + ".")
        elif not set(cand.segmento) <= {"Adulto", "Pediátrico"}:
            st.sidebar.error("`segmento` deve ser Adulto ou Pediátrico.")
        else:
            df, demo = cand, False
            if len(cand) < len(raw):
                st.sidebar.warning(f"{len(raw) - len(cand):,} linhas descartadas por dados ausentes.".replace(",", "."))
S, demo_h = gerar_hosp(), True
uh = st.sidebar.file_uploader("Hospitais habilitados (CSV, opcional)", type="csv",
                              help="Colunas: " + ", ".join(HOSP_COLS))
if uh is not None:
    hraw = pd.read_csv(uh)
    if [c for c in HOSP_COLS if c not in hraw.columns]:
        st.sidebar.error("Faltam colunas em hospitais: " + ", ".join(c for c in HOSP_COLS if c not in hraw.columns))
    else:
        S, demo_h = hraw, False
tseg = df.groupby("tipo").segmento.first()

seg = st.sidebar.radio("Segmento", ["Todos", "Adulto", "Pediátrico"], horizontal=True)
opts = sorted(df[df.segmento == seg].tipo.unique() if seg != "Todos" else df.tipo.unique())
tipos = st.sidebar.multiselect("Tipo de câncer", opts, placeholder="Todos")
regs = st.sidebar.multiselect("Região de residência", REG, default=REG)
sexos = st.sidebar.multiselect("Sexo", ["Feminino", "Masculino"], default=["Feminino", "Masculino"])
amin, amax = int(df.ano.min()), int(df.ano.max())
if amin == amax:
    a0 = a1 = amin
    st.sidebar.caption(f"Período: {amin} (único ano nos dados)")
else:
    a0, a1 = st.sidebar.slider("Período", amin, amax, (amin, amax))
taxa_on = st.sidebar.toggle("Taxa por 100 mil hab. (quando possível)")
na = a1 - a0 + 1


def filtra(x, sg, tp):
    m = x.ano.between(a0, a1) & x.regiao.isin(regs) & x.sexo.isin(sexos)
    if sg != "Todos":
        m &= x.segmento == sg
    if tp:
        m &= x.tipo.isin(tp)
    return x[m]


def serie(x, dims):
    """Casos e taxa bruta/100 mil por dimensão(ões). Taxa fica vazia quando não há denominador."""
    dims = [dims] if isinstance(dims, str) else list(dims)
    g = x.groupby(dims, observed=True).size().rename("casos").reset_index()
    pop = g.regiao.map(POP) if "regiao" in dims else pd.Series(sum(POP[r] for r in regs), index=g.index)
    if "tipo" in dims:
        g["segmento"] = g.tipo.map(tseg)
        pop = pop * g.segmento.map(SH)
    else:
        pop = pop * SH[seg]
    if "sexo" in dims:
        pop = pop / 2
    if "faixa_etaria" in dims or "mes" in dims:
        pop = pop * np.nan
    g["taxa"] = g.casos / pop / (1 if "ano" in dims else na) * 1e5
    return g


def met(g):
    return ("taxa", "Taxa por 100 mil hab.") if taxa_on and g.taxa.notna().all() else ("casos", "Casos")


st.title("Painel Oncológico Integrado")
st.caption("Câncer adulto e infantil · Painel Oncológico (DATASUS) · RHC-INCA · Mortalidade (SIM) · Regulação (SMSPOA)")
if demo:
    st.info("Dados demonstrativos (sintéticos), só para testar filtros e gráficos. Carregue um CSV real na barra lateral.")

d = filtra(df, seg, tipos)
if d.empty:
    st.warning("Nenhum caso com os filtros atuais.")
    st.stop()

T = st.tabs(["Visão geral", "Incidência", "Estrutura", "Acesso", "Desfecho", "Câncer infantil (ICCC-3)", "Fila e custo", "Projeção"])

# ------------------------------------------------------------------ visão geral
with T[0]:
    kp = [("Casos", f"{len(d):,}".replace(",", ".")), ("Tipos de câncer", d.tipo.nunique()), ("Com tratamento", f"{d.tratado.mean():.0%}"),
          ("Diagnóstico → tratamento", f"{d.dias_dx_trat.mean():.0f} dias"), ("Distância média", f"{d.dist_km.mean():.0f} km"),
          ("Óbitos no seguimento", f"{d.obito.mean():.0%}")]
    for col, (a, b) in zip(st.columns(6), kp):
        col.metric(a, b)
    show(px.treemap(d, path=["segmento", "tipo"], title="Composição dos casos por segmento e tipo"), 450)

# ------------------------------------------------------------------ incidência (P1-P3)
with T[1]:
    st.subheader("Incidência")
    g = serie(d, "tipo")
    c, lab = met(g)
    show(px.bar(g.sort_values(c), x=c, y="tipo", color="segmento", orientation="h", labels={c: lab},
                title=f"Pergunta 1 · {lab} por tipo de câncer"), 460)

    st.markdown("**Pergunta 2 · Evolução no tempo**")
    c1, c2 = st.columns([1, 3])
    res = c1.radio("Resolução", ["Ano", "Mês"], horizontal=True)
    top = d.tipo.value_counts().index[:5].tolist()
    sel = c2.multiselect("Tipos no gráfico", sorted(d.tipo.unique()), default=top) or top
    x = d[d.tipo.isin(sel)]
    if res == "Ano":
        g = serie(x, ["ano", "tipo"])
        c, lab = met(g)
        fig = px.line(g, x="ano", y=c, color="tipo", markers=True, labels={c: lab})
    else:
        g = x.groupby(["ano", "mes", "tipo"]).size().rename("casos").reset_index()
        g["data"] = pd.to_datetime(dict(year=g.ano, month=g.mes, day=1))
        fig = px.line(g, x="data", y="casos", color="tipo", labels={"casos": "Casos"})
    show(fig, 400)

    st.markdown("**Pergunta 3 · Distribuição por idade, sexo e local de moradia**")
    dim = st.selectbox("Distribuir por", ["sexo", "faixa_etaria", "regiao"], format_func=LAB.get)
    a, b = st.columns(2)
    g = serie(d, dim)
    c, lab = met(g)
    with a:
        show(px.bar(g, x=dim, y=c, labels={c: lab, dim: LAB[dim]}, category_orders={"faixa_etaria": FAIXAS}, title=f"{lab} por {LAB[dim].lower()}"))
    with b:
        show(px.density_heatmap(d, x="faixa_etaria", y="tipo", category_orders={"faixa_etaria": FAIXAS},
                                color_continuous_scale="Teal", title="Casos por faixa etária e tipo"))

# ------------------------------------------------------------------ estrutura (P4-P7)
with T[2]:
    st.subheader("Estrutura de atenção")
    if demo_h:
        st.caption("Hospitais sintéticos. Carregue o CSV de hospitais habilitados na barra lateral para usar dados reais.")
    st.caption("UNACON: hospital habilitado para os cânceres mais frequentes. CACON: estrutura mais ampla, com radioterapia própria.")
    s = S[S.regiao.isin(regs)]
    if seg != "Todos":
        s = s[s.segmento == seg]
    if tipos:
        s = s[s.tipo.isin(tipos)]
    h = s.drop_duplicates("hospital")
    if h.empty:
        st.info("Nenhum serviço habilitado para os filtros atuais.")
    else:
        for col, (a, b) in zip(st.columns(4), [("Pergunta 4 · Hospitais habilitados", len(h)),
                                               ("UNACON", int(h.habilitacao.str.startswith("UNACON").sum())),
                                               ("CACON", int(h.habilitacao.str.startswith("CACON").sum())),
                                               ("Serviços por tipo e segmento", len(s))]):
            col.metric(a, b)
        a, b = st.columns(2)
        with a:
            show(px.pie(h, names="esfera", hole=.45, title="Pergunta 5 · Hospitais por esfera de governo"), 400)
        with b:
            g = s.groupby(["tipo", "segmento"]).hospital.nunique().reset_index(name="servicos")
            show(px.bar(g.sort_values("servicos"), x="servicos", y="tipo", color="segmento", orientation="h", barmode="group",
                        labels={"servicos": "Serviços habilitados"}, title="Pergunta 6 · Serviços por tipo e segmento"), 400)
        o = s.groupby("tipo").ocupacao.mean().mul(100).reset_index()
        show(px.bar(o.sort_values("ocupacao"), x="ocupacao", y="tipo", orientation="h", labels={"ocupacao": "Ocupação média (%)"},
                    title="Pergunta 7 · Taxa de ocupação dos serviços por tipo de câncer"), 440)

# ------------------------------------------------------------------ acesso (P8-P13)
with T[3]:
    st.subheader("Acesso ao tratamento")
    t = d[d.tratado]
    g = t.groupby("tipo").dias_dx_trat.mean().round(1).reset_index().sort_values("dias_dx_trat")
    show(px.bar(g, x="dias_dx_trat", y="tipo", orientation="h", labels={"dias_dx_trat": "Dias"},
                title="Pergunta 8 · Tempo médio entre diagnóstico e início do tratamento"), 440)

    cmp_ = st.selectbox("Pergunta 9 · Comparar o tempo até o tratamento por", ["segmento", "atendimento", "regiao", "tipo", "sexo"], format_func=LAB.get)
    show(px.box(t, x=cmp_, y="dias_dx_trat", color=cmp_, points=False, labels={"dias_dx_trat": "Dias", cmp_: LAB[cmp_]}), 400)

    dim = st.selectbox("Pergunta 10 · Diagnosticados × tratados, por", ["tipo", "ano", "regiao"], format_func=LAB.get)
    g = d.groupby(dim, observed=True).agg(diagnosticados=("tratado", "size"), tratados=("tratado", "sum")).reset_index()
    g["pct_tratados"] = (g.tratados / g.diagnosticados * 100).round(1)
    show(px.bar(g, x=dim, y="pct_tratados", hover_data=["diagnosticados", "tratados"], text="pct_tratados",
                labels={"pct_tratados": "% tratados", dim: LAB[dim]}))

    det = st.selectbox("Pergunta 11 · Tratamentos por ano, detalhando por", ["—", "sexo", "faixa_etaria", "regiao"], format_func=lambda k: LAB.get(k, "Sem detalhamento"))
    g = t.groupby(["ano", "tratamento"] + ([] if det == "—" else [det]), observed=True).size().reset_index(name="n")
    show(px.bar(g, x="ano", y="n", color="tratamento", facet_col=None if det == "—" else det, facet_col_wrap=4,
                category_orders={"faixa_etaria": FAIXAS}, labels={"n": "Tratamentos"}), 420)

    st.markdown("**Perguntas 12 e 13 · Distância entre residência e local de tratamento**")
    st.metric("Distância média", f"{t.dist_km.mean():.0f} km")
    dim = st.selectbox("Comparar a distância por", ["segmento", "tipo", "regiao"], format_func=LAB.get)
    g = t.groupby([dim, "tratamento"]).dist_km.mean().round(1).reset_index()
    show(px.bar(g, x=dim, y="dist_km", color="tratamento", barmode="group", labels={"dist_km": "km (média)", dim: LAB[dim]}))

# ------------------------------------------------------------------ desfecho (P14-P19)
with T[4]:
    st.subheader("Desfecho")
    x = d[d.obito == 1]
    if x.empty:
        st.info("Sem óbitos nos filtros atuais.")
    else:
        g = serie(x, "tipo")
        c, lab = met(g)
        show(px.bar(g.sort_values(c), x=c, y="tipo", color="segmento", orientation="h", labels={c: lab.replace("Casos", "Óbitos")},
                    title="Pergunta 14 · Mortalidade por tipo de câncer no período"), 440)
    g = d.groupby(["faixa_etaria", "sexo"], observed=True).obito.mean().mul(100).round(1).reset_index()
    show(px.bar(g, x="faixa_etaria", y="obito", color="sexo", barmode="group", category_orders={"faixa_etaria": FAIXAS},
                labels={"obito": "% de óbitos entre os casos", "faixa_etaria": "Faixa etária"}, title="Pergunta 15 · Óbitos por idade e sexo"))

    st.markdown("**Perguntas 16 e 17 · Resultado do tratamento e associação**")
    g = d.groupby(["tratamento", "desfecho"]).size().reset_index(name="n")
    show(px.bar(g, x="tratamento", y="n", color="desfecho", labels={"n": "%"})
         .update_layout(barmode="stack", barnorm="percent"))
    ct = pd.crosstab(d.tratamento, d.desfecho)
    if min(ct.shape) > 1:
        ex = np.outer(ct.sum(1), ct.sum(0)) / ct.values.sum()
        chi2 = ((ct.values - ex) ** 2 / ex).sum()
        v = np.sqrt(chi2 / (ct.values.sum() * (min(ct.shape) - 1)))
        st.caption(f"Associação tratamento × desfecho: χ² = {chi2:,.1f} · V de Cramér = {v:.3f}. "
                   "Medida descritiva; não ajusta por estadiamento nem por outras variáveis.")

    st.markdown("**Perguntas 18 e 19 · Sobrevida (Kaplan-Meier)**")
    by = st.selectbox("Estratificar por", ["tipo", "sexo", "faixa_etaria", "regiao", "segmento", "atendimento", "estadio"], format_func=LAB.get)
    fig, rows = go.Figure(), []
    for gname in d[by].value_counts().index[:8]:
        sub = d[d[by] == gname]
        if sub.empty:
            continue
        xs, ys = km(sub)
        fig.add_scatter(x=xs, y=ys, mode="lines", name=str(gname), line_shape="hv")
        rows.append({LAB[by]: str(gname), "Casos": len(sub), "Sobrevida mediana (meses)": next((a for a, b in zip(xs, ys) if b <= .5), np.nan)})
    fig.update_layout(xaxis_title="Meses desde o diagnóstico", yaxis_title="Probabilidade de sobrevida", yaxis_range=[0, 1])
    show(fig, 420)
    st.dataframe(pd.DataFrame(rows), hide_index=True)
    st.caption("Mostra os 8 maiores grupos. Medianas vazias: a curva não cruzou 50% no seguimento.")

# ------------------------------------------------------------------ câncer infantil (ICCC-3)
with T[5]:
    st.subheader("Câncer infantil e adolescente (ICCC-3)")
    st.caption("A ICCC-3 classifica por histologia e morfologia (12 grupos principais, 47 subgrupos), diferente da classificação por sítio usada em adultos. "
               "Esta aba ignora o filtro de segmento e de tipo da barra lateral.")
    ped = filtra(df, "Pediátrico", [])
    if ped.empty:
        st.info("Sem casos pediátricos nos filtros atuais.")
    else:
        g = ped.groupby(["tipo", "faixa_etaria"], observed=True).size().reset_index(name="casos")
        show(px.bar(g, x="casos", y="tipo", color="faixa_etaria", orientation="h", category_orders={"faixa_etaria": FAIXAS[:4]},
                    title="Distribuição dos casos por grupo ICCC-3 e faixa etária"), 460)
        top = ped.tipo.value_counts().index[:6].tolist()
        g = ped[ped.tipo.isin(top)].groupby(["ano", "tipo"]).size().reset_index(name="casos")
        show(px.line(g, x="ano", y="casos", color="tipo", markers=True, title="Evolução anual dos 6 grupos mais frequentes"))
        tb = ped.groupby("tipo").agg(casos=("tipo", "size"), tratados=("tratado", "mean"), dias=("dias_dx_trat", "mean"),
                                     km=("dist_km", "mean"), obitos=("obito", "mean"))
        tb[["tratados", "obitos"]] *= 100
        st.dataframe(tb.round(1).reset_index().rename(columns={"tipo": "Grupo ICCC-3", "casos": "Casos", "tratados": "% tratados",
                     "dias": "Dias dx→trat. (média)", "km": "Distância (km)", "obitos": "% óbitos"}), hide_index=True)

# ------------------------------------------------------------------ fila e custo
with T[6]:
    st.subheader("Fila de espera e custo")
    st.warning("Perguntas marcadas como incertas no documento: pode não haver dado público (custo depende de AIH/APAC). "
               "Os gráficos abaixo são espaço reservado e só funcionam com as colunas opcionais do CSV.")
    if d.fila_regulador.notna().any():
        g = d.groupby("regiao")[["fila_regulador", "fila_consulta"]].mean().round(1).reset_index()
        g = g.melt("regiao", var_name="etapa", value_name="dias")
        g["etapa"] = g.etapa.map({"fila_regulador": "APS → visualização pelo regulador", "fila_consulta": "APS → consulta com o prestador"})
        show(px.bar(g, x="regiao", y="dias", color="etapa", barmode="group", labels={"dias": "Dias (média)", "regiao": "Região"},
                    title="Tempo médio de fila de espera"))
    if d.custo_hosp.notna().any():
        a, b = st.columns(2)
        alvo = a.selectbox("Custo médio por estadiamento, para", sorted(d.tipo.unique()),
                           index=sorted(d.tipo.unique()).index("Colo do útero") if "Colo do útero" in d.tipo.unique() else 0)
        g = d[d.tipo == alvo].groupby("estadio")[["custo_amb", "custo_hosp"]].mean().round(0).reset_index().melt("estadio")
        g["variable"] = g.variable.map({"custo_amb": "Ambulatorial", "custo_hosp": "Hospitalar"})
        with a:
            show(px.bar(g, x="estadio", y="value", color="variable", labels={"value": "R$ por paciente", "estadio": "Estádio"}))
        g = d.assign(custo=d.custo_amb + d.custo_hosp).groupby("tratamento").custo.sum().reset_index()
        with b:
            show(px.pie(g, names="tratamento", values="custo", hole=.45, title="Divisão do gasto por tipo de tratamento"))
    with st.expander("Perguntas ainda sem dado estruturado"):
        st.markdown("- Casas de apoio e acolhimento nas cidades de tratamento pediátrico\n"
                    "- Impactos sociais, escolares e na qualidade de vida da criança\n"
                    "- Doenças secundárias do tratamento (provavelmente só em prontuário)")

# ------------------------------------------------------------------ projeção
with T[7]:
    st.subheader("Projeção de casos")
    alvo = st.selectbox("Série", ["Todos os tipos filtrados"] + sorted(d.tipo.unique()))
    hz = st.slider("Anos a projetar", 1, 5, 3)
    hist = (d if alvo.startswith("Todos") else d[d.tipo == alvo]).groupby("ano").size()
    if len(hist) < 3:
        st.info("São necessários pelo menos 3 anos no período para projetar.")
    else:
        co = np.polyfit(hist.index, hist.values, 1)
        sd = (hist.values - np.polyval(co, hist.index)).std(ddof=2)
        fx = np.arange(hist.index.max() + 1, hist.index.max() + hz + 1)
        fy = np.polyval(co, fx)
        fig = go.Figure()
        fig.add_scatter(x=fx.tolist() + fx[::-1].tolist(), y=(fy + 1.96 * sd).tolist() + (fy - 1.96 * sd)[::-1].tolist(),
                        fill="toself", line_width=0, opacity=.2, name="Faixa ~95%")
        fig.add_scatter(x=hist.index, y=hist.values, mode="lines+markers", name="Observado")
        fig.add_scatter(x=fx, y=fy, mode="lines+markers", name="Projeção (tendência linear)", line_dash="dash")
        fig.update_layout(xaxis_title="Ano", yaxis_title="Casos")
        show(fig, 420)
        st.caption("Tendência linear simples, apenas para ilustrar a aba. Para uso analítico, troque por modelo de Poisson ou idade-período-coorte.")

# ------------------------------------------------------------------ rodapé
with st.expander("Esquema do CSV e mapa pergunta → aba"):
    st.markdown("**Colunas obrigatórias** (1 linha por caso): `" + "`, `".join(CORE) + "`  \n"
                "**Opcionais:** `" + "`, `".join(OPC) + "`  \n"
                "Regiões esperadas: " + ", ".join(REG) + ". `segmento` = Adulto ou Pediátrico; `tratado` = verdadeiro/falso; "
                "`obito` = 0/1; `meses` = tempo de seguimento até óbito ou censura. "
                "`tratado` aceita true/false, sim/não, 1/0.  \n"
                "**CSV de hospitais (opcional):** `" + "`, `".join(HOSP_COLS) + "` (`ocupacao` entre 0 e 1).")
    st.markdown("| Aba | Perguntas | Fonte prevista (a confirmar) |\n|---|---|---|\n"
                "| Incidência | 1 a 3 | Painel Oncológico (DATASUS), RHC-INCA |\n"
                "| Estrutura | 4 a 7 | habilitações e serviços (DATASUS) |\n"
                "| Acesso | 8 a 13 | Painel Oncológico, RHC-INCA, SMSPOA |\n"
                "| Desfecho | 14 a 19 | SIM, RHC-INCA |\n"
                "| Câncer infantil | ICCC-3 | RHC-INCA |\n"
                "| Fila e custo | extras | SMSPOA, AIH/APAC |")
