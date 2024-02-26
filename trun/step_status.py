"""
Possible values for a Step's status in the Scheduler
"""

PENDING = 'PENDING'
FAILED = 'FAILED'
DONE = 'DONE'
RUNNING = 'RUNNING'
BATCH_RUNNING = 'BATCH_RUNNING'
SUSPENDED = 'SUSPENDED'  # Only kept for backward compatibility with old clients
UNKNOWN = 'UNKNOWN'
DISABLED = 'DISABLED'
