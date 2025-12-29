# FILE: bwb_sim/geometry.py
import simpy
from .config import SimConfig

class Geometry:
    def __init__(self, env: simpy.Environment, config: SimConfig):
        self.env = env
        self.cfg = config.lopa
        self.sim_config = config # Store full config (for behavior)
        # Track mode to tune capacities (boarding vs egress)
        self.mode = getattr(config, "mode", "egress")
        self.grid_resources = {} 
        self.seats = {}          
        self.walls = set()       
        self.layout_map = {} 
        
        # Cache door rows for quick lookup
        self.door_rows = {d.row for d in self.cfg.door_locations}
        
        self._build_grid()

    def _build_grid(self):
        for section in self.cfg.sections:
            layout = section.layout_string
            for r in range(section.start_row, section.end_row + 1):
                aisle_indices = [i for i, char in enumerate(layout) if char == '-']
                
                for c, char in enumerate(layout):
                    self.layout_map[(r, c)] = char
                    
                    # Only create walkable grid for aisles '-' and seats 'S'
                    # Treat '.' (floor/structure) and '|' (walls) as barriers
                    if char == '-' or char == 'S':
                        # Moderate capacity in egress to allow queues to form
                        base_cap = 3 if self.mode == "egress" else 2
                        cap = base_cap
                        # WIDE AISLE (Any row with a door)
                        if r in self.door_rows: 
                            width_multiplier = getattr(self.sim_config.behavior, 'cross_aisle_width', 2.0)
                            cap = int(base_cap * width_multiplier)
                        
                        self.grid_resources[(r, c)] = simpy.Resource(self.env, capacity=cap)
                    
                    # Mark walls explicitly
                    if char == '|' or char == '.':
                        self.walls.add((r, c))
                        # Remove resource if accidentally added
                        if (r, c) in self.grid_resources:
                            del self.grid_resources[(r, c)]
                        
                    if char == 'S':
                        if aisle_indices:
                            aisle_col = min(aisle_indices, key=lambda x: abs(x - c))
                        else:
                            aisle_col = c 
                        self.seats[(r, c)] = {'aisle_col': aisle_col, 'class': section.class_name}

    def get_node(self, r, c):
        if (r, c) in self.grid_resources:
            return self.grid_resources[(r, c)]
            
        char = self.layout_map.get((r, c), '.')
        
        # EXPLICIT WALL CHECK: Never create resources for walls, even in door rows
        if char == '|' or (r, c) in self.walls:
             raise ValueError(f"PASSENGER CRASH: Agent tried to walk on WALL '{char}' at Row {r}, Col {c}.")
        
        # Allow dynamic creation only if it's a "Wide" row (Door row)
        is_wide_row = r in self.door_rows if hasattr(self, 'door_rows') else False
        if is_wide_row:
            # Matches _build_grid logic: Double width = double base capacity
            base_cap = 3 if self.mode == "egress" else 2
            width_multiplier = getattr(self.sim_config.behavior, 'cross_aisle_width', 2.0)
            res = simpy.Resource(self.env, capacity=int(base_cap * width_multiplier))
            self.grid_resources[(r, c)] = res
            return res

        # Allow walking on '.' (Floor) dynamically if not pre-built
        # Use moderate capacity in egress
        cap = 4 if self.mode == "egress" else 2
        res = simpy.Resource(self.env, capacity=cap)
        self.grid_resources[(r, c)] = res
        return res

    def get_target_aisle(self, r, c):
        if (r, c) in self.seats:
            return self.seats[(r, c)]['aisle_col']
        return 0

    def get_valid_neighbors(self, r, c):
        """Returns reachable neighbors (Up, Down, Left, Right)."""
        valid = []
        for dr, dc in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nr, nc = r + dr, c + dc
            
            # CRITICAL: Check walls FIRST before any other logic
            # Check 1: Explicit walls set check (fastest check)
            if (nr, nc) in self.walls:
                continue  # Block walls - solid aircraft structure (galley, etc.)
            
            # Check 2: Explicit wall type check
            next_type = self.layout_map.get((nr, nc), '.')
            if next_type == '|' or next_type == '.':
                continue  # Block walls and non-walkable floor areas
            
            # Check 3: Must be in grid resources (walls are excluded from grid_resources)
            if (nr, nc) not in self.grid_resources:
                continue
            
            curr_type = self.layout_map.get((r, c), '.')
            
            # RULE 1: Vertical movement (row change) is ONLY allowed between aisle cells
            # This prevents vestibule -> seat shortcuts, forcing use of aisle paths
            if r != nr:  # Vertical movement
                # Both current and next must be aisles for vertical movement
                if curr_type != '-' or next_type != '-':
                    continue
            
            # RULE 2: If in a Seat, can only move horizontally within the row
            # (This is now redundant with RULE 1, but kept for clarity)
            if curr_type == 'S':
                if r != nr:
                    continue  # No vertical movement from seats
                     
            # Final safety check: Double-verify it's not a wall before adding
            if next_type != '|' and (nr, nc) not in self.walls:
                valid.append((nr, nc))
        return valid

    def compute_distance_map(self, target_nodes):
        """
        BFS Flood Fill from target_nodes (list of (r,c)).
        Returns dict: {(r, c): distance_steps}
        First pass: Route through aisles only (no seats)
        Second pass: Propagate distances to seats from adjacent aisles (so passengers know direction)
        """
        dist_map = {}
        queue = []
        
        # First pass: Spread through aisles only (no routing through seats)
        for r, c in target_nodes:
            dist_map[(r, c)] = 0
            queue.append((r, c))
            
        head = 0
        while head < len(queue):
            curr_r, curr_c = queue[head]
            head += 1
            curr_dist = dist_map[(curr_r, curr_c)]
            
            for nr, nc in self.get_valid_neighbors(curr_r, curr_c):
                if (nr, nc) not in dist_map:
                    # Strictly block walls, but allow seats to be part of the distance map.
                    # Movement rules still prevent walking through seats vertically; this just
                    # ensures every seat gets a distance value for lateral moves.
                    char = self.layout_map.get((nr, nc), '.')
                    if char == '|' or (nr, nc) in self.walls:
                        continue  # Skip walls - solid aircraft structure, cannot pass through
                        
                    dist_map[(nr, nc)] = curr_dist + 1
                    queue.append((nr, nc))
        
        # Second pass: Propagate distances to seats from adjacent aisles
        # This allows passengers in seats to know which direction to move (towards nearest aisle)
        seat_queue = []
        # Create a list copy to avoid modifying dict during iteration
        for (r, c), dist in list(dist_map.items()):
            # For each aisle cell, check adjacent seats in the same row
            char = self.layout_map.get((r, c), '.')
            if char != 'S':  # Current cell is an aisle
                # Check horizontal neighbors (seats in same row)
                for dc in [-1, 1]:
                    nc = c + dc
                    if (r, nc) in self.grid_resources:
                        seat_char = self.layout_map.get((r, nc), '.')
                        # Skip walls - cannot propagate distances through walls
                        if seat_char == '|' or (r, nc) in self.walls:
                            continue
                        if seat_char == 'S' and (r, nc) not in dist_map:
                            # Found an adjacent seat - add it with distance + 1
                            dist_map[(r, nc)] = dist + 1
                            seat_queue.append((r, nc))
        
        # Continue propagating to seats that are adjacent to seats already in the map
        # (for seats further from aisles, they need to move through other seats to reach aisle)
        head = 0
        while head < len(seat_queue):
            curr_r, curr_c = seat_queue[head]
            head += 1
            curr_dist = dist_map[(curr_r, curr_c)]
            
            # Only check horizontal neighbors (seats can only move horizontally)
            for dc in [-1, 1]:
                nc = curr_c + dc
                if (curr_r, nc) in self.grid_resources:
                    seat_char = self.layout_map.get((curr_r, nc), '.')
                    # Skip walls - cannot propagate distances through walls
                    if seat_char == '|' or (curr_r, nc) in self.walls:
                        continue
                    if seat_char == 'S' and (curr_r, nc) not in dist_map:
                        dist_map[(curr_r, nc)] = curr_dist + 1
                        seat_queue.append((curr_r, nc))
                    
        return dist_map