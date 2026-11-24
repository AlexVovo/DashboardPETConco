"""Gera snapshots agregados. Ex.: python scripts/update_health_data.py --source all --raw-dir /tmp/petconco"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
import requests
from health_sources import (DATA_DIR, HOSPITAL_URL, HOSPITAL_PAGE, ONCOLOGY_FORM, SIM_PAGE,
                            ONCOLOGY_QUERY, aggregate_sim, collection_time, download, fetch_oncology, file_hash, now, parse_hospitals, write_json)


def update_hospitals(raw_dir, reuse):
    path = raw_dir / 'hosp_file.bin'
    if not reuse or not path.exists():
        download(HOSPITAL_URL, path)
    records = parse_hospitals(path)
    download_meta = json.loads(Path(str(path) + '.meta.json').read_text()) if Path(str(path) + '.meta.json').exists() else {}
    write_json(DATA_DIR / 'hospitais.json', dict(fonte=HOSPITAL_PAGE, arquivo=HOSPITAL_URL,
        referencia='Planilha HABILITAÇÃO 2026', consultado_em=collection_time(path),
        last_modified_http=download_meta.get('last_modified_http'), sha256_xls=file_hash(path),
        cobertura='Aba HABILITAÇÃO 2026: UNACON, CACON e unidades de complexo hospitalar. Não inclui a aba de serviços isolados de radioterapia.',
        hospitais=records))
    print('Hospitais:', len(records), flush=True)


def update_oncology(raw_dir, years):
    session = requests.Session()
    try:
        response = session.get(ONCOLOGY_FORM, timeout=(5, 60))
    except (requests.ConnectionError, requests.Timeout):
        # Endpoint legado de dados públicos: há períodos em que apenas HTTP responde.
        response = session.get(ONCOLOGY_FORM.replace('https:', 'http:'), timeout=(15, 60))
    response.raise_for_status()
    query_url = ONCOLOGY_QUERY.replace('https:', 'http:') if response.url.startswith('http:') else ONCOLOGY_QUERY
    form = response.content.decode('iso-8859-1')
    jobs = [(year, ped, adult) for year in years for ped, adult in [(False, False), (True, False), (False, True)]]
    results = []
    for year, pediatric, adult in jobs:
        result = fetch_oncology(form, year, pediatric, raw_dir, session=session, query_url=query_url, adult=adult)
        results.append(result)
        print('Tratamento:', year, '0–19' if pediatric else '20+' if adult else 'todas as idades', flush=True)
    records = [r for rows, _ in results for r in rows]
    metadata = [meta for _, meta in results]
    write_json(DATA_DIR / 'acesso_oncologia.json', dict(fonte=ONCOLOGY_FORM, consultado_em=now(),
        cobertura='Grupo Neoplasias Malignas (Lei nº 12.732/12), ambos os sexos, UF de residência, ano do diagnóstico. Recortes de 0–19 anos e 20 anos ou mais consultados diretamente na fonte; não somar recortes ao total de todas as idades.',
        consultas=metadata, dados=records))
    print('Acesso:', len(records), 'linhas', flush=True)


def update_mortality(raw_dir, years, reuse):
    response = requests.get(SIM_PAGE, timeout=(15, 60)); response.raise_for_status()
    import re
    page = json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', response.text, re.S).group(1))
    resources = page['props']['pageProps']['resources']
    frames, metadata = [], []
    for year in years:
        matches = [r for r in resources if r['format'] == 'CSV' and str(year) in r['name']]
        if len(matches) != 1:
            raise ValueError(f'Recurso CSV do SIM {year} ausente/ambíguo.')
        resource = matches[0]
        path = raw_dir / f'sim{year}.zip'
        if not reuse or not path.exists():
            download(resource['url'], path)
        frame, meta = aggregate_sim(path, year)
        meta.update(nome_recurso=resource['name'], url=resource['url'],
                    atualizado_no_catalogo=resource.get('metadata_modified'),
                    situacao='Prévia parcial' if 'prévia' in resource['name'].lower() else 'Preliminar' if 'preliminar' in resource['name'].lower() else 'Sem indicação de preliminar no catálogo')
        frames.append(frame); metadata.append(meta)
        print('SIM', year, meta['obitos_cancer'], flush=True)
    result = pd.concat(frames, ignore_index=True)
    target = DATA_DIR / 'mortalidade_sim.csv.gz'
    temp = target.with_name('mortalidade_sim.tmp.gz')
    result.to_csv(temp, index=False, compression={'method': 'gzip', 'mtime': 0})
    temp.replace(target)
    write_json(DATA_DIR / 'mortalidade_sim.json', dict(fonte=SIM_PAGE, consultado_em=max(m['consultado_em'] for m in metadata),
        processado_em=now(),
        criterio='Óbitos não fetais (TIPOBITO=2), causa básica CID-10 C00–C97, UF de residência. Não há vínculo com casos ou tratamentos do painel.',
        arquivo_agregado=target.name, sha256_agregado=file_hash(target), anos=metadata))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', choices=['all', 'hospitals', 'oncology', 'mortality'], default='all')
    parser.add_argument('--raw-dir', type=Path, default=Path('/tmp/petconco-sources'))
    parser.add_argument('--years', type=int, nargs='+', default=[2024, 2025, 2026])
    parser.add_argument('--reuse-downloads', action='store_true', help='Reutiliza arquivos brutos já baixados no diretório informado.')
    args = parser.parse_args(); args.raw_dir.mkdir(parents=True, exist_ok=True)
    if args.source in ('all', 'hospitals'): update_hospitals(args.raw_dir, args.reuse_downloads)
    if args.source in ('all', 'oncology'): update_oncology(args.raw_dir, args.years)
    if args.source in ('all', 'mortality'): update_mortality(args.raw_dir, args.years, args.reuse_downloads)
