"""Diagnostic test for BWB 255 front section evacuation."""
import sys
from bwb_sim.config import SimConfig
from bwb_sim.engine import Simulation

# Redirect output to file
output = open('diag_output.txt', 'w')
sys.stdout = output

cfg = SimConfig.from_json('layouts/bwb_255_mixed.json')
cfg.mode = 'egress'
cfg.load_factor = 0.2

sim = Simulation(cfg)
sim._generate_passengers_seated()

# Check the layout for front section (rows 1-7)
print("=== Layout Analysis ===")
for section in cfg.lopa.sections:
    print(f"Section: {section.class_name}")
    print(f"  Rows: {section.start_row}-{section.end_row}")
    print(f"  Layout: {section.layout_string}")
    print()

# Check seats in front section
print("=== Seats in Rows 1-7 ===")
front_seats = [(r, c) for (r, c) in sim.geo.seats if r < 8]
print(f"Count: {len(front_seats)}")
for r, c in sorted(front_seats):
    seat_info = sim.geo.seats[(r, c)]
    print(f"  Seat ({r}, {c}) -> aisle_col: {seat_info['aisle_col']}")

# Check passengers in front section
print("\n=== Passengers in Rows 1-7 ===")
front_pax = [p for p in sim.passengers if p.row < 8]
print(f"Count: {len(front_pax)}")
for p in front_pax[:10]:
    print(f"  Pax {p.id}: seat ({p.row}, {p.col}), aisle_col: {p.aisle_col}")

# Pre-compute door maps like the simulation does
import simpy
print("\n=== Distance Map Analysis ===")
sim.door_maps = {}
for d in cfg.lopa.door_locations:
    sim.door_resources[d.name] = simpy.Resource(sim.env, capacity=1)
    sim.door_maps[d.name] = sim.geo.compute_distance_map([(d.row, d.col)])
    
    # Check if front section seats are reachable from this door
    reachable = [(r, c) for (r, c) in front_seats if (r, c) in sim.door_maps[d.name]]
    print(f"\nDoor {d.name} at ({d.row}, {d.col}): {len(reachable)}/{len(front_seats)} front seats reachable")
    
    # Sample distances for reachable seats
    if reachable:
        print(f"  Reachable samples (with distances):")
        for r, c in reachable[:5]:
            dist = sim.door_maps[d.name].get((r, c), -1)
            print(f"    ({r}, {c}): dist={dist}")
    
    # Sample unreachable seats
    unreachable = [(r, c) for (r, c) in front_seats if (r, c) not in sim.door_maps[d.name]]
    if unreachable:
        print(f"  UNREACHABLE ({len(unreachable)} seats):")
        for r, c in unreachable[:5]:
            print(f"    ({r}, {c})")

# Check specific path from door L1 to front seats
print("\n=== Path Analysis from L1 (0,0) ===")
l1_map = sim.door_maps.get('L1', {})
print(f"L1 distance map size: {len(l1_map)} cells")

# Check aisle column 4 reachability
print("\nColumn 4 (left bay aisle) cells in L1 map:")
for r in range(8):
    dist = l1_map.get((r, 4), None)
    char = sim.geo.layout_map.get((r, 4), '?')
    in_grid = (r, 4) in sim.geo.grid_resources
    print(f"  Row {r}, Col 4: char='{char}', dist={dist}, in_grid={in_grid}")

output.close()
print("Diagnostic output written to diag_output.txt", file=sys.__stdout__)

