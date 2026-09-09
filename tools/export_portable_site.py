"""Export committed website source and recovery instructions without credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    destination = args.destination.resolve()
    if destination == ROOT or ROOT in destination.parents:
        parser.error('Choose a destination outside the source checkout.')
    destination.mkdir(parents=True, exist_ok=False)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    archive = destination / 'website-source.zip'
    subprocess.run(['git', 'archive', '--format=zip', '-o', str(archive), sha], cwd=ROOT, check=True)
    shutil.copy2(ROOT / 'docs' / 'PORTABLE_WEBSITE.md', destination / 'START_HERE.md')
    shutil.copy2(Path(__file__), destination / 'export_portable_site.py')
    manifest = {
        'createdAt': datetime.now(timezone.utc).isoformat(),
        'sourceCommit': sha,
        'sourceArchiveSha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'includes': ['Committed Git source', 'Recovery instructions', 'Export script'],
        'excludes': ['Private broker archive', 'Uncommitted changes', 'Git history',
                     'Ignored recordings', 'Hosting credentials', 'Chat history'],
        'productionUrl': 'https://malosound.ai',
    }
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Exported {sha} to {destination}')


if __name__ == '__main__':
    main()
