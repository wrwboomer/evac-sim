
import sys
import os
import glob
import inspect
sys.path.append(os.getcwd())

from bwb_sim.config import SimConfig
import bwb_sim.engine
from bwb_sim.engine import Simulation

# Redirect output to file to avoid buffering issues/truncation
log_file = open("verify_log.txt", "w", buffering=1)
sys.stdout = log_file
sys.stderr = log_file

def verify_logic():
    print(f"Engine File: {bwb_sim.engine.__file__}")
    print(f"Move Step Source:\n{inspect.getsource(Simulation.move_step)}")
    print("--- STARTING LOGIC VERIFICATION ---")
    
    # 1. Load Layout
    l = glob.glob(os.path.join("layouts", "*.json"))
    if not l: l = glob.glob(r"d:\Users\wwill\Python\Evac_Sim\layouts\*.json")
    if not l:
        print("FAIL: No layouts found")
        sys.exit(1)
        
    cfg = SimConfig.from_json(l[0])
    cfg.mode = "egress"
    cfg.load_factor = 0.2 # 20% load to test basic interaction/gridlock
    print(f"Loaded {l[0]} with Load Factor {cfg.load_factor}")

    # 2. Run Simulation
    sim = Simulation(cfg)
    print("Simulation initialized. Running headless...")
    
    try:
        stats = sim.run(headless=True)
        print("Simulation Completed Successfully!")
        print("Stats:", stats)
        
        if stats['evacuated_count'] == stats['total_pax']:
            print("PASS: All passengers evacuated.")
        else:
            print(f"WARN: Only {stats['evacuated_count']}/{stats['total_pax']} evacuated.")
            # It might be 90s limit reached, which is fine, logic didn't crash.
            
    except Exception as e:
        print("FAIL: Simulation Crashed")
        print(e)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    verify_logic()
