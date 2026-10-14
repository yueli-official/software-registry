"""Strict manifest loading; consumer settings cannot enter the catalog."""
from pathlib import Path
import hashlib
import ipaddress
import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator
from .errors import RegistryError, require

SCHEMA = json.loads(Path(__file__).with_name('schema.json').read_text(encoding='utf-8'))
VALIDATOR = Draft202012Validator(SCHEMA)


def public_url(value, transient=False):
    try:
        url = urlsplit(value)
        require(url.scheme == 'https' and url.hostname and not url.username and not url.password,
                'url.public', 'Expected public HTTPS URL without credentials')
        require(url.port in (None, 443) and not url.fragment, 'url.public', 'Unexpected URL port or fragment')
        host = url.hostname.lower()
        require('.' in host and not host.endswith(('.local', '.internal', '.localhost', '.test', '.invalid')),
                'url.public', 'Private or reserved host is not allowed')
        try:
            require(ipaddress.ip_address(host).is_global, 'url.public', 'Private network address is not allowed')
        except ValueError as error:
            if isinstance(error, RegistryError):
                raise
        require(transient or not re.search(r'(?i)(?:[?&])(?:token|secret|password|signature|sig|x-amz-signature)=', value),
                'url.public', 'Credential-bearing URLs are not catalog data')
        return value
    except (ValueError, TypeError) as error:
        if isinstance(error, RegistryError):
            raise
        raise RegistryError('url.public', 'Invalid public URL') from None


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def validate_manifest(value, filename=None):
    errors = sorted(VALIDATOR.iter_errors(value), key=lambda e: str(list(e.path)))
    require(not errors, 'manifest.schema', 'Invalid manifest field: ' + ('.'.join(map(str, errors[0].path)) if errors else ''))
    require(filename is None or filename == value['id'], 'manifest.identity', 'Filename must match software id')
    public_url(value['homepage'])
    if value.get('documentationUrl'):
        public_url(value['documentationUrl'].split('#', 1)[0])
    if value.get('icon'):
        icon = value['icon']
        if icon.get('url'):
            public_url(icon['url'])
        if icon.get('archiveEntry'):
            entry = icon['archiveEntry']
            require(not entry.startswith('/') and '\\' not in entry and ':' not in entry and '..' not in entry.split('/'),
                    'image.archive', 'Unsafe icon archive entry')
        if icon.get('inlineSvg'):
            svg = icon['inlineSvg']
            require(icon['mime'] == 'image/svg+xml' and hashlib.sha256(svg.encode('utf-8')).hexdigest() == icon['sha256'],
                    'image.hash', 'Inline icon type or SHA256 differs')
            require(not re.search(r'<!DOCTYPE|<!ENTITY', svg, re.I), 'image.svg', 'SVG entity declarations are not accepted')
            try:
                tree = ET.fromstring(svg)
            except ET.ParseError:
                raise RegistryError('image.svg', 'Inline icon is not a valid SVG') from None
            require(tree.tag.rsplit('}', 1)[-1] == 'svg', 'image.svg', 'Expected an SVG root')
            for element in tree.iter():
                require(element.tag.rsplit('}', 1)[-1].lower() not in ('script', 'foreignobject', 'iframe', 'object', 'embed'),
                        'image.svg', 'Active SVG content is not accepted')
                for key, text in element.attrib.items():
                    require(not key.rsplit('}', 1)[-1].lower().startswith('on') and 'javascript:' not in text.lower(),
                            'image.svg', 'Active SVG attributes are not accepted')
                    if key.rsplit('}', 1)[-1].lower() == 'href':
                        require(text.startswith('#') or re.match(r'data:image/(?:png|jpeg|gif|webp);base64,', text),
                                'image.svg', 'Inline SVG cannot fetch external resources')
        if icon.get('sourceKind') == 'generated-name-mark':
            require(icon.get('inlineSvg') and icon.get('provenance'), 'image.provenance', 'Generated name marks require their SVG and provenance')
    for image in value['screenshots']:
        public_url(image['url'])
        public_url(image['sourcePage'].split('#', 1)[0])
        require(not any(c in image['caption'] for c in '\r\n[]\\'), 'image.caption', 'Screenshot captions must be plain single-line text')
    slots = []
    for index, package in enumerate(value['packages']):
        slots.append((package['channel'], package['platform'], package['architecture']))
        source = package['source']; options = source['options']
        if source['driver'] == 'scoop':
            architecture = {'64bit': 'amd64', '32bit': '386', 'arm64': 'arm64', 'universal': 'universal'}[options['architecture']]
            require(package['platform'] == 'windows' and package['architecture'] == architecture,
                    'manifest.platform', 'Scoop platform or architecture differs from its declared slot')
        if source['driver'] in ('official-checksum', 'evermeet-release', 'ppsspp-release') or options.get('versionFromPrimary'):
            require(index > 0, 'manifest.primary', 'This source requires an earlier primary package')
        for key, text in options.items():
            if key.endswith(('Url', 'UrlTemplate')):
                public_url(text.replace('{version}', '1.0.0').replace('{series}', '1.0'))
    require(len(slots) == len(set(slots)), 'manifest.slot', 'Duplicate platform/architecture slot')
    return value


def load_categories(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and not path.is_junction(),
            'category.file', 'Expected an ordinary category definition file')
    require(path.stat().st_size <= 64_000, 'category.size', 'Category definitions are too large')
    values = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(values, dict) and 0 < len(values) <= 128, 'category.definitions', 'Expected category names keyed by readable identifiers')
    require(all(isinstance(key, str) and re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', key)
                and isinstance(label, str) and 0 < len(label.strip()) <= 128 for key, label in values.items()),
            'category.definitions', 'Invalid category identifier or label')
    return values


def load_manifest(path, categories=None):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and not path.is_junction(), 'manifest.file', 'Expected an ordinary manifest file')
    require(path.stat().st_size <= 256_000, 'manifest.size', 'Manifest is too large')
    value = validate_manifest(json.loads(path.read_text(encoding='utf-8')), path.stem)
    categories = load_categories(path.parent.parent / 'categories.json') if categories is None else categories
    require(value['category'] in categories, 'category.reference', 'Software refers to an unknown category')
    return value


def load_catalog(directory):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink() and not directory.is_junction(), 'catalog.directory', 'Expected an ordinary catalog directory')
    categories = load_categories(directory.parent / 'categories.json')
    rows = [load_manifest(p, categories) for p in sorted(directory.glob('*.json'))]
    require(rows, 'catalog.empty', 'Catalog has no manifests')
    require(len({row['id'] for row in rows}) == len(rows), 'catalog.identity', 'Duplicate software identifier')
    return {row['id']: row for row in rows}
