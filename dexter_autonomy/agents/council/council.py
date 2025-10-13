from __future__ import annotations
from . .adapters.ollama_adapter import OllamaClient
class Council:
    def __init__(self, model:str|None, host:str, temperature:float=0.2):
        self.ollama=OllamaClient(host) if model else None; self.model=model; self.temperature=temperature
    def round(self, goal:str, notes:str)->str:
        if not self.ollama: return f"PLAN: {goal}\n- Step 1\n- Step 2\nRISKS: Denylist"
        msg=[{"role":"system","content":"You are a terse planner."},{"role":"user","content":f"Goal: {goal}\nNotes: {notes}"}]
        return self.ollama.chat(self.model, msg, self.temperature)
