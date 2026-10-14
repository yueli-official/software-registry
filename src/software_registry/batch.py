"""Independent official discovery outcomes for a complete catalog."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from .planning import create_plan
from .reader import Reader


class BatchReader(Reader):
    def __init__(self):
        super().__init__()
        self.locks = {}
        self.guard = threading.Lock()

    def cached(self, key, read):
        with self.guard:
            lock = self.locks.setdefault(key, threading.Lock())
        with lock:
            return read()

    def github(self, endpoint):
        return self.cached('github:' + endpoint, lambda: super(BatchReader, self).github(endpoint))

    def get(self, url):
        return self.cached(url, lambda: super(BatchReader, self).get(url))


def discover_catalog(catalog, output, workers=4, reader=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    reader = reader or BatchReader()

    def discover(item):
        identity, manifest = item
        if manifest['kind'] == 'reference':
            return {'softwareId': identity, 'status': 'reference'}
        try:
            plan = create_plan(manifest, reader)
            relative = 'plans/' + identity + '.json'
            target = output / relative
            target.parent.mkdir(exist_ok=True)
            target.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            return {'softwareId': identity, 'status': 'discovered', 'version': plan['version'],
                    'planDigest': plan['planDigest'], 'path': relative}
        except Exception as error:
            # Diagnostics contain categories only; no transient URLs or credentials.
            return {'softwareId': identity, 'status': 'failed', 'error': getattr(error, 'code', type(error).__name__)}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(discover, sorted(catalog.items())))
    result = {'schemaVersion': 1, 'checkedAt': datetime.now(timezone.utc).isoformat(), 'software': rows}
    (output / 'index.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result
