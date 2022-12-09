from pathlib import Path

import pytest

pytest_plugins = ("jupyter_server.pytest_plugin",)


@pytest.fixture
def is_file_id_manager():
    # todo: make it a para
    #       situation:
    #           no fileid (support update)
    #           fileid with default ArbitraryFileIdManager(support update)
    #           fileid with LocalFileIdManager(support update and move)
    try:
        import jupyter_server_fileid
    except ImportError:
        return False
    return True


@pytest.fixture
def jp_server_config(jp_server_config, tmpdir, is_file_id_manager):
    default_config = {
        "ServerApp": {
            "jpserver_extensions": {
                "jupyter_kernel_executor": True,
            },
        },
    }
    if is_file_id_manager:
        default_config['ServerApp']['jpserver_extensions']['jupyter_server_fileid'] = True
        default_config['FileIdExtension'] = {}
        default_config['FileIdExtension']['file_id_manager_class'] = 'jupyter_server_fileid.manager.LocalFileIdManager'
        default_config['LocalFileIdManager'] = {}
        default_config['LocalFileIdManager']['db_path'] = (Path(tmpdir) / 'db.sqlite').as_posix()

    return default_config
