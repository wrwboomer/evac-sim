"""Quick check of door positions."""
from bwb_sim.config import SimConfig
from bwb_sim.engine import Simulation
cfg = SimConfig.from_json('layouts/bwb_255_mixed.json')
cfg.mode = 'egress'
sim = Simulation(cfg)

# Check if door positions are walkable
print('Door positions:')
for d in cfg.lopa.door_locations:
    in_grid = (d.row, d.col) in sim.geo.grid_resources
    is_wall = (d.row, d.col) in sim.geo.walls
    char = sim.geo.layout_map.get((d.row, d.col), '?')
    print(f'  {d.name} at ({d.row}, {d.col}): char="{char}" in_grid={in_grid} is_wall={is_wall}')

# Check row 0 vestibule
print('\nRow 0 (vestibule) cell types:')
for c in range(27):
    char = sim.geo.layout_map.get((0, c), '?')
    in_grid = (0, c) in sim.geo.grid_resources
    is_wall = (0, c) in sim.geo.walls
    print(f'  Col {c}: char="{char}" in_grid={in_grid} is_wall={is_wall}')
