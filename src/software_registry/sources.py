"""Read-only official-source resolvers. No installation hooks are executed."""
import fnmatch
import re
import urllib.parse
from datetime import date
from .errors import RegistryError as PlanError, require

BUCKETS = {'main': 'ScoopInstaller/Main', 'extras': 'ScoopInstaller/Extras'}

def download_url(value):
    require(isinstance(value, str), 'source.url', 'Expected a direct download URL')
    parsed = urllib.parse.urlsplit(value)
    require(parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password,
            'source.url', 'Only direct HTTPS URLs without credentials are supported')
    require(not any(x in value for x in ('$version', '$arch', '{{', '}}')),
            'source.dynamic', 'Unresolved download variables are unsupported')
    # Scoop's #/name changes the installed filename, not the upstream asset name.
    url = urllib.parse.urlunsplit(parsed._replace(fragment=''))
    name = urllib.parse.unquote(parsed.path.rsplit('/', 1)[-1])
    require(name and name not in ('.', '..') and not re.search(r'[<>:"/\\|?*\x00-\x1f]', name),
            'source.filename', 'Unsafe or missing upstream filename')
    return url, name


def source_hash(value):
    if not isinstance(value, str):
        return None, None
    raw = value.strip()
    if ':' in raw:
        algorithm, digest = raw.split(':', 1)
        algorithm = algorithm.lower()
    else:
        algorithm, digest = 'sha256', raw
    sizes = {'sha1': 40, 'sha256': 64, 'sha512': 128}
    if algorithm not in sizes or not re.fullmatch(f'[a-fA-F0-9]{{{sizes[algorithm]}}}', digest):
        return None, None
    return algorithm, digest.lower()


def sha256(value):
    algorithm, digest = source_hash(value)
    return digest if algorithm == 'sha256' else None


def github_asset(asset, slot):
    url, name = download_url(asset['browser_download_url'])
    require(name == asset['name'] and isinstance(asset['size'], int) and asset['size'] > 0,
            'source.asset', 'Unexpected GitHub asset metadata')
    return slot | {'filename': name, 'url': url, 'sha256': sha256(asset.get('digest')),
                   'sizeBytes': asset['size'], 'upstreamAssetId': asset['id'], 'upstreamUpdatedAt':asset.get('updated_at')}


def resolve_scoop(entry, reader):
    options = entry['source']['options']
    repository = BUCKETS[options['bucket']]
    revision = reader.github(f'repos/{repository}/commits/master')['sha']
    require(re.fullmatch('[a-f0-9]{40}', revision), 'source.revision', 'Invalid bucket revision')
    manifest_url = f'https://raw.githubusercontent.com/{repository}/{revision}/bucket/{options["app"]}.json'
    manifest = reader.get(manifest_url)
    version = manifest.get('version')
    require(isinstance(version, str) and version and version.lower() not in ('nightly', 'latest'),
            'source.version', 'Manifest must declare a fixed version')
    if options.get('stripPackageRevision'):
        match = re.fullmatch(r'([0-9]+(?:\.[0-9]+){1,3})-[0-9]+', version)
        require(match is not None, 'source.version', 'Expected a numeric Scoop package revision suffix')
        version = match.group(1)
    architectures = manifest.get('architecture')
    require(options['architecture'] != 'universal' or architectures is None,
            'source.architecture', 'Universal packages require an architecture-independent manifest')
    require(architectures is None or options['architecture'] in architectures,
            'source.architecture', 'Requested architecture is unavailable')
    selected = manifest | (architectures[options['architecture']] if architectures else {})
    require(not selected.get('pre_download'), 'source.script-required', 'pre_download is not supported')
    urls, hashes = selected.get('url'), selected.get('hash')
    urls = urls if isinstance(urls, list) else [urls]
    hashes = hashes if isinstance(hashes, list) else [hashes]
    require(len(urls) == 1 and len(hashes) == 1, 'source.multiple-files',
            'First version supports one directly downloadable package per manifest')
    url, source_name = download_url(urls[0])
    name = source_name
    if options.get('filenameTemplate'):
        name = options['filenameTemplate'].replace('{version}', version)
        require('{version}' in options['filenameTemplate'] and '{' not in name and '}' not in name,
                'source.filename', 'Scoop filenameTemplate must use only {version}')
        require(name not in ('', '.', '..') and not re.search(r'[<>:"/\\|?*\x00-\x1f]', name),
                'source.filename', 'Unsafe generated package filename')
    hash_algorithm, source_digest = source_hash(hashes[0])
    require(source_digest, 'source.hash', 'Manifest must provide a supported SHA1/SHA256/SHA512 hash')
    digest = source_digest if hash_algorithm == 'sha256' else None
    artifact = entry['slot'] | {'filename': name, 'url': url, 'sha256': digest,
                                'sourceHashAlgorithm': hash_algorithm, 'sourceHash': source_digest,
                                'sizeBytes': None, 'sizeCheck': 'unknown'}
    # Fixed GitHub asset metadata is preferable to HEAD: it also detects replaced assets.
    parsed = urllib.parse.urlsplit(url)
    match = re.fullmatch(r'/([^/]+/[^/]+)/releases/download/([^/]+)/([^/]+)', parsed.path)
    if parsed.hostname == 'github.com' and match:
        repo, tag, _ = match.groups()
        release = reader.github(f'repos/{repo}/releases/tags/{tag}')
        matches = [a for a in release['assets'] if a['name'] == source_name]
        if not matches and digest:
            # Scoop sometimes keeps obsolete filename casing. Reconcile only
            # an unambiguous official attachment with the same SHA256 bytes.
            folded = [a for a in release['assets'] if a['name'].casefold() == source_name.casefold()]
            if len(folded) == 1 and folded[0].get('digest') == 'sha256:' + digest:
                matches = folded
                artifact.update(manifestDownloadUrl=url, manifestFilename=source_name,
                                upstreamNameCorrection='case-only-official-sha256-match',
                                url=folded[0]['browser_download_url'])
                if not options.get('filenameTemplate'):
                    artifact['filename'] = folded[0]['name']
        require(len(matches) == 1, 'source.asset-missing', 'Manifest attachment is missing or ambiguous')
        remote = github_asset(matches[0], entry['slot'])
        require(digest is None or remote['sha256'] is None or remote['sha256'] == digest,
                'source.hash-conflict', 'Scoop and upstream SHA256 disagree')
        artifact.update(sha256=remote['sha256'] or digest, sizeBytes=remote['sizeBytes'],
                        upstreamAssetId=remote['upstreamAssetId'], sizeCheck='github')
    else:
        # Failure to establish size is never interpreted as under the limit.
        artifact['sizeBytes'] = reader.size(url)
        artifact['sizeCheck'] = 'head' if artifact['sizeBytes'] is not None else 'unknown'
    return ({'upstreamPublishedAt': release['published_at']} if parsed.hostname == 'github.com' and match and release.get('published_at') else {}) | {'version': version, 'authority': 'scoop-manifest', 'revision': revision,
            'evidenceUrl': manifest_url, 'homepage': manifest.get('homepage'),
            'license': manifest.get('license'), 'artifacts': [artifact]}


def resolve_github(entry, reader):
    options = entry['source']['options']
    repo = options['repository']
    tag_template = options.get('tagTemplate')
    if tag_template:
        require(not re.search(r'\{version(?:3)?\}',tag_template) or entry.get('_sourceVersion'),
                'source.tag', 'A version tag template requires the resolved primary version')
        source_version=entry.get('_sourceVersion','')
        requested_tag = tag_template.replace('{version}',source_version).replace('{version3}', '.'.join(source_version.split('.')[:3]))
        release = reader.github(f'repos/{repo}/releases/tags/{urllib.parse.quote(requested_tag, safe="")}')
        require(release.get('tag_name') == requested_tag, 'source.tag', 'Resolved release tag differs from the requested tag')
    elif entry['slot']['channel'] == 'beta':
        rows = reader.github(f'repos/{repo}/releases?per_page=100&page=1')
        candidates = [r for r in rows if r.get('prerelease') and not r.get('draft')]
        require(candidates, 'source.channel', 'No beta release found')
        require(len(rows) < 100, 'source.pagination', 'Beta discovery needs explicit review beyond the first release page')
        release = max(candidates, key=lambda r: r.get('published_at') or '')
    else:
        release = reader.github(f'repos/{repo}/releases/latest')
    require(not release.get('draft') and bool(release.get('prerelease')) == (entry['slot']['channel'] == 'beta'),
            'source.channel', 'Release channel differs from the declared package')
    tag = release['tag_name']
    prefix = options.get('tagPrefix')
    if prefix is None:
        version = tag.removeprefix('v')
    else:
        require(tag.startswith(prefix), 'source.tag', 'Latest release tag does not match configured prefix')
        version = tag[len(prefix):]
    suffix = options.get('tagSuffix')
    if suffix is not None:
        require(suffix in ('-stable', '-F-DROID') and version.endswith(suffix),
                'source.tag', 'Expected the configured official release suffix')
        version = version[:-len(suffix)]
    if tag_template and '{version}' in tag_template:
        # The exact requested tag was already checked, including any project suffix.
        version = entry['_sourceVersion']
    if options.get('tagVersionFormat') == 'date-build':
        match = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})-(\d{2})', version)
        require(match is not None, 'source.version', 'Expected an official YYYY-MM-DD-NN build tag')
        components = tuple(map(int, match.groups()))
        try:
            date(*components[:3])
        except ValueError:
            raise PlanError('source.version', 'Official build tag has an invalid calendar date') from None
        require(components[3] > 0, 'source.version', 'Official daily build number must be positive')
        version = '.'.join(map(str, components))
    require(version and re.fullmatch(r'[0-9]+(?:\.[0-9]+){0,3}(?:[-+][0-9A-Za-z.-]+)?', version),
            'source.version', 'GitHub release tag did not yield a numeric version')
    pattern = options['assetPattern'].replace('{version}', version).replace('{versionCompact}', version.replace('.', ''))
    if options.get('versionFromPrimary'):
        primary=entry.get('_sourceVersion')
        require(primary and primary.startswith(version+'.') and re.fullmatch(r'\d+(?:\.\d+){3}',primary),
                'source.version', 'Build version requires a matching three-component official release tag')
        version=primary
        pattern=options['assetPattern'].replace('{version}',version).replace('{versionCompact}',version.replace('.', ''))
    matches = [a for a in release['assets'] if fnmatch.fnmatchcase(a['name'], pattern)]
    require(len(matches) == 1, 'source.asset-match', 'Expected exactly one matching release attachment')
    require(not options.get('versionFromPrimary') or version in matches[0]['name'],
            'source.version', 'The official attachment must explicitly name the complete primary build version')
    return {'version': version, 'authority': 'github-date-build' if options.get('tagVersionFormat') == 'date-build' else 'github-tag' if tag_template else 'github-latest',
            **({'upstreamPublishedAt': release['published_at']} if release.get('published_at') else {}),
            'upstreamTag': tag,
            'evidenceUrl': release['html_url'], 'upstreamReleaseId': release['id'],
            'artifacts': [github_asset(matches[0], entry['slot'])]}


def resolve_evermeet_release(entry, reader):
    """Follow the primary version using the vendor's exact-version metadata."""
    version = entry.get('_sourceVersion')
    require(version and re.fullmatch(r'\d+(?:\.\d+){1,3}', version),
            'source.version', 'Evermeet must follow a fixed primary version')
    require(entry['slot']['platform'] == 'macos' and entry['slot']['architecture'] == 'amd64',
            'source.architecture', 'Evermeet provides Intel macOS binaries only')
    page = 'https://evermeet.cx/ffmpeg/info/ffmpeg/' + version
    info = reader.get(page)
    require(info.get('name') == 'ffmpeg' and info.get('type') == 'release' and info.get('version') == version,
            'source.version', 'Evermeet release identity/version changed')
    asset = info['download']['zip']
    url, filename = download_url(asset['url'])
    require(url == f'https://evermeet.cx/ffmpeg/ffmpeg-{version}.zip'
            and type(asset.get('size')) is int and asset['size'] > 0,
            'source.asset-match', 'Expected the exact versioned Evermeet ZIP')
    return {'version': version, 'authority': 'evermeet-version-api', 'evidenceUrl': page,
            'artifacts': [entry['slot'] | {'url': url, 'filename': filename, 'sha256': None,
                'sizeBytes': asset['size'], 'sizeCheck': 'vendor-api',
                'signatureUrl': asset['sig'], 'officialDownloadPage': 'https://evermeet.cx/ffmpeg/'}]}


def resolve_official_checksum(entry, reader):
    options=entry['source']['options'];version=entry.get('_sourceVersion')
    require(version and re.fullmatch(r'\d+(?:\.\d+){1,3}',version),
            'source.version','Official checksum packages must follow the resolved primary version')
    def expand(value):
        value=value.replace('{version}',version).replace('{series}','.'.join(version.split('.')[:2]))
        require('{' not in value and '}' not in value,'source.template','Unknown official source template variable')
        return value
    require('{version}' in options['urlTemplate'],'source.version','Official package URL must name the exact primary version')
    url,filename=download_url(expand(options['urlTemplate']))
    checksum_url=expand(options['checksumUrlTemplate']);download_url(checksum_url)
    require(urllib.parse.urlsplit(checksum_url).hostname==urllib.parse.urlsplit(url).hostname,
            'source.hash-origin','Official checksum and package must share an origin')
    checksums=reader.text(checksum_url)
    matches=[m[1].lower() for line in checksums.splitlines()
             if (m:=re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?(.+)',line.strip())) and m[2]==filename]
    require(len(matches)==1,'source.hash','Expected one official SHA256 entry for the exact filename')
    artifact=entry['slot']|{'filename':filename,'url':url,'sha256':matches[0],
                          'sizeBytes':reader.size(url),'sizeCheck':'head','checksumUrl':checksum_url,
                          'officialDownloadPage':options['evidenceUrl']}
    return {'version':version,'authority':'official-sha256','evidenceUrl':options['evidenceUrl'],'artifacts':[artifact]}


def resolve_python_release(entry, reader):
    options = entry['source']['options']
    series = options['series']
    releases = reader.get('https://www.python.org/api/v2/downloads/release/?is_published=true')
    require(isinstance(releases, list), 'source.response', 'Python release catalog must be a list')
    pattern = re.compile(rf'^Python {re.escape(series)}\.(\d+)$')
    matches = []
    for release in releases:
        if not isinstance(release, dict) or not release.get('is_published') or release.get('pre_release'):
            continue
        match = pattern.fullmatch(str(release.get('name', '')))
        if match:
            matches.append((int(match.group(1)), release))
    require(matches, 'source.version', f'No published Python {series}.x release found')
    _, release = max(matches, key=lambda item: item[0])
    version = release['name'].removeprefix('Python ')
    resource = str(release.get('resource_uri', ''))
    match = re.fullmatch(r'https://www\.python\.org/api/v2/downloads/release/(\d+)/', resource)
    require(match is not None, 'source.response', 'Unexpected Python release resource URI')
    release_id = match.group(1)
    files = reader.get(f'https://www.python.org/api/v2/downloads/release_file/?release={release_id}')
    require(isinstance(files, list), 'source.response', 'Python release file catalog must be a list')
    names = {
        '64bit': 'Windows installer (64-bit)',
        '32bit': 'Windows installer (32-bit)',
        'arm64': 'Windows installer (ARM64)',
    }
    name = 'macOS installer' if entry['slot']['platform']=='macos' else names[options['architecture']]
    selected = [item for item in files if isinstance(item, dict) and item.get('name') == name]
    require(len(selected) == 1, 'source.asset-match', 'Expected exactly one Python Windows installer')
    asset = selected[0]
    url, filename = download_url(asset.get('url'))
    parsed = urllib.parse.urlsplit(url)
    require(parsed.hostname == 'www.python.org' and parsed.path.startswith(f'/ftp/python/{version}/'),
            'source.url', 'Python installer must come from the official python.org release directory')
    digest = str(asset.get('sha256_sum', '')).lower()
    require(re.fullmatch(r'[a-f0-9]{64}', digest) is not None, 'source.hash', 'Python installer requires SHA256')
    size = asset.get('filesize')
    require(isinstance(size, int) and size > 0, 'source.size', 'Python installer size is missing')
    artifact = entry['slot'] | {'filename': filename, 'url': url, 'sha256': digest,
                                'sizeBytes': size, 'upstreamAssetId': asset.get('resource_uri'),
                                'sizeCheck': 'python.org-api'}
    return {'version': version, 'authority': 'python.org-api',
            'evidenceUrl': f'https://www.python.org/downloads/release/{release.get("slug")}/',
            'homepage': 'https://www.python.org/', 'artifacts': [artifact]}


def resolve_iterm_release(entry, reader):
    """Read the first complete stable release and its published SHA256."""
    page = 'https://iterm2.com/downloads.html'
    html = reader.text_prefix(page)
    sections = re.findall(r'<h4\b[^>]*>.*?(?=<h4\b)', html, re.S)
    require(sections, 'source.metadata-size', 'No complete iTerm2 stable release section in the bounded page prefix')
    block = sections[0]
    matches = re.findall(r'href="(https://iterm2\.com/downloads/stable/iTerm2-([0-9]+(?:_[0-9]+){2})\.zip)"', block)
    require(len(matches) == 1, 'source.asset-match', 'Expected one official stable iTerm2 ZIP')
    hashes = re.findall(r'\n\s*([a-f0-9]{64})\s*\n', block)
    require(len(hashes) == 1 and 'BEGIN PGP SIGNED MESSAGE' in block,
            'source.hash', 'Expected one published SHA256 in the exact stable release section')
    url, numeric = matches[0]
    url, filename = download_url(url)
    artifact = entry['slot'] | {'url': url, 'filename': filename, 'sha256': hashes[0],
        'sizeBytes': reader.size(url), 'sizeCheck': 'head', 'checksumUrl': page, 'officialDownloadPage': page}
    return {'version': numeric.replace('_', '.'), 'authority': 'iterm2-stable-page-sha256',
            'evidenceUrl': page, 'artifacts': [artifact]}


def resolve_ppsspp_release(entry, reader):
    """Official Android binary, linked by PPSSPP's download page for the primary version."""
    from html.parser import HTMLParser
    version = entry.get('_sourceVersion')
    require(isinstance(version, str) and re.fullmatch(r'\d+\.\d+(?:\.\d+)?', version),
            'source.version', 'PPSSPP Android must follow an exact stable primary version')
    require(entry['slot']['platform'] == 'android' and entry['slot']['architecture'] == 'universal'
            and entry['source']['options'] == {'package': 'android'},
            'source.platform', 'Only the official universal Android package is supported')
    page = 'https://www.ppsspp.org/download/'
    url = 'https://www.ppsspp.org/files/' + version.replace('.', '_') + '/ppsspp.apk'
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.urls = set()
        def handle_starttag(self, tag, attrs):
            if tag == 'a':
                href = dict(attrs).get('href')
                if href: self.urls.add(urllib.parse.urljoin(page, href))
    links = Links(); links.feed(reader.text(page))
    require(url in links.urls, 'source.asset-match', 'Exact version APK is absent from official download page')
    size = reader.size(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': page})
    require(isinstance(size, int) and 0 < size <= 300000000, 'source.size', 'Official APK exceeds package limit or has no fixed size')
    return {'version': version, 'authority': 'ppsspp.org-download-page', 'evidenceUrl': page,
            'artifacts': [entry['slot'] | {'filename': 'ppsspp.apk', 'url': url, 'sha256': None,
                           'sizeBytes': size, 'sizeCheck': 'head', 'officialDownloadPage': page}]}


def discover(manifest, reader):
    resolvers = {'scoop': resolve_scoop, 'github-release': resolve_github,
                 'python-release': resolve_python_release, 'iterm-release': resolve_iterm_release,
                 'evermeet-release': resolve_evermeet_release, 'official-checksum': resolve_official_checksum,
                 'ppsspp-release': resolve_ppsspp_release}
    packages = manifest['packages']
    primary = None
    artifacts = []
    for package in packages:
        entry = {'slot': {k: package[k] for k in ('platform', 'architecture', 'channel')}, 'source': package['source']}
        if primary:
            entry['_sourceVersion'] = primary['version']
        candidate = resolvers[entry['source']['driver']](entry, reader)
        if primary is None:
            primary = candidate
        require(candidate['version'] == primary['version'], 'source.platform-version', 'Platform versions differ')
        artifacts.extend(a | {'sourceAuthority': candidate['authority'],
                             'sourceReleaseId': candidate.get('upstreamReleaseId')}
                         for a in candidate['artifacts'])
    return primary | {'artifacts': artifacts}
