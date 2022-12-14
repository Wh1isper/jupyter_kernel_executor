import asyncio
import os
import json
from pathlib import Path
from uuid import uuid4

import nbformat

_here = Path(os.path.abspath(os.path.dirname(__file__)))
INTERVAL = 1


async def assert_ipynb_cell_outputs(real_path, cell_id, outputs):
    cell_output = None
    for _ in range(5):
        # pool for save file
        await asyncio.sleep(INTERVAL)
        with open(real_path) as f:
            nb = nbformat.read(f, as_version=nbformat.NO_CONVERT)
        for cell in nb['cells']:
            if cell['id'] == cell_id:
                cell_output = cell['outputs']
                try:
                    assert cell['outputs'] == outputs
                    return
                except:
                    pass
    assert cell_output == outputs


async def wait_for_finished(jp_fetch, kernel_id, path, cell_id):
    body = {
        "path": path,
        "cell_id": cell_id,
    }
    for _ in range(10):
        response = await jp_fetch('api', 'kernels', kernel_id, 'execute', method='GET')
        payload = json.loads(response.body)
        if body not in payload:
            break
        await asyncio.sleep(INTERVAL)
    else:
        raise TimeoutError('execute code timeout')


def rename_random(real_path):
    p = Path(real_path)
    random_name = f'{uuid4().hex}.ipynb'
    p = p.rename(p.parent / random_name)
    return p.as_posix()
