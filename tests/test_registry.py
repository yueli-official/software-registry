import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from software_registry.catalog import fingerprint, load_catalog, load_categories, load_manifest, public_url, validate_manifest
from software_registry.errors import RegistryError
from software_registry.planning import create_plan, validate_plan, verify_plan


def manifest():
    return {'schemaVersion': 1, 'id': 'sample', 'name': 'Sample', 'homepage': 'https://example.org/', 'kind': 'package',
            'category': 'utilities', 'summary': 'Sample utility', 'description': 'Sample software description.',
            'usageInstructions': 'Install and open the official package.', 'faq': 'See the official help for requirements.',
            'icon': {'url': 'https://example.org/icon.png', 'sha256': 'a' * 64, 'mime': 'image/png'}, 'screenshots': [],
            'packages': [{'platform': 'windows', 'architecture': 'amd64', 'channel': 'stable',
                          'source': {'driver': 'github-release', 'options': {'repository': 'example/sample', 'assetPattern': 'sample-{version}.zip'}}}]}


class FixtureReader:
    def __init__(self, values=None, data=b'original package'):
        self.values = values or {}
        self.payload = data
        self.reads = 0

    def github(self, endpoint):
        self.reads += 1
        return copy.deepcopy(self.values[endpoint])

    def get(self, url):
        return copy.deepcopy(self.values[url])

    def text(self, url):
        return self.values[url]

    def size(self, url, headers=None):
        return len(self.payload)

    def open(self, url):
        self.reads += 1
        return io.BytesIO(self.payload)


def release(data=b'original package'):
    return {'id': 12, 'tag_name': 'v1.2.3', 'html_url': 'https://github.com/example/sample/releases/tag/v1.2.3',
            'draft': False, 'prerelease': False, 'assets': [{'id': 42, 'name': 'sample-1.2.3.zip',
            'browser_download_url': 'https://github.com/example/sample/releases/download/v1.2.3/sample-1.2.3.zip',
            'size': len(data), 'digest': 'sha256:' + hashlib.sha256(data).hexdigest()}]}


class RegistryTests(unittest.TestCase):
    def test_release_date_is_official_optional_and_validated(self):
        value = release()
        reader = FixtureReader({'repos/example/sample/releases/latest': value})
        self.assertNotIn('upstreamPublishedAt', create_plan(manifest(), reader))
        value['published_at'] = '2025-01-02T03:04:05Z'
        reader = FixtureReader({'repos/example/sample/releases/latest': value})
        plan = create_plan(manifest(), reader)
        self.assertEqual(plan['upstreamPublishedAt'], value['published_at'])
        for bad in ('today', '2025-99-02T03:04:05Z', '2099-01-02T03:04:05Z'):
            changed = copy.deepcopy(plan); changed['upstreamPublishedAt'] = bad
            changed['planDigest'] = fingerprint({k: v for k, v in changed.items() if k != 'planDigest'})
            with self.subTest(date=bad), self.assertRaises(RegistryError): validate_plan(changed)

    def test_current_catalog_and_schema_copy(self):
        root = Path(__file__).resolve().parents[1]
        self.assertTrue(load_catalog(root / 'software'))
        self.assertEqual((root / 'schemas/software.schema.json').read_bytes(),
                         (root / 'src/software_registry/schema.json').read_bytes())

    def test_consumer_settings_and_hooks_cannot_enter_manifests(self):
        for key in ('credentials', 'deployment', 'storageKey', 'consumerId', 'shell', 'automation'):
            value = manifest(); value[key] = 'example'
            with self.assertRaises(RegistryError):
                validate_manifest(value)
        value = manifest(); value['packages'][0]['source']['options']['script'] = 'example'
        with self.assertRaises(RegistryError):
            validate_manifest(value)

    def test_private_and_credential_urls_are_rejected(self):
        for value in ['http://example.org/', 'https://127.0.0.1/', 'https://host.internal/',
                      'https://example.org/?token=example', 'https://invalid-user:invalid-password@example.org/']:
            with self.assertRaises(RegistryError):
                public_url(value)

    def test_catalog_content_is_complete_and_category_is_declared(self):
        value = manifest()
        for field in ('description', 'usageInstructions', 'faq', 'category'):
            incomplete = copy.deepcopy(value); incomplete.pop(field)
            with self.subTest(field=field), self.assertRaises(RegistryError):
                validate_manifest(incomplete)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'software').mkdir()
            path = root / 'software/sample.json'; path.write_text(json.dumps(value), encoding='utf-8')
            (root / 'categories.json').write_text('{"developer": "Developer tools"}', encoding='utf-8')
            with self.assertRaises(RegistryError):
                load_manifest(path)
            (root / 'categories.json').write_text('{"utilities": "Utilities"}', encoding='utf-8')
            self.assertEqual(load_manifest(path)['usageInstructions'], value['usageInstructions'])
            (root / 'categories.json').write_text('{"utilities": {"privateId": "example"}}', encoding='utf-8')
            with self.assertRaises(RegistryError):
                load_categories(root / 'categories.json')

    def test_documentation_url_obeys_public_source_boundary(self):
        value = manifest(); value['documentationUrl'] = 'https://docs.example.org/manual'
        validate_manifest(value)
        value['documentationUrl'] = 'https://private.internal/manual'
        with self.assertRaises(RegistryError):
            validate_manifest(value)

    def test_images_retain_source_identity_and_reject_active_svg(self):
        value = manifest()
        value['screenshots'] = [{'url': 'https://example.org/screenshot.png', 'sha256': 'b' * 64,
                                'mime': 'image/png', 'caption': 'Official example', 'sourcePage': 'https://example.org/docs#screenshots',
                                'licenseEvidence': 'Official permission evidence', 'provenance': 'Official example', 'reviewed': True}]
        validate_manifest(value)
        value['screenshots'][0]['assetId'] = 'consumer-private-id'
        with self.assertRaises(RegistryError):
            validate_manifest(value)
        value['screenshots'].pop()
        svg = '<svg xmlns="http://www.w3.org/2000/svg"><script>example()</script></svg>'
        value['icon'] = {'inlineSvg': svg, 'sha256': hashlib.sha256(svg.encode()).hexdigest(), 'mime': 'image/svg+xml'}
        with self.assertRaises(RegistryError):
            validate_manifest(value)

    def test_duplicate_slots_and_source_architecture_mismatch(self):
        value = manifest(); value['packages'] *= 2
        with self.assertRaises(RegistryError):
            validate_manifest(value)
        value = manifest(); value['packages'][0]['source'] = {'driver': 'scoop', 'options': {'bucket': 'main', 'app': 'sample', 'architecture': 'arm64'}}
        with self.assertRaises(RegistryError):
            validate_manifest(value)

    def test_release_plan_pins_upstream_asset_and_manifest(self):
        reader = FixtureReader({'repos/example/sample/releases/latest': release()})
        plan = create_plan(manifest(), reader)
        self.assertEqual(plan['version'], '1.2.3')
        self.assertEqual(plan['manifestDigest'], fingerprint(manifest()))
        self.assertEqual(plan['artifacts'][0]['upstreamAssetId'], 42)
        self.assertEqual(validate_plan(plan), plan)
        self.assertFalse(plan['verified'])

    def test_ambiguous_attachment_and_prerelease_stop_stable_updates(self):
        value = release(); value['assets'] *= 2
        with self.assertRaises(RegistryError):
            create_plan(manifest(), FixtureReader({'repos/example/sample/releases/latest': value}))
        value = release(); value['prerelease'] = True
        with self.assertRaises(RegistryError):
            create_plan(manifest(), FixtureReader({'repos/example/sample/releases/latest': value}))

    def test_beta_is_explicit_and_excludes_drafts(self):
        value = manifest(); value['packages'][0]['channel'] = 'beta'
        candidate = release(); candidate.update(prerelease=True, published_at='2026-01-01T00:00:00Z')
        draft = copy.deepcopy(candidate); draft.update(draft=True, published_at='2026-02-01T00:00:00Z')
        plan = create_plan(value, FixtureReader({'repos/example/sample/releases?per_page=100&page=1': [draft, candidate]}))
        self.assertEqual(plan['artifacts'][0]['channel'], 'beta')

    def test_platform_version_mismatch_cannot_drop_a_package(self):
        value = manifest(); package = copy.deepcopy(value['packages'][0]); package['platform'] = 'macos'
        package['source']['options']['repository'] = 'example/other'; value['packages'].append(package)
        other = release(); other['tag_name'] = 'v1.2.4'; other['assets'][0]['name'] = 'sample-1.2.4.zip'; other['assets'][0]['browser_download_url'] = other['assets'][0]['browser_download_url'].replace('1.2.3', '1.2.4')
        with self.assertRaises(RegistryError):
            create_plan(value, FixtureReader({'repos/example/sample/releases/latest': release(), 'repos/example/other/releases/latest': other}))

    def test_scoop_pins_commit_and_never_executes_download_hooks(self):
        value = manifest(); value['packages'][0]['source'] = {'driver': 'scoop', 'options': {'bucket': 'main', 'app': 'sample', 'architecture': '64bit'}}
        revision = 'a' * 40
        locator = 'https://raw.githubusercontent.com/ScoopInstaller/Main/' + revision + '/bucket/sample.json'
        row = {'version': '1.2.3', 'url': 'https://example.org/sample.zip', 'hash': 'b' * 64}
        reader = FixtureReader({'repos/ScoopInstaller/Main/commits/master': {'sha': revision}, locator: row})
        plan = create_plan(value, reader)
        self.assertIn(revision, plan['evidenceUrl'])
        row['pre_download'] = 'example'; reader.values[locator] = row
        with self.assertRaises(RegistryError):
            create_plan(value, reader)

    def test_tampered_plan_is_rejected_before_network_access(self):
        reader = FixtureReader({'repos/example/sample/releases/latest': release()})
        plan = create_plan(manifest(), reader); plan['artifacts'][0]['filename'] = 'changed.zip'
        before = reader.reads
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RegistryError):
                verify_plan(plan, directory, reader)
        self.assertEqual(reader.reads, before)

    def test_byte_verification_and_repeated_run_reuses_exact_cache(self):
        reader = FixtureReader({'repos/example/sample/releases/latest': release()})
        plan = create_plan(manifest(), reader)
        with tempfile.TemporaryDirectory() as directory:
            verified = verify_plan(plan, directory, reader)
            count = reader.reads
            self.assertTrue(verified['verified'])
            self.assertTrue(verified['verification'][0]['independentChecksum'])
            self.assertEqual(verify_plan(plan, directory, reader), verified)
            self.assertEqual(reader.reads, count)

    def test_wrong_bytes_and_size_limits_stop_handoff(self):
        plan = create_plan(manifest(), FixtureReader({'repos/example/sample/releases/latest': release()}))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RegistryError):
                verify_plan(plan, directory, FixtureReader(data=b'wrong bytes'))
        reader = FixtureReader()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RegistryError):
                verify_plan(plan, directory, reader, maximum_bytes=1)
        self.assertEqual(reader.reads, 0)

    def test_reference_has_no_invented_release(self):
        value = manifest(); value.update(kind='reference', packages=[])
        validate_manifest(value)
        with self.assertRaises(RegistryError):
            create_plan(value)

    def test_compact_version_rules_follow_new_releases(self):
        value = manifest(); value['packages'][0]['source']['options']['assetPattern'] = 'sample-{versionCompact}.zip'
        candidate = release(); candidate['assets'][0]['name'] = 'sample-123.zip'
        candidate['assets'][0]['browser_download_url'] = candidate['assets'][0]['browser_download_url'].replace('sample-1.2.3.zip', 'sample-123.zip')
        plan = create_plan(value, FixtureReader({'repos/example/sample/releases/latest': candidate}))
        self.assertEqual(plan['artifacts'][0]['filename'], 'sample-123.zip')

    def test_detached_signature_is_never_silently_skipped(self):
        plan = create_plan(manifest(), FixtureReader({'repos/example/sample/releases/latest': release()}))
        plan['artifacts'][0]['signatureUrl'] = 'https://example.org/sample.zip.sig'
        plan['planDigest'] = fingerprint({k: v for k, v in plan.items() if k != 'planDigest'})
        reader = FixtureReader()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RegistryError):
                verify_plan(plan, directory, reader)
            self.assertEqual(reader.reads, 0)
            self.assertTrue(verify_plan(plan, directory, reader, signature_verifier=lambda artifact, file: True)['verified'])

    def test_plan_lock_rejects_a_second_writer(self):
        from software_registry.state import ordinary_directory, plan_lock
        with tempfile.TemporaryDirectory() as directory:
            root = ordinary_directory(directory)
            with plan_lock(root):
                with self.assertRaises(RegistryError):
                    with plan_lock(root):
                        pass

    def test_authentication_cannot_be_sent_to_a_download_host(self):
        from software_registry.reader import Reader
        with self.assertRaises(RegistryError):
            Reader().open('https://example.org/sample.zip', headers={'Authorization': 'example'})

    def test_runtime_storage_signature_is_not_a_catalog_url(self):
        value = 'https://example.org/file.zip?sig=example'
        with self.assertRaises(RegistryError):
            public_url(value)
        self.assertEqual(public_url(value, transient=True), value)


if __name__ == '__main__':
    unittest.main()
