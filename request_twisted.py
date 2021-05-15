import inspect

from twisted.internet import threads
from twisted.internet.defer import ensureDeferred
from twisted.internet.error import ReactorAlreadyInstalledError
from twisted.internet import task

from requests import Session

class AsyncSession(Session):
    
    def __init__(self, n=None, reactor=None, loop=None, *args, **kwargs):
        if reactor is None:
            try:
                import asyncio
                loop = loop or asyncio.get_event_loop()
                try:
                    from twisted.internet import asyncioreactor
                    asyncioreactor.install(loop)
                except (ReactorAlreadyInstalledError, ImportError):
                    pass
            except ImportError:
                pass
            if n:
                from twisted.internet import reactor
                pool = reactor.getThreadPool()
                pool.adjustPoolsize(0, n)

        super(AsyncSession, self).__init__(*args, **kwargs)

    def request(self, *args, **kwargs):
        func = super(AsyncSession, self).request
        return threads.deferToThread(func, *args, **kwargs)

    def wrap(self, *args, **kwargs):
        return ensureDeferred(*args, **kwargs)

    def run(self, f):
        if hasattr(inspect, 'iscoroutinefunction'):
            if inspect.iscoroutinefunction(f):
                def w(reactor):
                    return self.wrap(f())    
                return task.react(w)
        else:
            return task.react(f)