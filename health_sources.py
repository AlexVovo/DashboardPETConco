"""Importadores de dados públicos de oncologia. Persistem apenas agregados do SIM."""
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
from io import StringIO
import json
from pathlib import Path
import re
from urllib.parse import urlencode, urljoin
import zipfile
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from official_data import STATE_REGION

DATA_DIR = Path(__file__).resolve().parent / 'data'
HOSPITAL_URL = 'https://www.gov.br/saude/pt-br/composicao/saes/cgcan/arquivos/estabelecimentos-habilitados-em-oncologia'
HOSPITAL_PAGE = 'https://www.gov.br/saude/pt-br/composicao/saes/cgcan/hospitais-habilitados'
ONCOLOGY_FORM = 'https://tabnet.datasus.gov.br/cgi/dhdat.exe?PAINEL_ONCO/PAINEL_ONCOLOGIABR.def'
ONCOLOGY_QUERY = 'https://tabnet.datasus.gov.br/cgi/webtabx.exe?PAINEL_ONCO/PAINEL_ONCOLOGIABR.def'
SIM_PAGE = 'https://dadosabertos.saude.gov.br/dataset/sim'
UF_CODES = dict(zip(
    ['11','12','13','14','15','16','17','21','22','23','24','25','26','27','28','29','31','32','33','35','41','42','43','50','51','52','53'],
    ['RO','AC','AM','RR','PA','AP','TO','MA','PI','CE','RN','PB','PE','AL','SE','BA','MG','ES','RJ','SP','PR','SC','RS','MS','MT','GO','DF']))
UF_NAMES = dict(zip(UF_CODES.values(),
    ['Rondônia','Acre','Amazonas','Roraima','Pará','Amapá','Tocantins','Maranhão','Piauí','Ceará','Rio Grande do Norte','Paraíba','Pernambuco','Alagoas','Sergipe','Bahia','Minas Gerais','Espírito Santo','Rio de Janeiro','São Paulo','Paraná','Santa Catarina','Rio Grande do Sul','Mato Grosso do Sul','Mato Grosso','Goiás','Distrito Federal']))
UNKNOWN = 'Ignorado/exterior'
TIME_COLUMNS = {'Até 30 dias': 'ate_30', '31 - 60 dias': 'de_31_a_60', 'Mais de 60': 'mais_60',
                'Sem informação de tratamento': 'sem_informacao', 'Total': 'casos'}


def now():
    return datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat()


def file_hash(path):
    digest = sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def collection_time(path):
    metadata = Path(str(path) + '.meta.json')
    if metadata.exists():
        return json.loads(metadata.read_text())['consultado_em']
    # Reprocessamento de download anterior: não apresenta a execução como nova coleta.
    return datetime.fromtimestamp(Path(path).stat().st_mtime, ZoneInfo('America/Sao_Paulo')).isoformat()


def write_json(path, data):
    path = Path(path)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def download(url, path):
    path = Path(path)
    temp = path.with_suffix('.download')
    with requests.get(url, timeout=(15, 90), stream=True) as response:
        response.raise_for_status()
        with temp.open('wb') as stream:
            for chunk in response.iter_content(1024 * 1024):
                stream.write(chunk)
        modified = response.headers.get('Last-Modified')
    temp.replace(path)
    write_json(str(path) + '.meta.json', {'url': url, 'consultado_em': now(), 'last_modified_http': modified})


def parse_hospitals(path):
    import xlrd
    book = xlrd.open_workbook(str(path), formatting_info=True)
    sheet = next((s for s in book.sheets() if s.name == 'HABILITAÇÃO 2026'), None)
    if sheet is None:
        raise ValueError('Edição/aba da planilha de hospitais mudou; revisar importador.')
    rows = [sheet.row_values(i) for i in range(sheet.nrows)]
    source_count = sum(row[3] for row in rows[2:] if row[5] and isinstance(row[3], (int, float)))
    if [str(x).strip() for x in rows[1]][:2] != ['UF', 'MUNICÍPIO']:
        raise ValueError('Cabeçalho de hospitais não reconhecido.')
    # Preenche somente células efetivamente mescladas na fonte, sem inventar localidade.
    for r0, r1, c0, c1 in sheet.merged_cells:
        for r in range(r0, r1):
            for c in range(c0, c1):
                rows[r][c] = rows[r0][c0]
    records = []
    for row in rows[2:]:
        if not row[5] or not row[4]:
            continue
        uf = str(row[0]).strip()
        if uf not in UF_NAMES:
            raise ValueError(f'UF inválida na planilha: {uf}')
        raw_code = row[5]
        cnes = str(int(raw_code)) if isinstance(raw_code, (int, float)) else str(raw_code).strip()
        cnes = cnes.zfill(7)
        if not re.fullmatch(r'\d{7}', cnes):
            raise ValueError('CNES inválido.')
        qualification = str(row[7]).strip()
        category = 'UNACON' if qualification.startswith('UNACON') else 'CACON' if qualification.startswith('CACON') else 'Unidade de complexo hospitalar'
        records.append(dict(cnes=cnes, hospital=str(row[4]).strip(), uf=uf, estado=UF_NAMES[uf],
                            regiao=STATE_REGION[UF_NAMES[uf]], municipio=str(row[1]).strip(),
                            habilitacao=qualification, codigo=str(row[6]).strip(), categoria=category,
                            pediatria='pediátrica' in qualification.lower()))
    if not records or len({r['cnes'] for r in records}) != len(records):
        raise ValueError('Lista vazia ou CNES duplicados; revisar fonte.')
    if {r['uf'] for r in records} != set(UF_NAMES):
        raise ValueError('A relação de hospitais não cobre as 27 UFs.')
    published_total = next((int(row[3]) for row in rows[2:] if not row[4] and isinstance(row[3], (int, float)) and row[3] > 100), None)
    if published_total is None or source_count != published_total:
        raise ValueError('Contagem de habilitações diverge do total publicado na planilha.')
    return records


class OncologyForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.options = {}
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'select':
            self.current = attrs.get('name')
            self.options[self.current] = []
        elif tag == 'option' and self.current:
            self.options[self.current].append(attrs)

    def handle_endtag(self, tag):
        if tag == 'select':
            self.current = None


def oncology_payload(form_html, year, pediatric=False):
    form = OncologyForm()
    form.feed(form_html)
    options = form.options
    if f'{year}|{year}|4' not in [x['value'] for x in options['PAno do diagnóstico']]:
        raise ValueError(f'Ano {year} não disponível no PAINEL-Oncologia.')
    payload = {key: next((o.get('value', '') for o in values if 'selected' in o), values[0].get('value', '') if values else '')
               for key, values in options.items() if not key.startswith('listahidden')}
    payload.update(Linha=next(o['value'] for o in options['Linha'] if o['value'].startswith('UF da residência|')),
                   Coluna=next(o['value'] for o in options['Coluna'] if o['value'].startswith('Tempo Tratamento|')),
                   nomedef='PAINEL_ONCO/PAINEL_ONCOLOGIABR.def', grafico='')
    payload['PAno do diagnóstico'] = f'{year}|{year}|4'
    payload['XDiagnóstico'] = next(o['value'] for o in options['XDiagnóstico'] if o['value'].startswith('Neoplasias Malignas'))
    if pediatric:
        payload['XFaixa etária'] = next(o['value'] for o in options['XFaixa etária'] if o['value'].startswith('0 a 19 anos|'))
    return payload


def parse_oncology_csv(text, year, segment):
    table = pd.read_csv(StringIO(text.strip()), sep=';', dtype=str)
    table.columns = [c.strip() for c in table.columns]
    if list(table.columns) != ['UF da residência', *TIME_COLUMNS]:
        raise ValueError('Colunas de tempo de tratamento mudaram; revisar importador.')
    records, published_total = [], None
    for row in table.to_dict('records'):
        counts = {}
        for original, target in TIME_COLUMNS.items():
            value = str(row[original]).strip()
            # Nesta tabulação '-' indica frequência nula. Outros símbolos exigem revisão.
            if value == '-':
                value = '0'
            if not re.fullmatch(r'\d+', value):
                raise ValueError(f'Frequência inválida na tabulação: {value}')
            counts[target] = int(value)
        if sum(counts[k] for k in ('ate_30', 'de_31_a_60', 'mais_60', 'sem_informacao')) != counts['casos']:
            raise ValueError('Faixas de tratamento não conciliam com o total.')
        label = row['UF da residência'].strip()
        if label == 'Total':
            published_total = counts
            continue
        code = label.split()[0]
        uf = UF_CODES.get(code, UNKNOWN)
        if code not in UF_CODES and code != '00':
            raise ValueError('UF inesperada na tabulação.')
        records.append(dict(ano=year, segmento=segment, uf=uf, **counts))
    if not records or published_total is None:
        raise ValueError('Resultado vazio ou sem total nacional.')
    if len({r['uf'] for r in records}) != len(records):
        raise ValueError('UF duplicada no resultado.')
    for key, value in published_total.items():
        if sum(r[key] for r in records) != value:
            raise ValueError('Soma das UFs diverge do total nacional do tratamento.')
    return records, published_total


def fetch_oncology(form_html, year, pediatric, raw_dir, session=None, query_url=ONCOLOGY_QUERY):
    session = session or requests.Session()
    payload = oncology_payload(form_html, year, pediatric)
    response = session.post(query_url, data=urlencode(payload, encoding='iso-8859-1').encode(),
                             headers={'Content-Type': 'application/x-www-form-urlencoded'}, timeout=(15, 90))
    response.raise_for_status()
    html = response.content.decode('iso-8859-1')
    if not re.search(rf'Ano do diagnóstico:</b>\s*{year}\s*<', html):
        raise ValueError('Resposta retornou outro ano; recusando dados.')
    if pediatric and '0 a 19 anos' not in html:
        raise ValueError('Filtro pediátrico não foi confirmado pela fonte.')
    link = re.search(r'HREF=([^>]+\.csv)', html)
    updated = re.search(r'Data de atualização dos dados:</strong>\s*([\d/]+)', html)
    if not link or not updated:
        raise ValueError('CSV/data de referência ausente na resposta.')
    csv_response = session.get(urljoin(query_url, link.group(1)), timeout=(15, 60))
    csv_response.raise_for_status()
    text = csv_response.content.decode('iso-8859-1')
    segment = '0–19 anos' if pediatric else 'Todas as idades'
    records, total = parse_oncology_csv(text, year, segment)
    name = f'oncologia_{year}_{"ped" if pediatric else "todos"}'
    Path(raw_dir, name + '.html').write_text(html, encoding='utf-8')
    Path(raw_dir, name + '.csv').write_text(text, encoding='utf-8')
    return records, dict(ano=year, segmento=segment, atualizado_na_fonte=updated.group(1),
                         total_publicado=total, parametros=payload, sha256_csv=sha256(csv_response.content).hexdigest(),
                         consultado_em=now(), consulta_url=query_url)


def age_band(value):
    if not re.fullmatch(r'\d{3}', str(value)):
        return 'Ignorada'
    unit, amount = value[0], int(value[1:])
    if unit in ('1', '2', '3'):
        age = 0
    elif unit == '4':
        age = amount
    elif unit == '5':
        age = 100 + amount
    else:
        return 'Ignorada'
    for upper, label in [(5, '0–4'), (10, '5–9'), (15, '10–14'), (20, '15–19'), (40, '20–39'), (60, '40–59'), (80, '60–79')]:
        if age < upper:
            return label
    return '80+'


def aggregate_sim_chunk(chunk, year):
    cause = chunk.CAUSABAS.str.strip().str.upper()
    mask = cause.str.fullmatch(r'C(?:[0-8]\d|9[0-7])\d?', na=False) & chunk.TIPOBITO.eq('2')
    x = chunk.loc[mask].copy()
    dates = pd.to_datetime(x.DTOBITO, format='%d%m%Y', errors='coerce')
    invalid = int((dates.isna() | dates.dt.year.ne(year)).sum())
    if invalid:
        raise ValueError(f'SIM {year}: {invalid} óbitos por câncer com data inválida/fora do ano.')
    x['ano'] = year
    x['mes'] = dates.dt.month
    x['uf'] = x.CODMUNRES.str[:2].map(UF_CODES).fillna(UNKNOWN)
    x['sexo'] = x.SEXO.map({'1': 'Masculino', '2': 'Feminino'}).fillna('Ignorado')
    x['faixa_etaria'] = x.IDADE.map(age_band)
    x['cid3'] = cause.loc[mask].str[:3]
    dims = ['ano', 'mes', 'uf', 'sexo', 'faixa_etaria', 'cid3']
    return x.groupby(dims).size().rename('obitos').reset_index()


def aggregate_sim(path, year):
    cols = ['TIPOBITO', 'DTOBITO', 'IDADE', 'SEXO', 'CODMUNRES', 'CAUSABAS']
    frames, total_rows = [], 0
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith('.csv')]
        if len(names) != 1:
            raise ValueError('Esperado um CSV por arquivo SIM.')
        with archive.open(names[0]) as stream:
            for chunk in pd.read_csv(stream, sep=';', encoding='utf-8-sig', dtype=str, usecols=cols,
                                     keep_default_na=False, chunksize=100000):
                total_rows += len(chunk)
                frames.append(aggregate_sim_chunk(chunk, year))
    dims = ['ano', 'mes', 'uf', 'sexo', 'faixa_etaria', 'cid3']
    result = pd.concat(frames).groupby(dims, as_index=False).obitos.sum()
    if result.empty or set(result.uf) - {UNKNOWN} != set(UF_NAMES):
        raise ValueError('SIM sem óbitos por câncer ou sem cobertura das 27 UFs.')
    return result, dict(ano=year, registros_lidos=total_rows, obitos_cancer=int(result.obitos.sum()),
                        ultimo_mes_com_registro=int(result.mes.max()), sha256_zip=file_hash(path),
                        consultado_em=collection_time(path), processado_em=now())
