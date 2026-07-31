#!/usr/bin/env python3
# bridge_activator.py — Minimal bridge wiring for OPRRRV + poller
# Wires EventBus subscriptions without full module dependency tree.
import os, sys, logging
logger = logging.getLogger("bridge")

def activate(operator=None, agent=None):
    '''Wire core modules via EventBus. Call once at startup.'''
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    try:
        from modules.event_bus import EventBus, Event, EVENT_TYPES
        bus = EventBus()
        
        # Core subscriptions
        bus.subscribe("task_completed", lambda e: logger.info(f"[Bridge] task done: {e.data.get('goal','')}"))
        bus.subscribe("action_executed", lambda e: logger.warning(f"[Bridge] action error: {e.data.get('error','')}"))
        bus.subscribe("model_switched", lambda e: logger.info(f"[Bridge] model changed: {e.data}"))
        
        logger.info("[Bridge] activated with 3 core subscriptions")
        return bus
    except ImportError as e:
        logger.warning(f"[Bridge] partial activation: {e}")
        return None
