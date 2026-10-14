"""One verifier per frozen plan; links are never used as cache directories."""
from contextlib import contextmanager
from pathlib import Path
import os
from .errors import RegistryError, require


def ordinary_directory(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        require(not item.is_symlink() and not item.is_junction(), 'state.link', 'State directory has a linked ancestor')
    path.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def plan_lock(directory):
    file = directory / '.lock'
    require(not file.is_symlink() and not file.is_junction(), 'state.link', 'Lock cannot be a link')
    with file.open('a+b') as stream:
        if file.stat().st_size == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RegistryError('state.busy', 'Another verifier owns this plan') from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
