import asyncio
from pathlib import Path
from typing import Optional, List

from watchfiles import awatch, Change

from jupyter_kernel_executor.fileid import FileIDWrapper


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class FileWatcher(metaclass=Singleton):
    def __init__(self, file_id_manager):
        self.task: Optional[asyncio.Task] = None
        self.file_id_manager: Optional[FileIDWrapper] = file_id_manager
        self.handlers = []

    @property
    def log(self):
        return getattr(self.file_id_manager, 'log')

    @property
    def con(self):
        return getattr(self.file_id_manager, 'con')

    def add(self, handle):
        self.handlers.append(handle)

    def remove(self, handle):
        if handle in self.handlers:
            self.handlers.remove(handle)
        # last exit, cleanup
        if not self.handlers:
            self.cancel()

    def cancel(self):
        if self.task:
            self.task.cancel()

    def start_if_not(self, root_dir):
        if self.task and not self.task.done():
            return self
        if not self.file_id_manager.enable:
            return self

        self.log.info('Start global file watcher')
        if not root_dir:
            root_dir = '.'

        async def _():
            # fixme There is this error on server shutdown
            # RuntimeError: Already borrowed
            # https://github.com/samuelcolvin/watchfiles/issues/200
            # https://github.com/PyO3/pyo3/issues/2525
            async for changes in awatch(root_dir):
                deleted_paths = []
                added_paths = []
                for change, changed_path in changes:
                    changed_path = Path(changed_path)
                    if change == Change.deleted:
                        deleted_paths.append(changed_path)
                        self.maybe_renamed(changed_path, deleted_paths, added_paths, is_added_path=False)
                    elif change == Change.added:
                        added_paths.append(changed_path)
                        self.maybe_renamed(changed_path, added_paths, deleted_paths, is_added_path=True)
                    elif change == Change.modified:
                        # Only modified can use save
                        self.file_id_manager.save(changed_path)

        # recreate task
        if self.task:
            self.task.cancel()
            del self.task
        self.task = asyncio.create_task(_())
        return self

    def maybe_renamed(self, changed_path: Path, changed_paths: List[Path], other_paths: List[Path],
                      is_added_path):
        if is_added_path:
            src = None
            dst = changed_path
        else:
            src = changed_path
            dst = None

        for op in other_paths:
            if self.get_mtime(changed_path) == self.get_mtime(op):
                changed_paths.remove(changed_path)
                if is_added_path:
                    src = op
                else:
                    dst = op
                self.file_id_manager.move(src.as_posix(), dst.as_posix())
                return

    def get_mtime(self, path):
        path = Path(path)
        if path.exists():
            return path.stat().st_mtime

        src = self.con.execute(
            "SELECT mtime FROM Files WHERE path = ?", (path.as_posix(),)
        ).fetchone()
        if src:
            return src[0]
        else:
            return None
