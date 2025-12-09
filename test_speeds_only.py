from bwb_sim.config import SimConfig
from bwb_sim.engine import Simulation

# Minimal test to check passenger speeds
cfg = SimConfig.from_json('layouts/767-300ER (248).json')
cfg.mode = 'egress'
cfg.behavior.evac_speed_mean = 1.5
cfg.behavior.visibility_factor = 1.0
cfg.load_factor = 0.1  # Just 10% load

sim = Simulation(cfg)
sim._generate_passengers_seated()

print(f"Generated {len(sim.passengers)} passengers")
print(f"\nPassenger speeds:")
for p in sim.passengers[:10]:
    print(f"  Pax {p.id} ({p.p_type}): speed = {p.speed:.3f} m/s, at seat ({p.row}, {p.col})")

print(f"\nConfig values:")
print(f"  evac_speed_mean: {cfg.behavior.evac_speed_mean}")
print(f"  visibility_factor: {cfg.behavior.visibility_factor}")
print(f"  Expected speed: {cfg.behavior.evac_speed_mean * cfg.behavior.visibility_factor}")
