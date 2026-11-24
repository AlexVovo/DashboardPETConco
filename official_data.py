"""Importação verificável das tabelas públicas de estimativa do INCA."""
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SOURCE_URL = 'https://www.gov.br/inca/pt-br/assuntos/cancer/numeros/estimativa/estado-capital/brasil'
SNAPSHOT = Path(__file__).resolve().parent / 'data' / 'inca_2026.json'
REGIONS = {
    'Norte': ['Acre', 'Amapá', 'Amazonas', 'Pará', 'Rondônia', 'Roraima', 'Tocantins'],
    'Nordeste': ['Alagoas', 'Bahia', 'Ceará', 'Maranhão', 'Paraíba', 'Pernambuco', 'Piauí', 'Rio Grande do Norte', 'Sergipe'],
    'Centro-Oeste': ['Distrito Federal', 'Goiás', 'Mato Grosso', 'Mato Grosso do Sul'],
    'Sudeste': ['Espírito Santo', 'Minas Gerais', 'Rio de Janeiro', 'São Paulo'],
    'Sul': ['Paraná', 'Rio Grande do Sul', 'Santa Catarina'],
}
STATE_REGION = {state: region for region, states in REGIONS.items() for state in states}
TOTAL = 'Todas as Neoplasias'
WITHOUT_SKIN = 'Todas as neoplasias, exceto Pele não melanoma'


class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tables = []
        self.depth = 0
        self.table = self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            if not self.depth:
                self.table = []
            self.depth += 1
        if self.depth == 1:
            if tag == 'tr':
                self.row = []
            elif tag in ('td', 'th'):
                self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if self.depth == 1:
            if tag in ('td', 'th') and self.cell is not None:
                self.row.append(' '.join(''.join(self.cell).split()))
                self.cell = None
            elif tag == 'tr' and self.row is not None:
                self.table.append(self.row)
                self.row = None
            elif tag == 'table':
                self.tables.append(self.table)
        if tag == 'table':
            self.depth -= 1


def number(value):
    if value in ('-', '**', ''):
        return None
    return float(value.replace('.', '').replace(',', '.'))


def parse_source(html):
    if not re.search(r'Estimativas para o ano de\s*2026', html):
        raise ValueError('A edição publicada mudou ou não foi reconhecida; revisar o importador.')
    parser = TableParser()
    parser.feed(html)
    if not parser.tables:
        raise ValueError('Nenhuma tabela oficial encontrada na página.')
    national = []
    kind = None
    for row in parser.tables[0]:
        if len(row) == 5 and row[1] == 'Homens':
            kind, row = row[0], row[1:]
        if len(row) == 4 and row[0] in ('Homens', 'Mulheres', 'Total') and kind:
            national.append(dict(tipo=kind, sexo=row[0], casos=number(row[1]),
                                 taxa_bruta=number(row[2]), taxa_ajustada=number(row[3])))
    states = {}
    for table in parser.tables:
        if not table or not table[0] or table[0][0] != 'Estados':
            continue
        headers = table[0][1:]
        for row in table[1:]:
            if not row or row[0] not in STATE_REGION:
                continue
            if len(row) != len(headers) + 1:
                raise ValueError('Estrutura da tabela estadual inesperada.')
            for header, value in zip(headers, row[1:]):
                key = (row[0], header)
                record = dict(estado=row[0], regiao=STATE_REGION[row[0]], tipo=header,
                              casos=number(value), valor_publicado=value)
                if key in states and states[key] != record:
                    raise ValueError('Totais estaduais divergentes entre tabelas.')
                states[key] = record
    totals = [r for r in national if r['tipo'] == TOTAL]
    if len(national) != 72 or len(totals) != 3 or not all(r['casos'] and r['casos'] > 0 for r in totals):
        raise ValueError('Tabela nacional incompleta ou inválida.')
    if len(states) != 27 * 24:
        raise ValueError('Esperadas 27 UFs e 24 categorias, incluindo totais.')
    total = next(r['casos'] for r in totals if r['sexo'] == 'Total')
    state_total = sum(r['casos'] for r in states.values() if r['tipo'] == 'Todas as neoplasias malignas')
    if state_total != total:
        raise ValueError('Total das UFs difere do total nacional.')
    updated = re.search(r'Atualizado em</span>\s*<span[^>]*>([^<]+)', html)
    return dict(fonte=SOURCE_URL, edicao='Estimativa 2026–2028', ano_referencia=2026,
                natureza='Estimativas anuais de incidência; não são registros individuais de pacientes.',
                atualizado_na_fonte=updated.group(1) if updated else None,
                consultado_em=datetime.now(ZoneInfo('America/Sao_Paulo')).isoformat(),
                sha256_html=sha256(html.encode()).hexdigest(), nacional=national,
                estados=list(states.values()))


def fetch_source():
    request = Request(SOURCE_URL, headers={'User-Agent': 'PainelOncologico/1.0'})
    with urlopen(request, timeout=15) as response:
        html = response.read(5_000_000).decode('utf-8')
    return parse_source(html)


def read_snapshot():
    return json.loads(SNAPSHOT.read_text(encoding='utf-8'))
