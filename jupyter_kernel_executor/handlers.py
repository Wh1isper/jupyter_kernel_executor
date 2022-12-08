import asyncio
import json
from typing import Optional

import tornado.web
from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import ensure_async

from jupyter_kernel_client.client import KernelWebsocketClient


class ExecuteCellHandler(APIHandler):
    executing_cell = dict()

    @property
    def file_id_manager(self):
        return self.settings.get("file_id_manager")

    def get_path(self, document_id):
        if not document_id:
            return None

        if self.file_id_manager:
            # Compatible with the case where document_id not found
            path = self.file_id_manager.get_path(document_id) or document_id
        else:
            path = document_id
        return path

    def get_document_id(self, path):
        if not path:
            return None

        if self.file_id_manager:
            # Compatible with the case where document_id not found
            document_id = self.file_id_manager.get_id(path) or path
        else:
            document_id = path
        return document_id

    @tornado.web.authenticated
    async def get(self, kernel_id):
        records = self.executing_cell.get(kernel_id, [])

        response = [
            {
                "path": self.get_path(record['document_id']),
                "cell_id": record['cell_id'],
            } for record in records
        ]

        await self.finish(json.dumps(
            response
        ))

    def is_executing(self, kernel_id, document_id, cell_id):
        return self.get_record(document_id, cell_id) in self.executing_cell.get(kernel_id, [])

    @tornado.web.authenticated
    async def post(self, kernel_id):
        """
        Json Body Required:
            path(str): file path
            cell_id(str):  cell to be executed
            OR
            code(str): just execute the code here

        Optional:
            block(bool): execute code sync or not, when path and cell_id available, default to False(not block)
                         or True(execute code sync), when block is True, response result
            not_write(bool): default to False,False means try to write result to document's cell

        """
        model = self.get_json_body()
        path = model.get('path')
        cell_id = model.get('cell_id')
        not_write = model.get('not_write', False)
        document_id = self.get_document_id(path)
        if self.is_executing(kernel_id, document_id, cell_id):
            self.log.info(f'cell {cell_id} of {path}(id:{document_id}) is executing')
            return await self.finish(json.dumps(
                model
            ))

        if model.get('block'):
            # from request, respect it
            # when not_write=True and block=False, means to execute code or cell silently
            block = model.get('block')
        elif not document_id or not cell_id:
            # no file or cell to write, need to response result
            block = True
        else:
            block = False

        client = KernelWebsocketClient(
            kernel_id=kernel_id,
            port=self.serverapp.port,
            base_url=self.base_url,
            token=self.token,
            encoded=True,
        )
        code = model.get('code') or await self.read_code_from_ipynb(
            document_id,
            cell_id,
        )
        assert code is not None

        if not block:
            self.log.debug("async execute code, write result to file")

            async def write_callback():
                await self.write_output(document_id, cell_id, client.get_result())

            if not not_write:
                client.register_callback(write_callback)
            await self.finish(json.dumps(
                model
            ))
            await self.execute(client, code, document_id, cell_id)
        else:
            self.log.debug("sync execute code, return execution result in response")
            result = await self.execute(client, code, document_id, cell_id)
            if not not_write:
                await self.write_output(document_id, cell_id, result)
            await self.finish(json.dumps({
                **model,
                **result
            }))

    async def execute(self, client, code, document_id, cell_id):
        kernel_id = client.kernel_id
        await self.pre_execute(kernel_id, document_id, cell_id)
        result = await client.execute(code)
        await self.post_execute(result, kernel_id, document_id, cell_id)
        return result

    async def pre_execute(self, kernel_id, document_id, cell_id):
        self.executing_cell.setdefault(kernel_id, []).append(
            self.get_record(document_id, cell_id)
        )

    async def post_execute(self, result, kernel_id, document_id, cell_id):
        if not (document_id and cell_id):
            return
        records = self.executing_cell.get(kernel_id, [])
        record = self.get_record(document_id, cell_id)
        if record in records:
            records.remove(record)

    def get_record(self, document_id, cell_id):
        return {
            'document_id': document_id,
            'cell_id': cell_id
        }

    async def read_code_from_ipynb(self, document_id, cell_id) -> Optional[str]:
        if not document_id or not cell_id:
            return None
        cm = self.contents_manager
        path = self.get_path(document_id)
        model = await ensure_async(cm.get(path, content=True, type='notebook'))
        nb = model['content']
        for cell in nb['cells']:
            if cell['id'] == cell_id:
                return cell['source']
        raise tornado.web.HTTPError(404, f"cell {cell_id} not found in {path}")

    async def write_output(self, document_id, cell_id, result):
        # todo add some timeout and interval prevent update too frequently
        if not document_id or not cell_id:
            return
        cm = self.contents_manager
        path = self.get_path(document_id)
        model = await ensure_async(cm.get(path, content=True, type='notebook'))
        nb = model['content']
        updated = False
        for cell in nb['cells']:
            if cell['id'] == cell_id:
                if result['outputs'] != cell["outputs"]:
                    cell["outputs"] = result['outputs']
                    updated = True
                if result['execution_count']:
                    cell['execution_count'] = int(result['execution_count'])
                    updated = True
                break
        if updated:
            await ensure_async(cm.save(model, path))


def setup_handlers(web_app):
    host_pattern = ".*$"

    base_url = web_app.settings["base_url"].rstrip('/')
    _kernel_id_regex = r"(?P<kernel_id>\w+-\w+-\w+-\w+-\w+)"
    handlers = [
        (rf"{base_url}/api/kernels/{_kernel_id_regex}/execute", ExecuteCellHandler),
    ]
    web_app.add_handlers(host_pattern, handlers)
