import asyncio
import os
import json
from pathlib import Path
from uuid import uuid4

import pytest
import nbformat

_here = Path(os.path.abspath(os.path.dirname(__file__)))
INTERVAL = 1


@pytest.fixture
def code():
    return '''
import time
print('hello')
time.sleep(3)
print('world')
'''


@pytest.fixture
def ipynb(jp_root_dir, code):
    example_ipynb_path = _here / "test.ipynb"
    test_ipynb_path = "test.ipynb"

    filepath = Path(jp_root_dir) / test_ipynb_path
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(example_ipynb_path, "rb") as f:
        nb = nbformat.read(f, as_version=nbformat.NO_CONVERT)
    cell_id = nb['cells'][0]['id']
    nb['cells'][0]['source'] = code
    nb['cells'][0]['outputs'] = []

    with open(filepath, "w") as f:
        nbformat.write(nb, f)

    yield test_ipynb_path, cell_id, filepath.as_posix()


from .utils import *


async def test_move_file_when_execute(jp_fetch, ipynb, is_file_id_manager):
    if not is_file_id_manager:
        return pytest.skip('no file id manager, cannot process itl')

    ipynb_path, cell_id, real_path = ipynb

    kernel_response = await jp_fetch('api', 'kernels', method='POST', body=json.dumps({
        'name': 'python3',
        'path': ipynb_path
    }))
    kernel_id = json.loads(kernel_response.body)['id']

    body = {
        "path": ipynb_path,
        "cell_id": cell_id,
    }

    # execute code
    response = await jp_fetch('api', 'kernels', kernel_id, 'execute', method='POST', body=json.dumps(body))
    assert response.code == 200
    real_path = rename_random(real_path)

    # wait for finished
    await wait_for_finished(jp_fetch, kernel_id, ipynb_path, cell_id)

    outputs = [{'name': 'stdout', 'output_type': 'stream', 'text': 'hello\n'},
               {'name': 'stdout', 'output_type': 'stream', 'text': 'world\n'}]
    await assert_ipynb_cell_outputs(real_path, cell_id, outputs)


async def test_modify_file_when_execute(jp_fetch, ipynb, is_file_id_manager):
    if not is_file_id_manager:
        return pytest.skip('no file id manager, cannot process itl')
    ipynb_path, cell_id, real_path = ipynb

    kernel_response = await jp_fetch('api', 'kernels', method='POST', body=json.dumps({
        'name': 'python3',
        'path': ipynb_path
    }))
    kernel_id = json.loads(kernel_response.body)['id']

    body = {
        "path": ipynb_path,
        "cell_id": cell_id,
    }

    # execute code
    response = await jp_fetch('api', 'kernels', kernel_id, 'execute', method='POST', body=json.dumps(body))
    assert response.code == 200

    # modified time change, expect sync it normally
    with open(real_path, 'a+') as f:
        f.write('\n')
    await asyncio.sleep(0.1)

    # wait for finished
    await wait_for_finished(jp_fetch, kernel_id, ipynb_path, cell_id)

    outputs = [{'name': 'stdout', 'output_type': 'stream', 'text': 'hello\n'},
               {'name': 'stdout', 'output_type': 'stream', 'text': 'world\n'}]
    await assert_ipynb_cell_outputs(real_path, cell_id, outputs)


if __name__ == '__main__':
    pytest.main()
