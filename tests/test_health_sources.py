import json
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from health_sources import (DATA_DIR, aggregate_sim_chunk, age_band, file_hash, oncology_payload,
                            parse_oncology_csv, fetch_oncology)


class MortalityTests(unittest.TestCase):
    def test_age_units_and_unknown(self):
        for code in ['101', '201', '311', '400', '404']:
            self.assertEqual(age_band(code), '0–4')
        self.assertEqual(age_band('419'), '15–19')
        self.assertEqual(age_band('420'), '20–39')
        self.assertEqual(age_band('500'), '80+')
        for code in ['', '999', '099']:
            self.assertEqual(age_band(code), 'Ignorada')

    def test_selects_malignant_nonfetal_deaths_and_preserves_unknown(self):
        x = pd.DataFrame({
            'TIPOBITO': ['2', '2', '2', '1', '2', '2'],
            'DTOBITO': ['01012025'] * 6, 'IDADE': ['419', '500', '999', '400', '450', '450'],
            'SEXO': ['1', '2', '0', '1', '1', '1'],
            'CODMUNRES': ['355030', '431490', '000000', '355030', '355030', '355030'],
            'CAUSABAS': ['C349', 'C97', 'C509', 'C50', 'D00', 'C98'],
        })
        out = aggregate_sim_chunk(x, 2025)
        self.assertEqual(out.obitos.sum(), 3)
        self.assertEqual(set(out.cid3), {'C34', 'C50', 'C97'})
        self.assertEqual(set(out.uf), {'SP', 'RS', 'Ignorado/exterior'})
        self.assertIn('Ignorada', set(out.faixa_etaria))
        with self.assertRaises(ValueError):
            aggregate_sim_chunk(x, 2026)

    def test_published_aggregates_reconcile_with_metadata(self):
        meta = json.loads((DATA_DIR / 'mortalidade_sim.json').read_text())
        self.assertEqual(file_hash(DATA_DIR / 'mortalidade_sim.csv.gz'), meta['sha256_agregado'])
        frame = pd.read_csv(DATA_DIR / 'mortalidade_sim.csv.gz')
        self.assertTrue((frame.obitos > 0).all())
        self.assertEqual(len(frame), len(frame.drop_duplicates(subset=list(frame.columns[:-1]))))
        for year in meta['anos']:
            subset = frame[frame.ano == year['ano']]
            self.assertEqual(subset.obitos.sum(), year['obitos_cancer'])
            self.assertEqual(subset.mes.max(), year['ultimo_mes_com_registro'])
        self.assertEqual(frame[frame.ano == 2025].mes.max(), 9)
        self.assertEqual(frame[frame.ano == 2026].mes.max(), 8)


class TreatmentTests(unittest.TestCase):
    def test_adult_query_selects_only_age_groups_from_twenty(self):
        form = '''<select name="PAno do diagnóstico"><option value="2025|2025|4"></select>
          <select name="Linha"><option value="UF da residência|x"></select>
          <select name="Coluna"><option value="Tempo Tratamento|x"></select>
          <select name="XDiagnóstico"><option value="Neoplasias Malignas|x"></select>
          <select name="XFaixa etária"><option value="TODAS_AS_CATEGORIAS__">
          <option value="0 a 19 anos|000-019|3">'''
        for age in range(20, 85, 5):
            form += f'<option value="{age} anos|{age}|3">'
        form += '</select>'
        query = oncology_payload(form, 2025, adult=True)
        self.assertEqual(len(query['XFaixa etária']), 13)
        self.assertTrue(all(int(value.split()[0]) >= 20 for value in query['XFaixa etária']))
        self.assertEqual(query['PAno do diagnóstico'], '2025|2025|4')
        with self.assertRaises(ValueError):
            oncology_payload(form, 2025, pediatric=True, adult=True)

    def test_response_from_wrong_year_is_rejected_before_csv_download(self):
        session = Mock()
        session.post.return_value.content = b'<b>Ano do diagn\xf3stico:</b> 2026<p>'
        with patch('health_sources.oncology_payload', return_value={}):
            with self.assertRaisesRegex(ValueError, 'outro ano'):
                fetch_oncology('', 2025, False, '/tmp', session=session)
        session.get.assert_not_called()

    def test_buckets_must_reconcile_and_missing_treatment_is_separate(self):
        text = ('"UF da residência";"Até 30 dias";"31 - 60 dias";"Mais de 60";"Sem informação de tratamento";" Total"\n'
                '"35 São Paulo";"10";"5";"5";"80";"100"\n'
                '"Total";"10";"5";"5";"80";"100"\n')
        rows, total = parse_oncology_csv(text, 2025, 'Todas as idades')
        self.assertEqual(rows[0]['uf'], 'SP')
        informed = total['ate_30'] + total['de_31_a_60'] + total['mais_60']
        self.assertEqual((total['ate_30'] + total['de_31_a_60']) / informed, .75)
        self.assertEqual(total['sem_informacao'], 80)
        with self.assertRaises(ValueError):
            parse_oncology_csv(text.replace(';"100"', ';"101"', 1), 2025, 'Todas as idades')
        with self.assertRaises(ValueError):
            parse_oncology_csv(text.replace('"10"', '"**"'), 2025, 'Todas as idades')

    def test_snapshot_totals_and_pediatric_subset(self):
        meta = json.loads((DATA_DIR / 'acesso_oncologia.json').read_text())
        rows = pd.DataFrame(meta['dados'])
        for query in meta['consultas']:
            x = rows[(rows.ano == query['ano']) & (rows.segmento == query['segmento'])]
            for column, total in query['total_publicado'].items():
                self.assertEqual(x[column].sum(), total)
        for year in rows.ano.unique():
            x = rows[rows.ano == year]
            all_ages = x[x.segmento == 'Todas as idades'].set_index('uf').casos
            ped = x[x.segmento == '0–19 anos'].set_index('uf').casos
            self.assertTrue((ped.reindex(all_ages.index, fill_value=0) <= all_ages).all())
            adult = x[x.segmento == '20 anos ou mais'].set_index('uf').casos
            if not adult.empty:
                known_ages = adult.reindex(all_ages.index, fill_value=0) + ped.reindex(all_ages.index, fill_value=0)
                self.assertTrue((known_ages <= all_ages).all())


class HospitalTests(unittest.TestCase):
    def test_identifiers_and_coverage(self):
        metadata = json.loads((DATA_DIR / 'hospitais.json').read_text())
        x = pd.DataFrame(metadata['hospitais'])
        self.assertEqual(len(x), 383)
        self.assertEqual(x.cnes.nunique(), len(x))
        self.assertTrue(x.cnes.str.fullmatch(r'\d{7}').all())
        self.assertIn('0009601', set(x.cnes))
        self.assertEqual(x.uf.nunique(), 27)
        self.assertTrue(x.municipio.str.len().gt(0).all())
        self.assertEqual(set(x.categoria), {'UNACON', 'CACON', 'Unidade de complexo hospitalar'})
        self.assertTrue(x[x.pediatria].habilitacao.str.contains('pediátrica', case=False).all())


if __name__ == '__main__':
    unittest.main()
