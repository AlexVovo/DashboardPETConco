"""Execute: python scripts/update_official_data.py (requer acesso à internet)."""
from pathlib import Path
import sys
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from official_data import SNAPSHOT, fetch_source

if __name__ == '__main__':
    data = fetch_source()
    temporary = SNAPSHOT.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(SNAPSHOT)
    print(f"Atualizado: {SNAPSHOT} ({data['consultado_em']})")
