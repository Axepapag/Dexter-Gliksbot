from __future__ import annotations
import time
from ..tasks.registry import TaskRegistry
class TMS:
    def __init__(self, registry: TaskRegistry, default_mode:str="medium"):
        self.reg=registry; self.default_mode=default_mode
    def ensure_task(self, project:str, owner:str, mode:str|None=None):
        tid=f"{project}:{owner}"; self.reg.upsert({"id":tid,"project":project,"status":"active","mode":mode or self.default_mode,"owner":owner,"budget":0.0,"lease_until":time.time()+60,"next_run_at":time.time(),"context":"{}"}); return tid
