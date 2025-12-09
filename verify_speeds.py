import sys
import os
import random
from bwb_sim.config import SimConfig
from bwb_sim.engine import Simulation

# Mock the LOPA file path for loading config
# We'll just use the default values from the class definition if possible, 
# or load a real one if we can find it.
# Actually, SimConfig.from_json needs a file.
# Let's try to find one.
import glob
lopa_files = glob.glob("layouts/*.json")
if not lopa_files:
    print("No LOPA files found in layouts/")
    sys.exit(1)

lopa_path = lopa_files[0]
print(f"Using LOPA: {lopa_path}")

cfg = SimConfig.from_json(lopa_path)

# Set specific speeds
cfg.behavior.speed_business = 2.0
cfg.behavior.speed_economy = 1.0
cfg.behavior.speed_family = 0.5
cfg.behavior.speed_prm = 0.1

# Set mix to ensure we have all types
cfg.pax_mix.business_pct = 25
cfg.pax_mix.family_pct = 25
cfg.pax_mix.prm_pct = 10 # Ensure at least some PRMs

sim = Simulation(cfg)
sim._generate_passengers()

print(f"Generated {len(sim.passengers)} passengers.")

errors = 0
for p in sim.passengers:
    expected_mean = 0
    if p.p_type == "business":
        expected_mean = cfg.behavior.speed_business
    elif p.p_type == "economy":
        expected_mean = cfg.behavior.speed_economy
    elif p.p_type == "family":
        expected_mean = cfg.behavior.speed_family
    elif p.p_type == "prm":
        expected_mean = cfg.behavior.speed_prm
    
    # Check if speed is within reasonable range (mean +/- 3*std_dev + buffer)
    # std_dev is 0.15 for most, 0.1 for PRM
    # We'll just check if it's "close enough" to distinguish from other types
    
    # Simple check: is it closer to its expected mean than the others?
    # Actually, with 2.0, 1.0, 0.5, 0.1, they should be quite distinct.
    
    diff = abs(p.speed - expected_mean)
    if diff > 0.5: # Generous buffer
        print(f"ERROR: Pax {p.id} ({p.p_type}) has speed {p.speed:.2f}, expected around {expected_mean}")
        errors += 1

if errors == 0:
    print("SUCCESS: All passengers have speeds within expected ranges.")
else:
    print(f"FAILURE: {errors} passengers had unexpected speeds.")
    sys.exit(1)
