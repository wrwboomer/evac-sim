from bwb_sim.config import SimConfig
from bwb_sim.engine import Simulation

# Test evacuation with fixed speeds - MORE VERBOSE
cfg = SimConfig.from_json('layouts/767-300ER (248).json')
cfg.mode = 'egress'
cfg.behavior.evac_speed_mean = 1.5
cfg.behavior.visibility_factor = 1.0
cfg.load_factor = 0.3  # Fewer passengers for easier debugging

print("Testing evacuation with speed = 1.5 m/s...")
print(f"Config: evac_speed_mean = {cfg.behavior.evac_speed_mean}")
print(f"Config: visibility_factor = {cfg.behavior.visibility_factor}")

sim = Simulation(cfg)

# Check passenger speeds after generation
print(f"\nGenerating {int(len(sim.geo.seats) * cfg.load_factor)} passengers...")
sim._generate_passengers_seated()

print(f"\nSample passenger speeds:")
for i, p in enumerate(sim.passengers[:5]):
    print(f"  Passenger {p.id} ({p.p_type}): speed = {p.speed:.2f} m/s")

print(f"\nRunning evacuation simulation...")
# Don't use headless so we can see progress
stats = sim.run_egress(headless=False)

print(f'\n=== Evacuation Results ===')
print(f'Total Time: {stats["total_time"]:.1f}s')
print(f'Evacuated: {stats["evacuated_count"]}/{stats["total_pax"]}')
print(f'Success: {stats["success"]}')
