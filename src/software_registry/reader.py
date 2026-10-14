"""Bounded public HTTP reads. Authentication is restricted to the GitHub API."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from .catalog import public_url
from .errors import RegistryError, require


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    max_redirections = 4

    def redirect_request(self, request, response, status, message, headers, new_url):
        # Storage signatures received during a download remain runtime-only.
        public_url(new_url, transient=True)
        if request.get_header('Authorization'):
            require(urlsplit(new_url).hostname == 'api.github.com', 'network.authentication', 'Authenticated redirect left the GitHub API')
        return super().redirect_request(request, response, status, message, headers, new_url)


class Reader:
    def __init__(self, timeout=30, metadata_limit=2_000_000):
        self.timeout = timeout
        self.limit = metadata_limit
        self.cache = {}

    def open(self, url, method='GET', headers=None):
        public_url(url)
        require(not any(k.lower() == 'authorization' for k in (headers or {})) or urlsplit(url).hostname == 'api.github.com',
                'network.authentication', 'Authentication is restricted to the GitHub API')
        request = urllib.request.Request(url, method=method, headers={'User-Agent': 'software-registry/0.1', **(headers or {})})
        try:
            return urllib.request.build_opener(PublicRedirect()).open(request, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            raise RegistryError('network.http', f'HTTP {error.code} from {urlsplit(url).hostname}') from None
        except OSError:
            raise RegistryError('network.unavailable', f'Cannot read {urlsplit(url).hostname}') from None

    def data(self, url, limit=None, headers=None):
        limit = self.limit if limit is None else limit
        with self.open(url, headers=headers) as response:
            data = response.read(limit + 1)
        require(len(data) <= limit, 'network.size', 'Metadata response exceeded its limit')
        return data

    def get(self, url):
        if url not in self.cache:
            self.cache[url] = json.loads(self.data(url))
        return self.cache[url]

    def github(self, endpoint):
        require(not endpoint.startswith('/') and '://' not in endpoint and '..' not in endpoint.split('/'),
                'network.github', 'Invalid GitHub API path')
        url = 'https://api.github.com/' + endpoint
        if url not in self.cache:
            token = os.environ.get('GITHUB_TOKEN')
            headers = {'Authorization': 'Bearer ' + token} if token else {}
            self.cache[url] = json.loads(self.data(url, headers=headers))
        return self.cache[url]

    def text(self, url):
        return self.data(url).decode('utf-8')

    def text_prefix(self, url):
        with self.open(url) as response:
            return response.read(256_000).decode('utf-8', errors='replace')

    def size(self, url, headers=None):
        with self.open(url, method='HEAD', headers=headers) as response:
            value = response.headers.get('Content-Length')
        return int(value) if value and value.isdecimal() else None
