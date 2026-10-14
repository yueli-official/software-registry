import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from software_registry.batch import discover_catalog
from software_registry.errors import RegistryError


class BatchTests(unittest.TestCase):
    def test_failed_source_does_not_suppress_other_plans_or_invent_reference_packages(self):
        catalog={'good':{'kind':'package'},'broken':{'kind':'package'},'link':{'kind':'reference'}}
        def plan(manifest, reader):
            if manifest is catalog['broken']: raise RegistryError('source.missing','Unavailable')
            return {'version':'1.2.3','planDigest':'a'*64}
        with tempfile.TemporaryDirectory() as directory, patch('software_registry.batch.create_plan',side_effect=plan):
            result=discover_catalog(catalog,Path(directory),reader=object())
            rows={r['softwareId']:r for r in result['software']}
            self.assertEqual(rows['broken']['error'],'source.missing')
            self.assertEqual(rows['link']['status'],'reference')
            self.assertEqual(json.loads((Path(directory)/rows['good']['path']).read_text())['version'],'1.2.3')
            self.assertFalse((Path(directory)/'plans/link.json').exists())
