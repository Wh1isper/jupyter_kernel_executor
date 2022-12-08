import asyncio
from pathlib import Path
from typing import Optional, List

from watchfiles import awatch, Change


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class FileWatcher(metaclass=Singleton):
    def __init__(self):
        self.task: Optional[asyncio.Task] = None
        self.handler: Optional = None

    @property
    def log(self):
        return self.handler.log

    @property
    def file_id_manager(self):
        return self.handler.file_id_manager

    @property
    def con(self):
        return self.handler.file_id_manager.con

    def initialize(self, handler):
        self.handler = handler

    def start_if_not(self, handler, root_dir):
        if self.task and not self.task.done():
            return
        self.initialize(handler)
        if not self.file_id_manager:
            return

        self.log.info('Start File watcher')
        if not root_dir:
            root_dir = '.'

        async def _():
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

        # recreate task
        if self.task:
            self.task.cancel()
            del self.task
        self.task = asyncio.create_task(_())

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
                if src.as_posix() == dst.as_posix():
                    self.file_id_manager.save(src.as_posix())
                else:
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
