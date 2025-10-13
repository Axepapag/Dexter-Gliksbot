from __future__ import annotations
import sqlite3, time, json, os
from typing import Any, Dict, List
class BrainDB:
    def __init__(self, db_path: str = "./data/brain.db"):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self._init()
    def _init(self):
        c = self.db.cursor(); c.execute("PRAGMA journal_mode=WAL;")
        c.execute("CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, kind TEXT, content TEXT, meta TEXT, ts REAL)")
        c.execute("CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(content, content='memories', content_rowid='id')")
        c.execute("CREATE TABLE IF NOT EXISTS edges(id INTEGER PRIMARY KEY, src INTEGER, rel TEXT, dst INTEGER, ts REAL)")
        self.db.commit()
    def add_memory(self, kind: str, content: str, meta: Dict[str, Any] | None = None,
                   task_root: str = "default", agent_id: str = "system") -> int:
        ts=time.time(); cur=self.db.cursor(); cur.execute("INSERT INTO memories(kind,content,meta,ts) VALUES (?,?,?,?)",(kind,content,json.dumps(meta or {}),ts)); mid=cur.lastrowid
        cur.execute("INSERT INTO memories_fts(rowid,content) VALUES (?,?)",(mid,content)); self.db.commit(); return mid
    def search(self, query: str, k: int = 10) -> List[Dict[str, Any]]:
        cur=self.db.cursor(); cur.execute("SELECT rowid FROM memories_fts WHERE memories_fts MATCH ? LIMIT ?",(query,k)); ids=[r[0] for r in cur.fetchall()]
        out=[]
        for i in ids:
            kind,content,meta,ts=self.db.execute("SELECT kind,content,meta,ts FROM memories WHERE id=?",(i,)).fetchone()
            out.append({"id":i,"kind":kind,"content":content,"meta":json.loads(meta or "{}"),"ts":ts})
        return out
    def add_edge(self, src:int, rel:str, dst:int):
        self.db.execute("INSERT INTO edges(src,rel,dst,ts) VALUES (?,?,?,?)",(src,rel,dst,time.time())); self.db.commit()
