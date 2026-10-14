import argparse
import json
from pathlib import Path
from .catalog import load_catalog
from .errors import RegistryError, require
from .planning import create_plan, validate_plan, verify_plan


def main():
    parser = argparse.ArgumentParser(description='Validate software definitions and prepare immutable release plans')
    parser.add_argument('--catalog', type=Path, default=Path('software'))
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('validate')
    commands.add_parser('list')
    batch = commands.add_parser('plan-all')
    batch.add_argument('--output-directory', type=Path, required=True)
    plan = commands.add_parser('plan'); plan.add_argument('id'); plan.add_argument('--output', type=Path, required=True)
    verify = commands.add_parser('verify'); verify.add_argument('--plan', type=Path, required=True)
    verify.add_argument('--state-directory', type=Path, required=True); verify.add_argument('--output', type=Path, required=True)
    verify.add_argument('--maximum-bytes', type=int, default=300_000_000)
    args = parser.parse_args()
    try:
        if args.command == 'verify':
            value = json.loads(args.plan.read_text(encoding='utf-8'))
            catalog = load_catalog(args.catalog)
            require(value['softwareId'] in catalog, 'catalog.identity', 'Software is not in the catalog')
            from .catalog import fingerprint
            require(value['manifestDigest'] == fingerprint(catalog[value['softwareId']]), 'plan.manifest', 'Manifest changed after plan creation')
            result = verify_plan(value, args.state_directory, maximum_bytes=args.maximum_bytes)
        else:
            catalog = load_catalog(args.catalog)
            if args.command == 'validate':
                print(json.dumps({'valid': True, 'softwareCount': len(catalog)})); return 0
            if args.command == 'list':
                print(json.dumps(sorted(catalog))); return 0
            if args.command == 'plan-all':
                from .batch import discover_catalog
                result = discover_catalog(catalog, args.output_directory)
                from collections import Counter
                print(json.dumps({'softwareCount': len(catalog), 'outcomes': Counter(r['status'] for r in result['software'])}))
                return 0
            require(args.id in catalog, 'catalog.identity', 'Unknown software identifier')
            result = create_plan(catalog[args.id])
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'softwareId': result['softwareId'], 'version': result['version'], 'verified': result['verified']}))
        return 0
    except (RegistryError, OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'error': getattr(error, 'code', 'input.invalid'), 'message': str(error) if isinstance(error, RegistryError) else type(error).__name__}))
        return 1
