import unittest
from pathlib import Path
from unittest.mock import patch

from official_data import STATE_REGION, TOTAL, WITHOUT_SKIN, number, parse_source, read_snapshot


class OfficialDataTests(unittest.TestCase):
    def test_snapshot_matches_published_national_totals(self):
        data = read_snapshot()
        total = {(r['tipo'], r['sexo']): r for r in data['nacional']}
        self.assertEqual(total[TOTAL, 'Total']['casos'], 781050)
        self.assertEqual(total[WITHOUT_SKIN, 'Total']['casos'], 517770)
        self.assertEqual(total['Mama Feminina', 'Mulheres']['casos'], 78610)
        self.assertEqual(total['Mama Feminina', 'Mulheres']['taxa_bruta'], 71.57)
        self.assertIsNone(total['Mama Feminina', 'Homens']['casos'])
        self.assertEqual(total[TOTAL, 'Homens']['casos'] + total[TOTAL, 'Mulheres']['casos'],
                         total[TOTAL, 'Total']['casos'])

    def test_states_cover_country_and_reconcile_total(self):
        rows = read_snapshot()['estados']
        self.assertEqual({r['estado'] for r in rows}, set(STATE_REGION))
        self.assertEqual(len({(r['estado'], r['tipo']) for r in rows}), len(rows))
        totals = [r for r in rows if r['tipo'] == 'Todas as neoplasias malignas']
        self.assertEqual(len(totals), 27)
        self.assertEqual(sum(r['casos'] for r in totals), 781050)
        suppressed = [r for r in rows if r['valor_publicado'] == '**']
        self.assertTrue(suppressed)
        self.assertTrue(all(r['casos'] is None for r in suppressed))

    def test_unknown_values_are_not_zero(self):
        self.assertIsNone(number('**'))
        self.assertIsNone(number('-'))
        self.assertEqual(number('0'), 0)
        self.assertEqual(number('78.610'), 78610)
        self.assertEqual(number('71,57'), 71.57)

    def test_changed_edition_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_source('<h2>Estimativas para o ano de 2029</h2>')


class OfficialDashboardTests(unittest.TestCase):
    def run_app(self, failure=False):
        from official_dashboard import load_official
        from streamlit.testing.v1 import AppTest
        load_official.clear()
        if failure:
            mock = patch('official_dashboard.fetch_source', side_effect=OSError('fonte indisponível'))
        else:
            mock = patch('official_dashboard.fetch_source', return_value=read_snapshot())
        with mock:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py'), default_timeout=20).run()
        self.assertFalse(app.exception)
        return app

    def test_default_is_official_and_filters_work(self):
        app = self.run_app()
        self.assertEqual(app.sidebar.selectbox[0].value, 'INCA — estimativas oficiais')
        self.assertEqual(app.metric[0].value, '781.050')
        self.assertEqual([tab.label for tab in app.tabs], [
            'Visão geral', 'Incidência', 'Estrutura', 'Acesso', 'Desfecho',
            'Câncer infantil (ICCC-3)', 'Fila e custo', 'Projeção',
        ])
        self.assertEqual(len(app.tabs[0].metric), 6)
        self.assertEqual(app.tabs[0].metric[2].value, '—')
        sex = next(x for x in app.selectbox if x.label == 'Sexo — dados nacionais')
        sex.select('Mulheres').run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '389.090')
        regions = next(x for x in app.multiselect if x.label == 'Regiões')
        regions.set_value([]).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Selecione pelo menos' in x.value for x in app.info))
        app.sidebar.selectbox[0].select('CSV de casos').run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)

    def test_offline_snapshot_is_explicit(self):
        app = self.run_app(failure=True)
        self.assertEqual(app.metric[0].value, '781.050')
        self.assertTrue(any('cópia verificada' in x.value for x in app.warning))
        self.assertTrue(any('Consulta:' in x.value for x in app.caption))


if __name__ == '__main__':
    unittest.main()
