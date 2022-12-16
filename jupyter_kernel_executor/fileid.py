class FileIDWrapper:
    def __init__(self, file_id_manager, save_lock):
        self.file_id_manager = file_id_manager
        self.save_lock = save_lock
        if file_id_manager:
            try:
                import jupyter_server_fileid
            except ImportError:
                self.enable = False
            else:
                self.enable = isinstance(file_id_manager, jupyter_server_fileid.manager.LocalFileIdManager)
        else:
            self.enable = False

    @property
    def log(self):
        return self.file_id_manager.log

    @property
    def con(self):
        return self.file_id_manager.con

    def normalize_path(self, path):
        if not path:
            return None

        if self.enable:
            return self.file_id_manager._normalize_path(path)
        else:
            return path

    def index(self, path):
        if path:
            path = path.lstrip('/')
        path = self.normalize_path(path)
        if not path:
            return None

        if self.enable:
            return self.file_id_manager.index(path)
        else:
            return path

    async def get_path(self, file_id):
        if not file_id:
            return None
        if self.enable:
            async with self.save_lock:
                row = self.file_id_manager.con.execute("SELECT path, ino FROM Files WHERE id = ?",
                                                       (file_id,)).fetchone()
                path, ino = row
                stat_info = self.file_id_manager._stat(path)
                # same inode number, consider it as same file
                if stat_info and ino == stat_info.ino:
                    return self.file_id_manager._from_normalized_path(path)
                # inode change, let file_id_manger sync it
                # finally fallback to file_id itself
                path = self.file_id_manager.get_path(file_id) or file_id
                self.log.debug(f'convert id {file_id} to file {path}')
        else:
            path = file_id
        return path

    def get_id(self, path):
        path = self.normalize_path(path)
        if not path:
            return None

        if self.file_id_manager:
            # get or index it
            file_id = self.file_id_manager.get_id(path) or self.index(path)
            self.log.debug(f'tracking file {path} with id {file_id}')
        else:
            file_id = path
        return file_id

    def save(self, path):
        if self.enable:
            return self.file_id_manager.save(path)

    def move(self, old_path, new_path):
        if self.enable:
            return self.file_id_manager.move(old_path, new_path)
