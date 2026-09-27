"""Review or apply REgenOS display identity. Does not modify boot, disks or PAM."""
import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

IDENTITY = '''NAME="REgenOS"
PRETTY_NAME="REgenOS (Arch Linux prototype)"
ID=arch
ID_LIKE=arch
BUILD_ID=rolling
ANSI_COLOR="38;2;84;220;180"
HOME_URL="https://github.com/Aryan1771/ai-os"
DOCUMENTATION_URL="https://github.com/Aryan1771/ai-os/tree/main/docs"
SUPPORT_URL="https://github.com/Aryan1771/ai-os/issues"
LOGO=regenos
'''


def files(repo):
    return {
        'etc/os-release': IDENTITY,
        'usr/share/icons/hicolor/scalable/apps/regenos.svg': (repo/'branding/regenos-mark.svg').read_text(),
        'usr/share/pixmaps/regenos.svg': (repo/'branding/regenos-mark.svg').read_text(),
        'etc/issue': 'REgenOS — Arch Linux desktop prototype\\n\\l\n\n',
    }


def apply(root, repo):
    content = files(repo)
    directory = root/'var/lib/regenos/branding-backups'
    directory.mkdir(parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='identity-', dir=directory))
    manifest = {}
    # Back up all targets before replacing any. Preserve /etc/os-release's symlink,
    # never follow it to overwrite Arch's packaged /usr/lib/os-release.
    for name in content:
        path = root/name
        record = {'exists': path.exists() or path.is_symlink()}
        if path.is_symlink():
            record['symlink'] = os.readlink(path)
        elif path.exists():
            saved = backup/name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, saved)
        manifest[name] = record
    (backup/'manifest.json').write_text(json.dumps(manifest, indent=2))
    for name, text in content.items():
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix='.regenos-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as output:
                output.write(text)
            os.chmod(temporary, 0o644)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return backup


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.apply:
        if os.geteuid() != 0:
            parser.error('--apply needs root; review the default plan first')
        print('Identity applied. Backup:', apply(Path('/'), repo))
    else:
        print('Proposed files:', '\n'.join('/'+name for name in files(repo)), sep='\n')
        print(IDENTITY)
        print('Keeps ID=arch for package compatibility; replaces the os-release symlink, not its target.')
        print('No bootloader, initramfs, login authentication, disk or hostname changes.')
