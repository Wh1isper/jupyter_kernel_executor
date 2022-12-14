## Install

In Linux systems, it is common to use `ext` or similar file systems, and through the `ino` attributes provided by such
file systems, we can track the movement of files.

If your system meets these requirements, it is recommended that you also install jupyter_server_fileid

```bash
pip install jupyter_kernel_executor[fileid]
```

## Config

Config to use `LocalFileIdManager` to enable it, The default `ArbitraryFileIdManager` needs the assistance of other
functions to work properly, and currently no corresponding `watcher` has been seen to appear, so the default
configuration
`ArbitraryFileIdManager` has no effect in this plugin.

by using python config file

```python
import jupyter_server_fileid

c.FileIdExtension.file_id_manager_class = jupyter_server_fileid.manager.LocalFileIdManager
```

or json

```json
{
  "FileIdExtension": {
    "file_id_manager_class": "jupyter_server_fileid.manager.LocalFileIdManager"
  }
}
```

or hack (just an example, don't do it unless you have no other choice)

```python
def _load_jupyter_server_extension(serverapp):
    ...
    try:
        import jupyter_server_fileid
    except ImportError:
        return
    serverapp.web_app.settings['file_id_manager'] = jupyter_server_fileid.manager.LocalFileIdManager(
        log=serverapp.log, root_dir=serverapp.root_dir, config=serverapp.config
    )
```

## Behavior

When `LocalFileIdManager` is
enabled, [a watcher](https://github.com/Wh1isper/jupyter_kernel_executor/blob/master/jupyter_kernel_executor/file_watcher.py)
of `root_dir` is triggered whenever `document_id` and `cell_id` are
specified. It will listen to all the changes under the folder, save the `modified` event will trigger
`LocalFileIdManager.save()` to update the `mtime` in the database, move will trigger both the `added` and `deleted`
events, by
comparing the database'`mtime` and the `mtime` of the new file to locate the path after the file is moved

## Troubleshooting

If any problems occur, you can try to clear the fileid record database, which will not corrupt your code files

default is in `~/.local/share/jupyter/file_id_manager.db`, or just use `jupyter-fileid drop` to drop all records.
