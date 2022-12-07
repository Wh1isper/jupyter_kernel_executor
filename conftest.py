import pytest

pytest_plugins = ("jupyter_server.pytest_plugin",)


@pytest.fixture
def jp_server_config(jp_server_config):
    return {
        "ServerApp": {
            "jpserver_extensions": {
                "jupyter_kernel_executor": True,
                "jupyter_server_fileid": True,
            },
        },
        "FileIdExtension": {
            "file_id_manager_class": "jupyter_server_fileid.manager.LocalFileIdManager"
        }
    }
