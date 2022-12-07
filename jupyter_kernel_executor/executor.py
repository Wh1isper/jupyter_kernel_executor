import asyncio
from concurrent.futures import Future
from datetime import datetime
from uuid import uuid4

from jupyter_client.session import Session
from jupyter_server.base.handlers import log
from jupyter_server.services.kernels.kernelmanager import MappingKernelManager
from tornado import gen
from tornado.ioloop import IOLoop


def _ensure_future(f):
    """Wrap a concurrent future as an asyncio future if there is a running loop."""
    try:
        asyncio.get_running_loop()
        return asyncio.wrap_future(f)
    except RuntimeError:
        return f


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class ExecutorManager(object, metaclass=Singleton):
    def __init__(self, kernel_manager: MappingKernelManager, config):
        self.km = kernel_manager
        self.config = config
        self.result = dict()

        self.session = Session(config=self.config)
        self.session_id = str(uuid4())

    @property
    def log(self):
        """use the Jupyter log by default, falling back on tornado's logger"""
        return log()

    async def execute(self, kernel_id, code, block=False):
        self.on_start(kernel_id)

        task = await self.execute_code(kernel_id, code)
        # task.add_done_callback(self.on_done(kernel_id))
        if block:
            await asyncio.wait_for(task, None)

    async def execute_code(self, kernel_id, code) -> asyncio.Task:
        channels = self.create_stream(kernel_id)

        shell_channel = channels['shell']
        control_channel = channels['control']
        iopub_channel = channels["iopub"]

        def on_shell_reply(stream, msg_list):
            idents, fed_msg_list = self.session.feed_identities(msg_list)
            msg = self.session.deserialize(fed_msg_list)
            self.log.info(f"On shell reply:{stream}, {msg}")

        def on_iopub_reply(stream, msg_list):
            idents, fed_msg_list = self.session.feed_identities(msg_list)
            msg = self.session.deserialize(fed_msg_list)
            self.log.info(f"On iopub reply:{stream}, {msg}")

        def on_control_reply(stream, msg_list):
            idents, fed_msg_list = self.session.feed_identities(msg_list)
            msg = self.session.deserialize(fed_msg_list)
            self.log.info(f"On control reply:{stream}, {msg}")

        msg = {
            "buffers": [],
            "content": {
                "silent": False,
                "store_history": True,
                "user_expressions": {},
                "allow_stdin": True,
                "stop_on_error": True,
                "code": code,
            },
            "header": {
                "date": datetime.utcnow().isoformat() + "Z",
                "msg_id": f"{uuid4()}",
                "msg_type": "execute_request",
                "session": self.session_id,
                "username": "",
                "version": "5.2"
            },
            "metadata": {},
            "parent_header": {}
        }

        shell_channel.on_recv_stream(on_shell_reply)
        iopub_channel.on_recv_stream(on_iopub_reply)
        control_channel.on_recv_stream(on_control_reply)
        identity = self.session.bsession
        self.session.send(shell_channel, msg, ident=identity)

        await asyncio.sleep(10)

    def on_start(self, kernel_id):
        self.km.notify_connect(kernel_id)

    def on_done(self, kernel_id):
        def _():
            self.km.notify_disconnect(kernel_id)

        return _

    def create_stream(self, kernel_id):
        channels = dict()
        identity = self.session.bsession

        for channel in ("iopub", "shell", "control", "stdin"):
            meth = getattr(self.km, "connect_" + channel)
            channels[channel] = stream = meth(kernel_id, identity=identity)
            stream.channel = channel
        return channels
