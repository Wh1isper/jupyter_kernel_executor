import asyncio
import json
import os
from typing import Optional, Dict, List
from datetime import datetime

import tornado.web
from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import ensure_async
from watchfiles import awatch, Change

from jupyter_kernel_client.client import KernelWebsocketClient
from jupyter_kernel_executor.file_watcher import FileWatcher
from jupyter_kernel_executor.fileid import FileIDWrapper


class ExecuteCellHandler(APIHandler):
    executing_cell: Dict[str, List[
        Dict[str, str]]
    ] = dict()
    save_lock = asyncio.Lock()

    def initialize(self):
        self.execution_start_datetime: Optional[datetime] = None
        self.execution_end_datetime: Optional[datetime] = None
        self.watch_dir = self.normal_path(self.serverapp.root_dir or '.')
        self.global_watcher = FileWatcher(self.file_id_manager)

    def finish(self, *args, **kwargs):
        return super().finish(*args, **kwargs)

    @property
    def file_id_manager(self) -> FileIDWrapper:
        return FileIDWrapper(self.settings.get("file_id_manager"), self.save_lock)

    def normal_path(self, path):
        return self.file_id_manager.normalize_path(path)

    def index(self, path):
        return self.file_id_manager.index(path)

    async def get_path(self, document_id):
        return await self.file_id_manager.get_path(document_id)

    def get_document_id(self, path):
        return self.file_id_manager.get_id(path)

    def get_request_auth(self):
        auth_in_header = self.request.headers.get('Authorization')
        return {
            'Authorization': auth_in_header
        } if auth_in_header else dict()

    def get_auth_header(self):
        # v2 using identity_provider for token
        provider = getattr(self, "identity_provider", self.serverapp)

        return {"Authorization": f"token {provider.token}"}

    @tornado.web.authenticated
    async def get(self, kernel_id):
        if not self.kernel_manager.get_kernel(kernel_id):
            raise tornado.web.HTTPError(404, f"No such kernel {kernel_id}")

        records = self.executing_cell.get(kernel_id, [])
        response = [
            {
                "path": await self.get_path(record['document_id']),
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
            path(str): file path, When file_id_manager(jupyter_server_fileid) available,
                       tracking path's file id automatically for remove or some other actions

            cell_id(str):  cell to be executed
            OR
            code(str): just execute the code here

        Optional:
            block(bool): execute code sync or not, when path and cell_id available, default to False(not block)
                         or True(execute code sync), when block is True, response result
            not_write(bool): default to False, False means try to write result to document's cell

        """
        if not self.kernel_manager.get_kernel(kernel_id):
            raise tornado.web.HTTPError(404, f"No such kernel {kernel_id}")

        model = self.get_json_body()
        path = model.get('path')
        cell_id = model.get('cell_id')
        not_write = model.get('not_write', False)
        document_id = self.index(path)
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

        auth_header = self.get_request_auth()
        if not auth_header:
            # fallback using app setting, May not be compatible with jupyterhub-singleuser or other singleuser app
            auth_header = self.get_auth_header()

        client = KernelWebsocketClient(
            kernel_id=kernel_id,
            host=self.serverapp.ip,
            port=self.serverapp.port,
            base_url=self.base_url,
            auth_header=auth_header,
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
                try:
                    await self.write_output(document_id, cell_id, client.get_result())
                except Exception as e:
                    self.log.error('Exception when asynchronous writing result to file')
                    self.log.exception(e)

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
        try:
            result = await client.execute(code)
        finally:
            await self.post_execute(kernel_id, document_id, cell_id)
        self.log.debug(f'execute time: {self.execution_end_datetime - self.execution_start_datetime}')
        return result

    async def pre_execute(self, kernel_id, document_id, cell_id):
        if document_id and cell_id:
            self.executing_cell.setdefault(kernel_id, []).append(
                self.get_record(document_id, cell_id)
            )
            self.global_watcher.add(self)
            self.global_watcher.start_if_not(self.watch_dir)

        self.execution_start_datetime = datetime.now()

    async def post_execute(self, kernel_id, document_id, cell_id):
        self.execution_end_datetime = datetime.now()
        records = self.executing_cell.get(kernel_id, [])
        if document_id and cell_id:
            # prevent memory leak
            self.global_watcher.remove(self)
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
        path = await self.get_path(document_id)
        model = await ensure_async(cm.get(path, content=True, type='notebook'))
        nb = model['content']
        for cell in nb['cells']:
            if cell['id'] == cell_id:
                return cell['source']
        raise tornado.web.HTTPError(404, f"cell {cell_id} not found in {path}")

    async def write_output(self, document_id, cell_id, result):
        if not document_id or not cell_id:
            return
        cm = self.contents_manager
        path = await self.get_path(document_id)
        async with self.save_lock:
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
                self.file_id_manager.save(path)

    def executing_document(self):
        executing_document = []
        for kernel_records in self.executing_cell.values():
            for records in kernel_records:
                executing_document.append(records['document_id'])
        return executing_document


def setup_handlers(web_app):
    host_pattern = ".*$"

    base_url = web_app.settings["base_url"].rstrip('/')
    _kernel_id_regex = r"(?P<kernel_id>\w+-\w+-\w+-\w+-\w+)"
    handlers = [
        (rf"{base_url}/api/kernels/{_kernel_id_regex}/execute", ExecuteCellHandler),
    ]
    web_app.add_handlers(host_pattern, handlers)
