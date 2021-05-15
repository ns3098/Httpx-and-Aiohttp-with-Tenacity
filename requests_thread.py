from functools import partial
import traceback

try:
    import gevent
    from gevent import monkey
    from gevent.pool import Pool
except ImportError:
    raise RuntimeError('Gevent is required')


monkey.patch_all(thread=False, select=False)

from requests import Session



class AsyncRequest(object):
   
    def __init__(self, method, url, **kwargs):
 
        self.method = method
       
        self.url = url
  
        self.session = kwargs.pop('session', None)

        if self.session is None:
            self.session = Session()
            self._close = True
        else:
            self._close = False 

        callback = kwargs.pop('callback', None)
        if callback:
            kwargs['hooks'] = {'response': callback}

        self.kwargs = kwargs
  
        self.response = None

    def send(self, **kwargs):
        
        merged_kwargs = {}
        merged_kwargs.update(self.kwargs)
        merged_kwargs.update(kwargs)
        try:
            self.response = self.session.request(self.method,
                                                self.url, **merged_kwargs)
        except Exception as e:
            self.exception = e
            self.traceback = traceback.format_exc()
        finally:
            if self._close:
                self.session.close()
        return self


def send(r, pool=None, stream=False):

    if pool is not None:
        return pool.spawn(r.send, stream=stream)

    return gevent.spawn(r.send, stream=stream)


def request(method, url, **kwargs):
    return AsyncRequest(method, url, **kwargs)


def imap(requests, stream=False, size=2, exception_handler=None):

    pool = Pool(size)

    def send(r):
        return r.send(stream=stream)

    for request in pool.imap_unordered(send, requests):
        if request.response is not None:
            yield request.response
        elif exception_handler:
            ex_result = exception_handler(request, request.exception)
            if ex_result is not None:
                yield ex_result

    pool.join()