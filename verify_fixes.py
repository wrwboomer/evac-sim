from bwb_sim.engine import Simulation
from bwb_sim.config import SimConfig, AircraftLOPA, Behavior, PassengerMix
import json
import os
import sys

def test_timeout():
    print("Testing Timeout Fix & Geometry...")
    
    # Load the layout to test
    layout_path = "layouts/Z4 (254).json"
    
    try:
        # Load config from JSON
        cfg = SimConfig.from_json(layout_path)
        cfg.primary_door = "L1" # FORCE L1 to test crash hypothesis
        # Ensure we use a short timeout for testing if not already set, 
        # but we want to test the *engine* timeout, so we rely on engine.py's run() default or explicit call.
        # engine.py now has self.env.run(until=3600).
        
        print(f"Running simulation for {cfg.lopa.name}...")
        sim = Simulation(cfg)
        stats = sim.run(headless=True)
        print("Simulation finished successfully.")
        print(f"Stats: {stats}")
        
        # Verify Heatmap Data
        if sim.heatmap_accum:
            print(f"PASS: Heatmap data collected. Keys: {len(sim.heatmap_accum)}")
            max_val = max(sim.heatmap_accum.values())
            print(f"Max Congestion: {max_val} ticks")
        else:
            print("FAIL: No heatmap data collected.")
        
    except ValueError as e:
        print(f"CAUGHT EXPECTED CRASH (if testing bad geometry): {e}")
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_timeout()
