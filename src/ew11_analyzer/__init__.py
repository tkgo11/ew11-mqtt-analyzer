"""EW11 MQTT packet auto-analysis tool.

Captures wallpad RS485 traffic bridged to MQTT (via Elfin EW11 or similar),
learns the baseline (idle/heartbeat) traffic, and isolates event packets
produced by button presses for reverse-engineering.
"""

__version__ = "0.1.0"
