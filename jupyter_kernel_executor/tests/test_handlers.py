import os
from pathlib import Path

import pytest

_here = Path(os.path.abspath(os.path.dirname(__file__)))
INTERVAL = 1
str_code = '''
import time
print('hello')
time.sleep(1)
print('world')
'''

list_code = [line + '\n' for line in str_code.split('\n')]


@pytest.fixture(name='ipynb', params=(list_code,))
def _ipynb(request, jp_root_dir):
    code = request.param
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
    await assert_ipynb_cell_outputs(real_path, cell_id, outputs)


async def test_execute_cell_abspath(jp_fetch, ipynb):
    ipynb_path, cell_id, real_path = ipynb
    ipynb_path = '/' + ipynb_path
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
    await assert_ipynb_cell_outputs(real_path, cell_id, outputs)


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
