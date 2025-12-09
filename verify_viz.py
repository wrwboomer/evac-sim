import sys
import os
import tkinter as tk
import matplotlib.pyplot as plt

# Add current dir to sys.path
sys.path.append(os.getcwd())

from bwb_sim.config import SimConfig
from bwb_sim.engine import Simulation
from bwb_sim.live_viz import LiveSimulationFrame

def verify():
    # Load default layout
    import glob
    l = glob.glob(os.path.join("layouts", "*.json"))
    if not l:
        # Try absolute path if running from elsewhere? 
        # Assuming running from Evac_Sim root
        l = glob.glob(r"d:\Users\wwill\Python\Evac_Sim\layouts\*.json")
        
    if not l:
        print("No layouts found!")
        return

    layout_path = l[0]
    print(f"Loading {layout_path}")
    cfg = SimConfig.from_json(layout_path)
    cfg.mode = "egress"
    
    # BLOCK A DOOR
    if cfg.lopa.door_locations:
        target_door = cfg.lopa.door_locations[0].name
        print(f"Blocking door: {target_door}")
        cfg.behavior.active_exits[target_door] = False
    else:
        print("No door locations found in LOPA.")
    
    sim = Simulation(cfg)
    
    root = tk.Tk()
    
    print("Initializing Frame...")
    # Mock callback
    def cb(): pass
    
    app = LiveSimulationFrame(root, sim, cb)
    app.pack(fill="both", expand=True)
    
    # Force update to ensure canvas is ready?
    root.update()
    
    # Trigger draw
    print("Drawing frame...")
    app.draw_frame()
    
    # Save figure to artifact dir for report
    out_dir = r"C:\Users\wwill\.gemini\antigravity\brain\5545e489-59a9-474e-b1e2-732c0fe3d06e"
    out_path = os.path.join(out_dir, "verification_blocked_door.png")
    app.fig.savefig(out_path)
    print(f"Saved visualization to {out_path}")
    
    root.destroy()

if __name__ == "__main__":
    verify()
