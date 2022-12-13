## Install

In Linux systems, it is common to use `ext` or similar file systems, and through the `ino` attributes provided by such
file systems, we can track the movement of files.

If your system meets these requirements, it is recommended that you also install jupyter_server_fileid

```bash
pip install jupyter_kernel_executor[fileid]
```

## Config

Config to use `LocalFileIdManager` to enable it

by using python config file

```python
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

## Troubleshooting

If any problems occur, you can try to clear the fileid record database, which will not corrupt your code files

default is in `~/.local/share/jupyter/file_id_manager.db`, or just use `jupyter-fileid drop` to drop all records.
