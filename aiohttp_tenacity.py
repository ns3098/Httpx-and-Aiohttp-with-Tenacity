import asyncio
import logging
import dataclasses
from types import TracebackType
from typing import (
    AsyncContextManager,
    Callable,
    Optional,
    Type,
    TypeVar,
    Union,
)
import aiohttp
import tenacity


logger = logging.getLogger("tenacity")


T = TypeVar("T")


class asyncnullcontext(AsyncContextManager[T]):
    """Asynchronous version of 'contextlib.nullcontext'."""

    def __init__(self, aenter_result: T) -> None:
        self._aenter_result = aenter_result

    async def __aenter__(self) -> T:
        return self._aenter_result

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        return None

@dataclasses.dataclass
class RetryConfiguration:
    retry_attempts: int
    max_retry_period_seconds: float = 1



class TenacityAiohttp:

    def __init__(self, urls, method, headers, cookies, data, handle_httpstatus_list, retries, use_proxy, client_session: Optional[aiohttp.ClientSession] = None):

        self.method, self.headers, self.cookies, self.data = method, headers, cookies, data
        self.urls = [urls] if isinstance(urls, str) else urls
        self.proxy, self.proxy_auth = 'http://X.X.X.X:Y' if use_proxy else None, 'password' if use_proxy else None
        self.responses, self.retries, self.handle_httpstatus_list = [], retries, [200] + handle_httpstatus_list
        self.client_session = client_session

    async def collect(self, url, session):
        # if headers is None:
        #     headers = {}
        # headers['Host'] = f"{urlparse(url).hostname}:443"
        response = await session.request(self.method, url, headers=self.headers, cookies=self.cookies,
                        proxy=self.proxy, proxy_auth=self.proxy_auth, data=self.data, timeout=10)
        if response.status in self.handle_httpstatus_list:
            return await response.read()
        response.raise_for_status()
                
    async def upload(self, url):
        config = RetryConfiguration(**{'retry_attempts': self.retries})
        retrying_create = self._make_retrying("Async request", config)
        try:
            ctx: Union[aiohttp.ClientSession, AsyncContextManager[aiohttp.ClientSession]]
            if self.client_session is None:
                ctx = aiohttp.ClientSession()
            else:
                ctx = asyncnullcontext(self.client_session)
            async with ctx as session:
                response = await retrying_create.call(
                    self.collect,
                    url,
                    session
                )

                return response
        except asyncio.CancelledError:  # pragma: no cover
            raise
        except tenacity.RetryError as e:
            logger.error(
                f"Unable to complete request, even after retrying: {e.last_attempt.exception()}"
            )
        except Exception as e:
            logger.error(f"Unable to complete request: {e}")

        return None

    def _make_log_before_function(self, s: str) -> Callable[[tenacity.RetryCallState], None]:
        def log(retry_state: tenacity.RetryCallState) -> None:
            if retry_state.attempt_number > 1:
                logger.info(f"Trying {s} again, attempt number {retry_state.attempt_number}...")
        return log

    def _make_log_before_sleep_function(self, s: str,) -> Callable[[tenacity.RetryCallState], None]:
        def log(retry_state: tenacity.RetryCallState) -> None:
            if (retry_state.next_action is not None) and (retry_state.outcome is not None):
                duration = retry_state.next_action.sleep
                if retry_state.outcome.failed:
                    value = retry_state.outcome.exception()
                else:
                    value = retry_state.outcome.result()
                logger.warning(
                    f"{s.capitalize()} failed, "
                    f"retrying in {duration:.0f} second(s): {value}"
                )

        return log


    def _make_retrying(self, s: str, config: RetryConfiguration) -> tenacity.AsyncRetrying:
        return tenacity.AsyncRetrying(
            retry=tenacity.retry_if_exception_type(aiohttp.ClientError),
            stop=tenacity.stop_after_attempt(config.retry_attempts),
            wait=tenacity.wait_exponential(max=config.max_retry_period_seconds),
            before=self._make_log_before_function(s),
            before_sleep=self._make_log_before_sleep_function(s),
        )

    async def launch(self):
        self.responses = await asyncio.gather(*map(self.upload, self.urls))


def make_request(urls, method='GET', headers=None, cookies=None, data=None, handle_httpstatus_list=[], retries=6, use_proxy=False):
    cls = TenacityAiohttp(urls, method, headers, cookies, data, handle_httpstatus_list, retries, use_proxy)
    asyncio.run(cls.launch())
    return cls.responses




urls = ['https://www.google.com/', 'https://wideo.co/']

responses = make_request(urls)
print(responses)