"""Semantic change detection, independent of storage or publishing APIs."""
import hashlib
import json


def normalized(value):
    if isinstance(value, str):
        return value.replace('\r\n', '\n').replace('\r', '\n').rstrip('\n')
    if isinstance(value, dict):
        return {key: normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalized(item) for item in value]
    return value


def equivalent(left, right):
    return json.dumps(normalized(left), sort_keys=True, ensure_ascii=False) == json.dumps(normalized(right), sort_keys=True, ensure_ascii=False)


def field_changes(current, desired):
    return {key: value for key, value in desired.items() if not equivalent(current.get(key, ''), value)}


def digest(value):
    data = json.dumps(normalized(value), sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def component_fingerprints(manifest, categories):
    content = {key: manifest.get(key, '') for key in
               ('name', 'summary', 'description', 'usageInstructions', 'faq', 'homepage', 'documentationUrl', 'category')}
    content['categoryLabel'] = categories[manifest['category']]
    images = manifest.get('screenshots', [])
    packages = manifest.get('packages', [])
    rules = {'primary': packages[0] if packages else None,
             'supplemental': sorted(packages[1:], key=lambda row: (row['channel'], row['platform'], row['architecture']))}
    return {
        'content': digest(content),
        'iconBytes': digest(manifest['icon']['sha256']),
        'screenshotBytes': digest(sorted({image['sha256'] for image in images})),
        'screenshotPresentation': digest([{key: image[key] for key in ('sha256', 'caption', 'sourcePage')} for image in images]),
        'packageRules': digest(rules),
    }
