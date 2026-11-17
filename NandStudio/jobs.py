"""Bounded latest-request worker. No Tk calls are made outside the main thread."""
from concurrent.futures import ThreadPoolExecutor


class LatestWorker:
    def __init__(self):
        self.pool=ThreadPoolExecutor(max_workers=1)
        self.version=0;self.future=None;self.pending=None;self.active=0;self.closed=False

    def submit(self,fn):
        self.version+=1
        self.pending=(self.version,fn)
        if self.future is None:self._start()
        return self.version

    def _start(self):
        if self.pending is None or self.closed:return
        self.active,fn=self.pending;self.pending=None;self.future=self.pool.submit(fn)

    def poll(self):
        if self.future is None or not self.future.done():return None
        version=self.active
        try:result=self.future.result();error=None
        except Exception as exc:result=None;error=exc
        self.future=None
        self._start()
        if version!=self.version:return None
        return version,result,error

    def close(self):
        self.closed=True;self.pending=None;self.pool.shutdown(wait=False,cancel_futures=True)

    def invalidate(self):
        self.version+=1;self.pending=None
