from __future__ import annotations
import os
import time
import json
import logging
import threading
import heapq
import sqlite_utils
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import msgpack
import gzip

logger = logging.getLogger(__name__)

@dataclass
class MemoryToken:
    """A single memory token with embedding and metadata."""
    id: str
    text: str
    embedding: np.ndarray
    task_root: str  # Namespace for task isolation
    agent_id: str
    meta: Dict[str, Any] = field(default_factory=dict)
    size: int = field(init=False)  # token count estimate
    atime: float = field(default_factory=time.time)  # access time for LRU
    refs: List[str] = field(default_factory=list)  # references to other tokens
    
    def __post_init__(self):
        self.size = len(self.text.split())  # rough token count
    
    def to_bytes(self) -> bytes:
        """Serialize token for storage."""
        return msgpack.packb({
            'id': self.id,
            'text': self.text,
            'embedding': self.embedding.tobytes(),
            'embedding_shape': self.embedding.shape,
            'task_root': self.task_root,
            'agent_id': self.agent_id,
            'meta': self.meta,
            'size': self.size,
            'atime': self.atime,
            'refs': self.refs
        })
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'MemoryToken':
        """Deserialize token from storage."""
        unpacked = msgpack.unpackb(data)
        embedding = np.frombuffer(unpacked['embedding'], dtype=np.float32)
        embedding = embedding.reshape(unpacked['embedding_shape'])
        
        token = cls(
            id=unpacked['id'],
            text=unpacked['text'],
            embedding=embedding,
            task_root=unpacked['task_root'],
            agent_id=unpacked['agent_id'],
            meta=unpacked['meta']
        )
        token.size = unpacked['size']
        token.atime = unpacked['atime']
        token.refs = unpacked['refs']
        return token

class STM:
    """
    Short-Term Memory: RAM-resident memory store with 5GB capacity.
    Implements task-based isolation and intelligent eviction to LTM.
    """
    _instance = None
    
    def __new__(cls, max_bytes: int = 5_000_000_000):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init(max_bytes)
        return cls._instance
    
    def _init(self, max_bytes: int):
        self.max_bytes = max_bytes
        self.used_bytes = 0
        self.tokens: Dict[str, MemoryToken] = {}
        self.lru: List[Tuple[float, str]] = []  # (atime, token_id) for eviction
        self.task_indices: Dict[str, set[str]] = {}  # task_root -> set of token_ids
        self.agent_indices: Dict[str, set[str]] = {}  # agent_id -> set of token_ids
        self.lock = threading.RLock()
        
        # Initialize LTM connection
        data_dir = Path(os.environ.get("DEXTER_DATA_DIR", "./data"))
        self.ltm = sqlite_utils.Database(data_dir / "brain.db")
        self._init_ltm_tables()
        
        # Load snapshot if exists
        self._load_snapshot()
        
        logger.info(f"STM initialized with {max_bytes / 1e9:.1f} GB capacity")
    
    def _init_ltm_tables(self):
        """Initialize long-term memory tables."""
        self.ltm["ltm_tokens"].create({
            "id": str,
            "text": str,
            "embedding": bytes,
            "task_root": str,
            "agent_id": str,
            "meta": str,
            "size": int,
            "atime": float,
            "refs": str
        }, pk="id", if_not_exists=True)
        
        self.ltm["ltm_tokens"].create_index(["task_root"], if_not_exists=True)
        self.ltm["ltm_tokens"].create_index(["agent_id"], if_not_exists=True)
        self.ltm["ltm_tokens"].create_index(["atime"], if_not_exists=True)
    
    def add(self, token: MemoryToken) -> None:
        """Add a token to STM."""
        with self.lock:
            # Check if we need to evict
            token_size = token.embedding.nbytes + len(token.text.encode('utf-8'))
            while self.used_bytes + token_size > self.max_bytes and self.lru:
                self._evict_one()
            
            # Add token
            self.tokens[token.id] = token
            self.used_bytes += token_size
            
            # Update indices
            if token.task_root not in self.task_indices:
                self.task_indices[token.task_root] = set()
            self.task_indices[token.task_root].add(token.id)
            
            if token.agent_id not in self.agent_indices:
                self.agent_indices[token.agent_id] = set()
            self.agent_indices[token.agent_id].add(token.id)
            
            # Update LRU
            heapq.heappush(self.lru, (token.atime, token.id))
            
            logger.debug(f"Added token {token.id} to STM (task: {token.task_root})")
    
    def get(self, token_id: str) -> Optional[MemoryToken]:
        """Get a token by ID."""
        with self.lock:
            token = self.tokens.get(token_id)
            if token:
                token.atime = time.time()
            return token
    
    def query(self, embedding: np.ndarray, task_root: Optional[str] = None, 
              agent_id: Optional[str] = None, top_k: int = 20) -> List[MemoryToken]:
        """
        Query tokens by embedding similarity with task/agent filtering.
        """
        with self.lock:
            candidates = []
            
            # Filter by task_root if specified
            if task_root:
                token_ids = self.task_indices.get(task_root, set())
                candidates = [self.tokens[tid] for tid in token_ids if tid in self.tokens]
            # Filter by agent_id if specified
            elif agent_id:
                token_ids = self.agent_indices.get(agent_id, set())
                candidates = [self.tokens[tid] for tid in token_ids if tid in self.tokens]
            else:
                candidates = list(self.tokens.values())
            
            # Compute similarities
            scored = []
            for token in candidates:
                similarity = np.dot(embedding, token.embedding) / (
                    np.linalg.norm(embedding) * np.linalg.norm(token.embedding)
                )
                scored.append((similarity, token))
            
            # Sort by similarity and return top k
            scored.sort(reverse=True)
            return [token for _, token in scored[:top_k]]
    
    def get_task_context(self, task_root: str, max_tokens: int = 1000) -> List[MemoryToken]:
        """Get all tokens for a specific task."""
        with self.lock:
            token_ids = self.task_indices.get(task_root, set())
            tokens = [self.tokens[tid] for tid in token_ids if tid in self.tokens]
            # Sort by access time (most recent first)
            tokens.sort(key=lambda t: t.atime, reverse=True)
            return tokens[:max_tokens]
    
    def _evict_one(self) -> None:
        """Evict the least recently used token."""
        while self.lru:
            atime, token_id = heapq.heappop(self.lru)
            token = self.tokens.pop(token_id, None)
            if token:
                # Remove from indices
                self.task_indices[token.task_root].discard(token_id)
                if not self.task_indices[token.task_root]:
                    del self.task_indices[token.task_root]
                
                self.agent_indices[token.agent_id].discard(token_id)
                if not self.agent_indices[token.agent_id]:
                    del self.agent_indices[token.agent_id]
                
                # Update memory usage
                token_size = token.embedding.nbytes + len(token.text.encode('utf-8'))
                self.used_bytes -= token_size
                
                # Persist to LTM
                self._persist_to_ltm(token)
                
                logger.debug(f"Evicted token {token_id} to LTM")
                break
    
    def _persist_to_ltm(self, token: MemoryToken) -> None:
        """Persist token to long-term memory."""
        self.ltm["ltm_tokens"].insert({
            "id": token.id,
            "text": token.text,
            "embedding": token.embedding.tobytes(),
            "task_root": token.task_root,
            "agent_id": token.agent_id,
            "meta": json.dumps(token.meta),
            "size": token.size,
            "atime": token.atime,
            "refs": json.dumps(token.refs)
        }, replace=True)
    
    def _load_snapshot(self) -> None:
        """Load STM snapshot if exists."""
        snapshot_path = Path(os.environ.get("DEXTER_DATA_DIR", "./data")) / "stm_snapshot.msgpack.gz"
        if snapshot_path.exists():
            try:
                with gzip.open(snapshot_path, 'rb') as f:
                    data = msgpack.unpackb(f.read())
                
                for token_data in data.get('tokens', []):
                    token = MemoryToken.from_bytes(token_data)
                    self.add(token)
                
                logger.info(f"Loaded STM snapshot with {len(data.get('tokens', []))} tokens")
            except Exception as e:
                logger.error(f"Failed to load STM snapshot: {e}")
    
    def create_snapshot(self) -> None:
        """Create a snapshot of current STM state."""
        with self.lock:
            snapshot_path = Path(os.environ.get("DEXTER_DATA_DIR", "./data")) / "stm_snapshot.msgpack.gz"
            
            data = {
                'timestamp': time.time(),
                'token_count': len(self.tokens),
                'used_bytes': self.used_bytes,
                'tokens': [token.to_bytes() for token in self.tokens.values()]
            }
            
            with gzip.open(snapshot_path, 'wb') as f:
                f.write(msgpack.packb(data))
            
            logger.info(f"Created STM snapshot with {len(self.tokens)} tokens")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get STM statistics."""
        with self.lock:
            return {
                'token_count': len(self.tokens),
                'used_bytes': self.used_bytes,
                'max_bytes': self.max_bytes,
                'usage_percent': (self.used_bytes / self.max_bytes) * 100,
                'task_count': len(self.task_indices),
                'agent_count': len(self.agent_indices)
            }

class LTM:
    """Long-Term Memory: Disk-based storage for evicted tokens."""
    
    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            data_dir = Path(os.environ.get("DEXTER_DATA_DIR", "./data"))
            db_path = data_dir / "brain.db"
        
        self.db = sqlite_utils.Database(db_path)
        self._init_tables()
    
    def _init_tables(self):
        """Initialize LTM tables."""
        self.db["ltm_tokens"].create({
            "id": str,
            "text": str,
            "embedding": bytes,
            "task_root": str,
            "agent_id": str,
            "meta": str,
            "size": int,
            "atime": float,
            "refs": str
        }, pk="id", if_not_exists=True)
        
        # Create indexes
        self.db["ltm_tokens"].create_index(["task_root"], if_not_exists=True)
        self.db["ltm_tokens"].create_index(["agent_id"], if_not_exists=True)
        self.db["ltm_tokens"].create_index(["atime"], if_not_exists=True)
    
    def query(self, embedding: np.ndarray, task_root: Optional[str] = None,
              agent_id: Optional[str] = None, top_k: int = 20) -> List[MemoryToken]:
        """Query LTM tokens by similarity."""
        where_clause = []
        params = []
        
        if task_root:
            where_clause.append("task_root = ?")
            params.append(task_root)
        
        if agent_id:
            where_clause.append("agent_id = ?")
            params.append(agent_id)
        
        where_str = " AND ".join(where_clause) if where_clause else "1=1"
        
        rows = list(self.db["ltm_tokens"].rows_where(
            where_str,
            params,
            order_by="atime DESC",
            limit=top_k * 10  # Get more candidates for similarity filtering
        ))
        
        # Convert to tokens and compute similarities
        tokens = []
        for row in rows:
            token = MemoryToken(
                id=row["id"],
                text=row["text"],
                embedding=np.frombuffer(row["embedding"], dtype=np.float32),
                task_root=row["task_root"],
                agent_id=row["agent_id"],
                meta=json.loads(row["meta"])
            )
            token.size = row["size"]
            token.atime = row["atime"]
            token.refs = json.loads(row["refs"])
            tokens.append(token)
        
        # Compute similarities and sort
        scored = []
        for token in tokens:
            similarity = np.dot(embedding, token.embedding) / (
                np.linalg.norm(embedding) * np.linalg.norm(token.embedding)
            )
            scored.append((similarity, token))
        
        scored.sort(reverse=True)
        return [token for _, token in scored[:top_k]]
    
    def cleanup_old(self, days: int = 30) -> int:
        """Clean up tokens older than specified days."""
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        
        result = self.db.execute(
            "DELETE FROM ltm_tokens WHERE atime < ?",
            [cutoff_time]
        )
        
        deleted_count = result.rowcount
        logger.info(f"Cleaned up {deleted_count} old LTM tokens")
        return deleted_count
