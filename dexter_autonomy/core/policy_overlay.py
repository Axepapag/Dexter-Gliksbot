from __future__ import annotations
from typing import Dict, Any, Tuple
import fnmatch, re
import html

class CompositeDenyPolicy:
    def __init__(self, profile: Dict[str, Any], overlay: Dict[str, Any] | None = None):
        self.p = profile or {}; self.o = overlay or {}
        # Common injection patterns
        self.injection_patterns = [
            r"(?i)(union|select|insert|update|delete|drop|create|alter|exec|execute)",
            r"(?i)(<script|javascript:|vbscript:|onload|onerror)",
            r"(?i)(\b(0x[0-9a-f]+|\d+e\d+|\d+'\s*(or|and)\s*'?\d+))",
        ]

    def _merge(self,a,b,k): return list(a.get(k, [])) + list(b.get(k, []))
    
    def allow_process(self, cmd: str):
        pats = self._merge(self.p.get("process",{}), self.o.get("process",{}), "deny_cmd_patterns")
        return (not any(fnmatch.fnmatch(cmd,g) for g in pats), "process denied")
    
    def allow_path(self, path: str, write=False):
        p,o = self.p.get("files",{}), self.o.get("files",{})
        globs = self._merge(p,o, "deny_write_globs" if write else "deny_read_globs")
        if any(fnmatch.fnmatch(path,g) for g in globs): return False, "path denied"
        for d in self._merge(p,o,"deny_dirs"):
            if str(path).startswith(str(d)): return False, "dir denied"
        return True, ""
    
    def allow_url(self, url: str):
        for r in self._merge(self.p.get("network",{}), self.o.get("network",{}), "deny_url_regex"):
            if re.search(r,url): return False,"url denied"
        for h in self._merge(self.p.get("network",{}), self.o.get("network",{}), "deny_hosts"):
            if h in url: return False,"host denied"
        return True, ""
    
    def allow_hotkey(self, chord: str):
        for x in self._merge(self.p.get("hotkeys",{}), self.o.get("hotkeys",{}), "deny"):
            if x.upper()==chord.upper(): return False, "hotkey denied"
        return True, ""
    
    def allow_input(self, text: str):
        p,o = self.p.get("input",{}), self.o.get("input",{})
        max_chars = max(int(p.get("max_chars",0) or 0), int(o.get("max_chars",0) or 0))
        if max_chars and len(text)>max_chars: return False, "too long"
        for r in self._merge(p,o, "deny_regex"):
            if re.search(r,text): return False, "content denied"
        
        # Additional injection detection
        clean_text = html.unescape(text.strip().lower())
        for pattern in self.injection_patterns:
            if re.search(pattern, clean_text):
                return False, "potential injection detected"
        return True, ""
