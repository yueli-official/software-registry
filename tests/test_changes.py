import copy
import unittest
from software_registry.changes import component_fingerprints, equivalent, field_changes


def definition():
    return {'name': 'Example', 'homepage': 'https://example.org', 'category': 'utilities',
            'description': 'Intro\n\nSteps  \nDetails', 'usageInstructions': 'Open the app.', 'faq': 'See help.',
            'icon': {'sha256': 'a' * 64, 'url': 'https://example.org/icon.png'},
            'screenshots': [{'sha256': 'b' * 64, 'caption': 'First', 'sourcePage': 'https://example.org/docs'},
                            {'sha256': 'c' * 64, 'caption': 'Second', 'sourcePage': 'https://example.org/docs'}],
            'packages': [{'platform': 'windows', 'architecture': 'amd64', 'channel': 'stable',
                          'source': {'driver': 'github-release', 'options': {'repository': 'example/app'}}}]}


class ChangesTests(unittest.TestCase):
    def test_representation_changes_do_not_change_content(self):
        value = definition(); changed = dict(reversed(list(value.items())))
        changed['description'] = changed['description'].replace('\n', '\r\n') + '\r\n'
        self.assertEqual(component_fingerprints(value, {'utilities': 'Utilities'}),
                         component_fingerprints(changed, {'utilities': 'Utilities'}))
        self.assertFalse(equivalent('Text  \nNext', 'Text\nNext'))
        self.assertFalse(equivalent(True, 1))

    def test_text_change_does_not_invalidate_images_or_package_rules(self):
        value = definition(); changed = copy.deepcopy(value); changed['faq'] = 'New answer.'
        old = component_fingerprints(value, {'utilities': 'Utilities'})
        new = component_fingerprints(changed, {'utilities': 'Utilities'})
        self.assertEqual([key for key in old if old[key] != new[key]], ['content'])

    def test_caption_order_and_source_link_do_not_invalidate_image_bytes(self):
        value = definition(); changed = copy.deepcopy(value)
        changed['icon']['url'] = 'https://example.org/renamed-icon.png'
        changed['screenshots'].reverse(); changed['screenshots'][0]['caption'] = 'New caption'
        changed['screenshots'][0]['sourcePage'] = 'https://example.org/new-docs'
        old = component_fingerprints(value, {'utilities': 'Utilities'})
        new = component_fingerprints(changed, {'utilities': 'Utilities'})
        self.assertEqual([key for key in old if old[key] != new[key]], ['screenshotPresentation'])

    def test_only_owned_actual_differences_are_reported(self):
        current = {'faq': 'Answer\r\n', 'description': 'Existing\r\n', 'privateField': 'Keep'}
        self.assertEqual(field_changes(current, {'faq': 'Answer\n', 'description': 'Updated'}),
                         {'description': 'Updated'})
