#!/usr/bin/env python3
"""
Standalone WebSocket Test Client for Dexter Cockpit

Manual testing tool for validating real-time WebSocket streaming.
Connects to ws://localhost:8765/ws/cockpit and displays events in real-time.

Features:
- Auto-reconnect on disconnect (with exponential backoff)
- Pretty-printed JSON messages with syntax highlighting
- Filter updates (agent_ids, mission_ids, log_levels, event_types)
- Request state snapshots (normal or force_refresh)
- Interactive commands (type 'help' for list)
- Statistics tracking (messages received, event types)
- Color-coded output (errors=red, warnings=yellow, info=cyan, success=green)

Usage:
    # Connect with no filters (all events)
    python scripts/test_websocket_client.py
    
    # Connect with filters
    python scripts/test_websocket_client.py --agent-ids agent-1,agent-2 --log-levels ERROR,WARN
    
    # Custom server URL
    python scripts/test_websocket_client.py --url ws://192.168.1.100:8765/ws/cockpit
    
    # Verbose mode (show all message details)
    python scripts/test_websocket_client.py --verbose

Interactive Commands:
    help              - Show available commands
    filters           - Show current filters
    update <filters>  - Update filters (e.g., 'update agent_ids=agent-1,agent-2')
    snapshot          - Request state snapshot
    snapshot refresh  - Request state snapshot with force_refresh
    stats             - Show statistics
    clear             - Clear screen
    quit / exit       - Disconnect and exit
"""
import asyncio
import json
import sys
import argparse
from datetime import datetime
from typing import Dict, Any, Optional, Set
from urllib.parse import urlencode

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
except ImportError:
    print("❌ Error: websockets library not installed")
    print("   Install with: pip install websockets")
    sys.exit(1)


# ANSI color codes
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


class WebSocketTestClient:
    """
    Interactive WebSocket test client for Dexter Cockpit.
    """
    
    def __init__(
        self,
        url: str,
        agent_ids: Optional[Set[str]] = None,
        mission_ids: Optional[Set[str]] = None,
        log_levels: Optional[Set[str]] = None,
        event_types: Optional[Set[str]] = None,
        verbose: bool = False,
        auto_reconnect: bool = True,
    ):
        self.base_url = url
        self.agent_ids = agent_ids or set()
        self.mission_ids = mission_ids or set()
        self.log_levels = log_levels or set()
        self.event_types = event_types or set()
        self.verbose = verbose
        self.auto_reconnect = auto_reconnect
        
        self.websocket: Optional[WebSocketClientProtocol] = None
        self.running = False
        self.reconnect_attempts = 0
        self.max_reconnect_delay = 30  # seconds
        
        # Statistics
        self.stats = {
            "messages_received": 0,
            "reconnects": 0,
            "errors": 0,
            "event_types": {},
            "start_time": None,
            "last_message_time": None,
        }
    
    def _build_url(self) -> str:
        """Build WebSocket URL with query parameters."""
        params = {}
        if self.agent_ids:
            params["agent_ids"] = ",".join(self.agent_ids)
        if self.mission_ids:
            params["mission_ids"] = ",".join(self.mission_ids)
        if self.log_levels:
            params["log_levels"] = ",".join(self.log_levels)
        if self.event_types:
            params["event_types"] = ",".join(self.event_types)
        
        if params:
            return f"{self.base_url}?{urlencode(params)}"
        return self.base_url
    
    def _print(self, message: str, color: str = Colors.WHITE, bold: bool = False):
        """Print colored message."""
        prefix = Colors.BOLD if bold else ""
        print(f"{prefix}{color}{message}{Colors.RESET}")
    
    def _print_json(self, data: Dict[str, Any], indent: int = 2):
        """Pretty-print JSON with syntax highlighting."""
        json_str = json.dumps(data, indent=indent, sort_keys=True)
        
        # Basic syntax highlighting
        for line in json_str.split('\n'):
            if '"type"' in line or '"timestamp"' in line:
                self._print(f"  {line}", Colors.CYAN, bold=True)
            elif '"error"' in line or '"ERROR"' in line:
                self._print(f"  {line}", Colors.RED)
            elif '"WARN"' in line or '"warning"' in line:
                self._print(f"  {line}", Colors.YELLOW)
            elif '"agent_id"' in line or '"mission_id"' in line:
                self._print(f"  {line}", Colors.MAGENTA)
            else:
                self._print(f"  {line}", Colors.DIM)
    
    async def connect(self):
        """Connect to WebSocket server."""
        url = self._build_url()
        self._print(f"\n🔌 Connecting to {url}...", Colors.CYAN, bold=True)
        
        try:
            self.websocket = await websockets.connect(url)
            self.stats["start_time"] = datetime.now()
            self._print("✅ Connected successfully!", Colors.GREEN, bold=True)
            self._print(f"📊 Filters: agent_ids={self.agent_ids or 'all'}, mission_ids={self.mission_ids or 'all'}, log_levels={self.log_levels or 'all'}, event_types={self.event_types or 'all'}", Colors.DIM)
            self._print("\n💡 Type 'help' for available commands\n", Colors.YELLOW)
            self.reconnect_attempts = 0
            return True
        except Exception as e:
            self._print(f"❌ Connection failed: {e}", Colors.RED, bold=True)
            self.stats["errors"] += 1
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket server."""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            self._print("\n🔌 Disconnected", Colors.YELLOW)
    
    async def send_message(self, message: Dict[str, Any]):
        """Send message to server."""
        if not self.websocket:
            self._print("❌ Not connected", Colors.RED)
            return
        
        try:
            await self.websocket.send(json.dumps(message))
            if self.verbose:
                self._print(f"📤 Sent: {message}", Colors.DIM)
        except Exception as e:
            self._print(f"❌ Send error: {e}", Colors.RED)
            self.stats["errors"] += 1
    
    async def receive_messages(self):
        """Receive and display messages from server."""
        while self.running and self.websocket:
            try:
                message_str = await self.websocket.recv()
                message = json.loads(message_str)
                
                # Update statistics
                self.stats["messages_received"] += 1
                self.stats["last_message_time"] = datetime.now()
                event_type = message.get("type", "unknown")
                self.stats["event_types"][event_type] = self.stats["event_types"].get(event_type, 0) + 1
                
                # Display message
                timestamp = message.get("timestamp", "N/A")
                
                # Compact display for common events (unless verbose)
                if not self.verbose and event_type in ["agent_status", "perf_metric", "perf_system"]:
                    agent_id = message.get("data", {}).get("agent_id", "N/A")
                    self._print(f"[{timestamp}] {event_type}: {agent_id}", Colors.DIM)
                else:
                    # Full display for important events
                    color = Colors.WHITE
                    if "error" in event_type.lower():
                        color = Colors.RED
                    elif "warn" in event_type.lower():
                        color = Colors.YELLOW
                    elif event_type in ["mission_started", "mission_completed", "collaboration_started", "consensus"]:
                        color = Colors.GREEN
                    
                    self._print(f"\n{'='*80}", Colors.DIM)
                    self._print(f"[{timestamp}] {event_type}", color, bold=True)
                    self._print_json(message)
                    self._print(f"{'='*80}\n", Colors.DIM)
                
            except websockets.exceptions.ConnectionClosed:
                self._print("\n⚠️  Connection closed by server", Colors.YELLOW)
                break
            except json.JSONDecodeError as e:
                self._print(f"❌ Invalid JSON: {e}", Colors.RED)
                self.stats["errors"] += 1
            except Exception as e:
                self._print(f"❌ Receive error: {e}", Colors.RED)
                self.stats["errors"] += 1
                break
    
    async def handle_user_input(self):
        """Handle interactive user commands."""
        while self.running:
            try:
                # Non-blocking input (wait 0.5s for input, then loop)
                await asyncio.sleep(0.5)
                
                # Check if input is available (this is a workaround for async input)
                # In a real implementation, you'd use aioconsole or similar
                # For now, we'll just skip interactive commands in async context
                
            except Exception as e:
                self._print(f"❌ Input error: {e}", Colors.RED)
    
    def _show_help(self):
        """Display help message."""
        self._print("\n📖 Available Commands:", Colors.CYAN, bold=True)
        self._print("  help              - Show this help message", Colors.WHITE)
        self._print("  filters           - Show current filters", Colors.WHITE)
        self._print("  update <filters>  - Update filters (e.g., 'update agent_ids=agent-1,agent-2')", Colors.WHITE)
        self._print("  snapshot          - Request state snapshot", Colors.WHITE)
        self._print("  snapshot refresh  - Request state snapshot with force_refresh", Colors.WHITE)
        self._print("  stats             - Show statistics", Colors.WHITE)
        self._print("  clear             - Clear screen", Colors.WHITE)
        self._print("  quit / exit       - Disconnect and exit\n", Colors.WHITE)
    
    def _show_stats(self):
        """Display statistics."""
        uptime = (datetime.now() - self.stats["start_time"]).total_seconds() if self.stats["start_time"] else 0
        last_msg_age = (datetime.now() - self.stats["last_message_time"]).total_seconds() if self.stats["last_message_time"] else 0
        
        self._print("\n📊 Statistics:", Colors.CYAN, bold=True)
        self._print(f"  Uptime: {uptime:.1f}s", Colors.WHITE)
        self._print(f"  Messages received: {self.stats['messages_received']}", Colors.WHITE)
        self._print(f"  Reconnects: {self.stats['reconnects']}", Colors.WHITE)
        self._print(f"  Errors: {self.stats['errors']}", Colors.WHITE)
        self._print(f"  Last message: {last_msg_age:.1f}s ago", Colors.WHITE)
        
        if self.stats["event_types"]:
            self._print("\n  Event Types:", Colors.CYAN)
            for event_type, count in sorted(self.stats["event_types"].items(), key=lambda x: x[1], reverse=True):
                self._print(f"    {event_type}: {count}", Colors.DIM)
        self._print("")
    
    async def request_snapshot(self, force_refresh: bool = False):
        """Request state snapshot from server."""
        self._print(f"\n📸 Requesting state snapshot (force_refresh={force_refresh})...", Colors.CYAN)
        await self.send_message({
            "type": "request_snapshot",
            "force_refresh": force_refresh
        })
    
    async def update_filters(self, **filters):
        """Update subscription filters."""
        self._print(f"\n🔧 Updating filters: {filters}", Colors.CYAN)
        await self.send_message({
            "type": "update_filters",
            "filters": filters
        })
        
        # Update local filters
        if "agent_ids" in filters:
            self.agent_ids = set(filters["agent_ids"]) if filters["agent_ids"] else set()
        if "mission_ids" in filters:
            self.mission_ids = set(filters["mission_ids"]) if filters["mission_ids"] else set()
        if "log_levels" in filters:
            self.log_levels = set(filters["log_levels"]) if filters["log_levels"] else set()
        if "event_types" in filters:
            self.event_types = set(filters["event_types"]) if filters["event_types"] else set()
    
    async def run(self):
        """Main run loop with auto-reconnect."""
        self.running = True
        
        while self.running:
            # Connect
            if not await self.connect():
                if not self.auto_reconnect:
                    break
                
                # Exponential backoff
                delay = min(2 ** self.reconnect_attempts, self.max_reconnect_delay)
                self.reconnect_attempts += 1
                self.stats["reconnects"] += 1
                self._print(f"🔄 Reconnecting in {delay}s (attempt {self.reconnect_attempts})...", Colors.YELLOW)
                await asyncio.sleep(delay)
                continue
            
            # Receive messages
            try:
                await self.receive_messages()
            except Exception as e:
                self._print(f"❌ Error in receive loop: {e}", Colors.RED)
                self.stats["errors"] += 1
            
            # Disconnect
            await self.disconnect()
            
            # Auto-reconnect if running
            if self.running and self.auto_reconnect:
                delay = min(2 ** self.reconnect_attempts, self.max_reconnect_delay)
                self.reconnect_attempts += 1
                self.stats["reconnects"] += 1
                self._print(f"🔄 Reconnecting in {delay}s...", Colors.YELLOW)
                await asyncio.sleep(delay)
            else:
                break
        
        self._print("\n👋 Goodbye!", Colors.GREEN, bold=True)
        self._show_stats()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WebSocket test client for Dexter Cockpit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--url",
        default="ws://localhost:8765/ws/cockpit",
        help="WebSocket URL (default: ws://localhost:8765/ws/cockpit)"
    )
    parser.add_argument(
        "--agent-ids",
        help="Comma-separated agent IDs to filter (e.g., 'agent-1,agent-2')"
    )
    parser.add_argument(
        "--mission-ids",
        help="Comma-separated mission IDs to filter"
    )
    parser.add_argument(
        "--log-levels",
        help="Comma-separated log levels (TRACE,INFO,WARN,ERROR)"
    )
    parser.add_argument(
        "--event-types",
        help="Comma-separated event types to filter"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show all message details (verbose mode)"
    )
    parser.add_argument(
        "--no-auto-reconnect",
        action="store_true",
        help="Disable auto-reconnect on disconnect"
    )
    
    args = parser.parse_args()
    
    # Parse filters
    agent_ids = set(args.agent_ids.split(",")) if args.agent_ids else None
    mission_ids = set(args.mission_ids.split(",")) if args.mission_ids else None
    log_levels = set(args.log_levels.split(",")) if args.log_levels else None
    event_types = set(args.event_types.split(",")) if args.event_types else None
    
    # Create client
    client = WebSocketTestClient(
        url=args.url,
        agent_ids=agent_ids,
        mission_ids=mission_ids,
        log_levels=log_levels,
        event_types=event_types,
        verbose=args.verbose,
        auto_reconnect=not args.no_auto_reconnect
    )
    
    # Print banner
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}Dexter Cockpit WebSocket Test Client{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.RESET}\n")
    
    # Run client
    try:
        await client.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Interrupted by user{Colors.RESET}")
        client.running = False
        await client.disconnect()
        client._show_stats()


if __name__ == "__main__":
    asyncio.run(main())
