import asyncio
import os
import json
from pathlib import Path

import pytest
import nbformat

_here = Path(os.path.abspath(os.path.dirname(__file__)))
INTERVAL = 1


@pytest.fixture
def code():
    return '''
import time
print('hello')
time.sleep(1)
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

    with open(filepath, "w") as f:
        nbformat.write(nb, f)

    yield test_ipynb_path, cell_id, filepath.as_posix()


def assert_ipynb_cell_outputs(real_path, cell_id, outputs):
    with open(real_path) as f:
        nb = nbformat.read(f, as_version=nbformat.NO_CONVERT)
    for cell in nb['cells']:
        if cell['id'] == cell_id:
            assert cell['outputs'] == outputs
            return
    raise KeyError('cell not found')


async def wait_for_finished(jp_fetch, kernel_id, path, cell_id):
    body = {
        "path": path,
        "cell_id": cell_id,
    }
    for _ in range(10 * INTERVAL):
        response = await jp_fetch('api', 'kernels', kernel_id, 'execute', method='GET')
        payload = json.loads(response.body)
        if body not in payload:
            break
        await asyncio.sleep(INTERVAL)
    else:
        raise TimeoutError('execute code timeout')


async def test_execute_cell(jp_fetch, ipynb):
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

    # wait for finished
    await wait_for_finished(jp_fetch, kernel_id, ipynb_path, cell_id)

    outputs = [{'name': 'stdout', 'output_type': 'stream', 'text': 'hello\n'},
               {'name': 'stdout', 'output_type': 'stream', 'text': 'world\n'}]
    assert_ipynb_cell_outputs(real_path, cell_id, outputs)


async def test_execute_code(jp_fetch):
    # will block and execute code, response result of the code
    kernel_response = await jp_fetch('api', 'kernels', method='POST', body=json.dumps({
        'name': 'python3',
        'path': 'NotExist.ipynb'
    }))
    kernel_id = json.loads(kernel_response.body)['id']

    body = {
        "code": "print('hello world')"
    }

    response = await jp_fetch('api', 'kernels', kernel_id, 'execute', method='POST', body=json.dumps(body))

    assert response.code == 200
    payload = json.loads(response.body)
    assert payload == {'code': "print('hello world')",
                       'outputs': [{'output_type': 'stream', 'name': 'stdout', 'text': 'hello world\n'}],
                       'execution_count': 1}


if __name__ == '__main__':
    pytest.main()
