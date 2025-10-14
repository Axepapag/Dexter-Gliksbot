#!/usr/bin/env python3
"""
Clear Redis Celery Queues

This script clears old Celery tasks from Redis to prevent
"unregistered task" errors when task names have changed.
"""

import sys

try:
    import redis
except ImportError:
    print("❌ Redis Python package not installed.")
    print("   Install with: pip install redis")
    sys.exit(1)


def clear_celery_queues(host='localhost', port=6379, db=0):
    """
    Clear Celery queues from Redis.
    
    Args:
        host: Redis host (default: localhost)
        port: Redis port (default: 6379)
        db: Redis database number (default: 0)
    """
    try:
        # Connect to Redis
        r = redis.Redis(host=host, port=port, db=db, socket_connect_timeout=2)
        
        # Test connection
        r.ping()
        print(f"✓ Connected to Redis at {host}:{port}")
        
        # Get all keys
        all_keys = r.keys('*')
        print(f"  Found {len(all_keys)} keys in Redis")
        
        # Clear Celery-related keys
        celery_patterns = [
            'celery',
            '_kombu.binding.celery*',
            'unacked*',
            'unacked_mutex*',
        ]
        
        deleted_count = 0
        for pattern in celery_patterns:
            keys = r.keys(pattern)
            if keys:
                deleted = r.delete(*keys)
                deleted_count += deleted
                print(f"  Deleted {deleted} keys matching: {pattern}")
        
        if deleted_count > 0:
            print(f"\n✓ Cleared {deleted_count} Celery queue entries")
        else:
            print("\n✓ No Celery queue entries to clear")
        
        # Show remaining keys (for debugging)
        remaining = r.keys('*')
        if remaining:
            print(f"  {len(remaining)} keys remaining in Redis:")
            for key in remaining[:10]:  # Show first 10
                print(f"    - {key.decode('utf-8')}")
            if len(remaining) > 10:
                print(f"    ... and {len(remaining) - 10} more")
        
        return True
        
    except redis.ConnectionError:
        print(f"❌ Could not connect to Redis at {host}:{port}")
        print("   Make sure Redis is running:")
        print("   - Windows: Start Redis service or run 'redis-server'")
        print("   - Linux: sudo systemctl start redis")
        print("   - macOS: brew services start redis")
        return False
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Redis Celery Queue Cleaner")
    print("=" * 70)
    print()
    
    success = clear_celery_queues()
    
    if success:
        print("\n" + "=" * 70)
        print("✓ Done! You can now restart your Celery worker:")
        print("  celery -A dexter_autonomy.workers.tasks:celery_app worker --loglevel=info --pool=solo")
        print("=" * 70)
        sys.exit(0)
    else:
        sys.exit(1)
