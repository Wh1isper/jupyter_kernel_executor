from pathlib import Path

import pytest

pytest_plugins = ("jupyter_server.pytest_plugin",)


@pytest.fixture
def jp_server_config(jp_server_config, tmpdir):
    default_config = {
        "ServerApp": {
            "jpserver_extensions": {
                "jupyter_kernel_executor": True,
            },
        },
    }
    if is_file_id_manager():
        default_config['ServerApp']['jpserver_extensions']['jupyter_server_fileid'] = True
        default_config['FileIdExtension'] = {}
        default_config['FileIdExtension']['file_id_manager_class'] = 'jupyter_server_fileid.manager.LocalFileIdManager'
        default_config['LocalFileIdManager'] = {}
        default_config['LocalFileIdManager']['db_path'] = (Path(tmpdir) / 'db.sqlite').as_posix()

    return default_config


def is_file_id_manager():
    try:
        import jupyter_server_fileid
    except ImportError:
        return False
    return True
