"""Freeze source evidence, then verify original bytes before consumer handoff."""
import copy
import hashlib
import json
import os
import re
import time
from pathlib import Path
from .catalog import fingerprint, public_url, validate_manifest
from .errors import require
from .reader import Reader
from .sources import discover
from .state import ordinary_directory, plan_lock


def create_plan(manifest, reader=None):
    validate_manifest(manifest)
    require(manifest['kind'] != 'reference', 'plan.reference', 'Reference entries have no package release')
    resolved = discover(manifest, reader or Reader())
    for artifact in resolved['artifacts']:
        public_url(artifact['url'])
        name = artifact['filename']
        require(name not in ('', '.', '..') and not re.search(r'[<>:"/\\|?*\x00-\x1f]', name), 'plan.filename', 'Unsafe artifact filename')
    plan = {'schemaVersion': 1, 'softwareId': manifest['id'], 'manifestDigest': fingerprint(manifest),
            'version': resolved['version'], 'evidenceUrl': resolved['evidenceUrl'],
            'artifacts': resolved['artifacts'], 'verified': False}
    for key in ('authority', 'upstreamTag', 'upstreamReleaseId'):
        if key in resolved:
            plan[key] = resolved[key]
    plan['planDigest'] = fingerprint(plan)
    return plan


def validate_plan(plan):
    expected = plan['planDigest']
    value = {k: v for k, v in plan.items() if k != 'planDigest'}
    require(fingerprint(value) == expected, 'plan.digest', 'Plan changed since it was frozen')
    require(re.fullmatch(r'[a-f0-9]{64}', plan['manifestDigest']), 'plan.manifest', 'Invalid manifest digest')
    require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', plan['softwareId']), 'plan.identity', 'Invalid software identifier')
    public_url(plan['evidenceUrl'])
    require(plan['artifacts'], 'plan.empty', 'Plan has no packages')
    slots = []
    for a in plan['artifacts']:
        public_url(a['url'])
        require(a['filename'] not in ('', '.', '..') and not re.search(r'[<>:"/\\|?*\x00-\x1f]', a['filename']), 'plan.filename', 'Unsafe filename')
        slots.append((a['channel'], a['platform'], a['architecture']))
        if a.get('sha256'):
            require(re.fullmatch(r'[a-f0-9]{64}', a['sha256']), 'plan.hash', 'Invalid SHA256')
    require(len(slots) == len(set(slots)), 'plan.slot', 'Duplicate package slot')
    return plan


def _verify_plan(plan, directory, reader=None, maximum_bytes=300_000_000, signature_verifier=None):
    validate_plan(plan)
    require(type(maximum_bytes) is int and maximum_bytes > 0, 'verify.limit', 'Expected a positive byte limit')
    reader = reader or Reader()
    result = copy.deepcopy(plan)
    checks = []
    for index, artifact in enumerate(result['artifacts']):
        require(not artifact.get('signatureUrl') or signature_verifier is not None, 'verify.signature', 'A trusted detached-signature verifier is required for this source')
        if artifact.get('sizeBytes') is not None:
            require(type(artifact['sizeBytes']) is int and 0 < artifact['sizeBytes'] <= maximum_bytes,
                    'verify.size', 'Package exceeds the configured limit')
        file = directory / (str(index) + '-' + artifact['filename'])
        require(not file.is_symlink() and not file.is_junction(), 'verify.file', 'Package cache cannot be a link')
        if not file.exists():
            part = file.with_name(file.name + '.part')
            require(not part.is_symlink() and not part.is_junction(), 'verify.file', 'Partial cache cannot be a link')
            size = 0; deadline = time.monotonic() + 1800
            with reader.open(artifact['url']) as response, part.open('wb') as output:
                while block := response.read(1024 * 1024):
                    require(time.monotonic() <= deadline, 'verify.timeout', 'Download exceeded its time limit')
                    size += len(block)
                    require(size <= maximum_bytes, 'verify.size', 'Download exceeded the configured limit')
                    output.write(block)
            os.replace(part, file)
        require(file.stat().st_size <= maximum_bytes, 'verify.size', 'Cached package exceeds the configured limit')
        with file.open('rb') as data:
            actual = hashlib.file_digest(data, 'sha256').hexdigest()
        if artifact.get('sha256'):
            require(actual == artifact['sha256'], 'verify.hash', 'Original package SHA256 differs')
        if artifact.get('sourceHash'):
            algorithm = artifact['sourceHashAlgorithm']
            require(algorithm in ('sha1', 'sha256', 'sha512'), 'verify.hash', 'Unknown source hash algorithm')
            with file.open('rb') as data:
                require(hashlib.file_digest(data, algorithm).hexdigest() == artifact['sourceHash'], 'verify.hash', 'Source checksum differs')
        size = file.stat().st_size
        require(size > 0 and (artifact.get('sizeBytes') is None or size == artifact['sizeBytes']), 'verify.size', 'Original package size differs')
        if artifact.get('signatureUrl'):
            require(signature_verifier(artifact, file) is True, 'verify.signature', 'Detached signature did not verify')
        artifact.update(sha256=actual, sizeBytes=size)
        checks.append({'platform': artifact['platform'], 'architecture': artifact['architecture'], 'sha256': actual,
                       'sizeBytes': size, 'independentChecksum': bool(plan['artifacts'][index].get('sha256') or artifact.get('sourceHash'))})
    result['verified'] = True
    result['verification'] = checks
    result['inputPlanDigest'] = plan['planDigest']
    result.pop('planDigest')
    result['planDigest'] = fingerprint(result)
    (directory / 'verified.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return result



def verify_plan(plan, state_directory, reader=None, maximum_bytes=300_000_000, signature_verifier=None):
    validate_plan(plan)
    directory = ordinary_directory(Path(state_directory) / plan['planDigest'])
    with plan_lock(directory):
        return _verify_plan(plan, directory, reader, maximum_bytes, signature_verifier)
