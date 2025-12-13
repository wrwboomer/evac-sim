# FILE: bwb_sim/engine.py
import simpy
import random
from tqdm import tqdm
from .config import SimConfig
from .geometry import Geometry
from .agents import Passenger
from .strategies import apply_strategy

class Simulation:
    def __init__(self, config: SimConfig):
        self.cfg = config
        self.env = simpy.Environment()
        self.geo = Geometry(self.env, config)
        self.passengers = []
        self.snapshots = [] 
        self.heatmap_accum = {}
        self.pbar = None
        self.occupied_seats = {} 
        self.all_seated_event = self.env.event()
        self.all_evacuated_event = self.env.event()
        self.door_queues = {}
        self.door_resources = {}  # Serialized door access (FIFO, capacity=1)
        self.exit_records = []    # [{'door': name, 't_exit': time, 'p_type': str}]
    
    def _validate_position(self, r, c, passenger_id=None):
        """Validate that a position is not a wall (including galley). Raises error if invalid."""
        # Special positions are allowed (-99 seated, -999 evacuated, -1 not in system)
        if r < 0 or c < 0:
            return True
        
        # CRITICAL: Check walls set first (includes galley walls)
        if (r, c) in self.geo.walls:
            pax_info = f" (Passenger {passenger_id})" if passenger_id is not None else ""
            raise ValueError(f"CRITICAL: Attempted to set position to WALL/GALLEY at ({r}, {c}){pax_info}. This should never happen!")
        
        char = self.geo.layout_map.get((r, c), '.')
        if char == '|':
            pax_info = f" (Passenger {passenger_id})" if passenger_id is not None else ""
            raise ValueError(f"CRITICAL: Attempted to set position to WALL/GALLEY '{char}' at ({r}, {c}){pax_info}. This should never happen!")
        return True

    def run(self, headless=False):
        # Router: Boarding vs Egress
        if self.cfg.mode == "egress":
            return self.run_egress(headless)

        self._generate_passengers()
        
        if not headless:
            print(f"Simulating Boarding: {len(self.passengers)} passengers...")
            self.pbar = tqdm(total=len(self.passengers), unit="pax")
            self.env.process(self.snapshot_loop())

        self.env.process(self.boarding_control())
        
        # Run until everyone seated OR 1 hour passes
        self.env.run(until=simpy.AnyOf(self.env, [self.all_seated_event, self.env.timeout(3600)]))
        
        if self.pbar: self.pbar.close()
        return self.get_stats()

    def run_egress(self, headless=False):
        self._generate_passengers_seated()
        
        if not headless:
            print(f"Simulating EVACUATION: {len(self.passengers)} passengers...")
            self.pbar = tqdm(total=len(self.passengers), unit="pax")
            self.env.process(self.snapshot_loop())
            
        # Initialize door queues
        for d in self.cfg.lopa.door_locations:
            self.door_queues[d.name] = 0

        # --- PRE-COMPUTE BFS MAPS ---
        # Maps: {door_name: {(r,c): dist}}
        self.door_maps = {}
        # Apply BLOCKING (active_exits overrides LOPA)
        override = self.cfg.behavior.active_exits
        active_doors = []
        for d in self.cfg.lopa.door_locations:
             # Check Override (UI) -> Default LOPA active -> True
             is_active = override.get(d.name, d.active)
             if is_active:
                 active_doors.append(d)
        
        if not active_doors: 
            print("WARNING: No active doors! Enabling ALL as fallback.")
            active_doors = self.cfg.lopa.door_locations

        print("Computing Pathfinding Maps...")
        # Initialize door resources (capacity=1) for FIFO exit flow
        for d in active_doors:
            self.door_resources[d.name] = simpy.Resource(self.env, capacity=1)
            # Door node is target
            self.door_maps[d.name] = self.geo.compute_distance_map([(d.row, d.col)])

        self.env.process(self.evacuation_control(active_doors))
        # Run until everyone evacuates (no hard 90s cap; use long safety cap to avoid infinite hang)
        self.env.run(until=simpy.AnyOf(self.env, [self.all_evacuated_event, self.env.timeout(3600)]))
        
        if self.pbar: self.pbar.close()
        return self.get_stats()

    def get_stats(self):
        if self.cfg.mode == "egress":
            evacuated_count = len([p for p in self.passengers if p.curr_r == -999])
            total_pax = len(self.passengers)
            total_time = self.env.now
            return {
                "total_time": total_time,
                "evacuated_count": evacuated_count,
                "total_pax": total_pax,
                "success": (evacuated_count == total_pax),
                "faa_pass_90s": (evacuated_count == total_pax and total_time <= 90.0)
            }
        else:
            seated_pax = [p for p in self.passengers if p.curr_r == -99]
            return {
                "total_time": self.env.now,
                "seated_count": len(seated_pax),
                "total_pax": len(self.passengers)
            }

    def _generate_passengers(self):
        seats = []
        pid = 0
        for (r, c), data in self.geo.seats.items():
            seats.append({'id': pid, 'r': r, 'c': c, 'aisle': data['aisle_col']})
            pid += 1
            
        total = len(seats)
        mix = self.cfg.pax_mix
        
        # FAA Demographics - assign to passengers (female / over_50 quotas)
        n_female = int(total * (mix.female_pct / 100))
        n_over_50 = int(total * (mix.over_50_pct / 100))
        
        # Behavioral types (unchanged percentages)
        n_prm = max(1, int(total * 0.02))  # 2% wheelchair/PRM
        n_family = max(1, int(total * 0.10))  # 10% families
        n_bus = max(1, int(total * 0.15))  # 15% business
        n_eco = total - n_bus - n_family - n_prm
        
        pax_list = []
        
        def make_pax(s_data, ptype, grp_id):
            p = Passenger(id=s_data['id'], row=s_data['r'], col=s_data['c'])
            p.aisle_col = s_data['aisle']
            p.p_type = ptype
            p.group_id = grp_id
            
            # Use NEW granular speeds
            if ptype == "business":
                base = self.cfg.behavior.speed_business
                p.stow_time = 4.0
            elif ptype == "family":
                base = self.cfg.behavior.speed_family
                p.stow_time = 20.0
            elif ptype == "prm":
                base = self.cfg.behavior.speed_prm
                p.width_units = 2
            else:
                base = self.cfg.behavior.speed_economy
                p.stow_time = self.cfg.behavior.stow_time_mean
            
            p.speed = random.gauss(base, 0.1)
            p.speed = max(0.2, p.speed)
            return p

        random.shuffle(seats)
        seat_idx = 0
        for _ in range(n_bus):
            if seat_idx >= total: break
            pax_list.append(make_pax(seats[seat_idx], "business", seat_idx)); seat_idx += 1
        for _ in range(n_prm):
            if seat_idx >= total: break
            pax_list.append(make_pax(seats[seat_idx], "prm", seat_idx)); seat_idx += 1
        for _ in range(n_eco):
            if seat_idx >= total: break
            pax_list.append(make_pax(seats[seat_idx], "economy", seat_idx)); seat_idx += 1
        while seat_idx < total:
            fam_id = seat_idx
            for i in range(4):
                if seat_idx >= total: break
                pax_list.append(make_pax(seats[seat_idx], "family", fam_id)); seat_idx += 1

        if self.cfg.load_factor < 1.0:
            count = int(len(pax_list) * self.cfg.load_factor)
            pax_list = random.sample(pax_list, count)

        # Apply demographic flags and speed adjustments
        random.shuffle(pax_list)
        for p in pax_list[:n_female]:
            p.is_female = True
        for p in pax_list[n_female:n_female + n_over_50]:
            p.is_over_50 = True

        for p in pax_list:
            # Over 50: slower
            if getattr(p, "is_over_50", False):
                p.speed = max(0.2, p.speed * 0.8)
            # Female: keep as-is (could tweak if needed)
            # PRM already handled via p_type

        self.passengers = pax_list
        strat = getattr(self.cfg, 'strategy', 'random')
        apply_strategy(self.passengers, strat, self.cfg.lopa.sections)

    def _generate_passengers_seated(self):
        self._generate_passengers()
        for p in self.passengers:
            p.curr_r = -99 # Start strictly seated for visuals
            p.curr_c = p.col
            # Apply VISIBILITY factor
            vis = getattr(self.cfg.behavior, 'visibility_factor', 1.0)
            # Apply visibility multiplier on top of per-passenger speed
            p.speed = max(0.2, p.speed * vis)

    def evacuation_control(self, active_doors):
        for p in self.passengers:
            self.env.process(self.passenger_egress_process(p, active_doors))
        yield self.env.timeout(0)

    def passenger_egress_process(self, p, doors):
        # 1. Reaction Time
        reaction_delay = random.expovariate(1.0 / self.cfg.behavior.reaction_time_mean)
        yield self.env.timeout(reaction_delay)
        
        # VISUAL: Stand Up
        self._validate_position(p.row, p.col, p.id)
        # Double-check: ensure seat position is not a wall/galley
        if (p.row, p.col) in self.geo.walls or self.geo.layout_map.get((p.row, p.col), '.') == '|':
            raise ValueError(f"CRITICAL: Passenger {p.id} seat position ({p.row}, {p.col}) is a WALL/GALLEY!")
        p.curr_r, p.curr_c = p.row, p.col
        
        # 2. Target Selection (Panic vs Rational)
        panic_threshold = self.cfg.behavior.panic_level
        entry_door = next((d for d in doors if d.name == "L2"), doors[0])
        
        curr_r, curr_c = p.row, p.col
        
        # Determine Target Door
        if random.random() < panic_threshold:
             target_door = entry_door # Irrational
        else:
             # Rational: Minimize ACTUAL Walking Distance (BFS)
             # Shuffle candidates to break ties (Load Balancing)
             candidates = list(doors)
             random.shuffle(candidates)
             
             def get_dist(d):
                 return self.door_maps[d.name].get((curr_r, curr_c), 9999)
             target_door = min(candidates, key=get_dist)
        
        # If unreachable, try to find a door that has this position in its distance map
        # Don't use Manhattan distance as it ignores walls/aisles
        if self.door_maps[target_door.name].get((curr_r, curr_c)) is None:
             # Try to find any door that can reach this position
             reachable_doors = [d for d in doors if (curr_r, curr_c) in self.door_maps.get(d.name, {})]
             if reachable_doors:
                 target_door = min(reachable_doors, key=lambda d: self.door_maps[d.name].get((curr_r, curr_c), 9999))
             else:
                 # If truly unreachable, pick door with shortest path from aisle (not Manhattan)
                 # Find nearest aisle position first
                 min_dist = 9999
                 best_door = doors[0] if doors else None
                 for d in doors:
                     # Check distance from door's nearest reachable point
                     door_dist_map = self.door_maps.get(d.name, {})
                     if door_dist_map:
                         # Find minimum distance in the map (closest reachable point)
                         min_in_map = min(door_dist_map.values()) if door_dist_map else 9999
                         if min_in_map < min_dist:
                             min_dist = min_in_map
                             best_door = d
                 if best_door:
                     target_door = best_door
        
        dist_map = self.door_maps[target_door.name]
        print(f"Pax {p.id} ({p.p_type}) Target: {target_door.name} Dist: {dist_map.get((curr_r, curr_c), -1)}")

        # 3. Getting Out of Seat (stepwise, respecting occupancy)
        # Acquire current seat node first
        current_reqs = yield from self.acquire_node(p, p.row, p.col)
        p.curr_r, p.curr_c = p.row, p.col
        curr_r, curr_c = p.row, p.col

        if p.col != p.aisle_col:
            step = 1 if p.aisle_col > p.col else -1
            
            # 1. Reaction/Standup
            yield self.env.timeout(random.uniform(1.0, 2.0))
            
            # 2. Wait for neighbors to clear (with timeout to prevent infinite blocking)
            blocked = True
            max_wait_time = 1.5  # tighter to avoid long stalls
            wait_elapsed = 0.0
            while blocked and wait_elapsed < max_wait_time:
                blocked = False
                for c_chk in range(p.col + step, p.aisle_col, step):
                    node = self.geo.get_node(p.row, c_chk)
                    if node.count >= 1: 
                        blocked = True
                        break
                if blocked:
                    wait_time = min(0.3, max_wait_time - wait_elapsed)
                    yield self.env.timeout(wait_time)
                    wait_elapsed += wait_time
            
            # 3. Stepwise lateral move to aisle (with occupancy)
            while curr_c != p.aisle_col:
                next_c = curr_c + step
                new_reqs, old_reqs = yield from self.move_step(
                    p, curr_r, next_c, current_reqs, timeout=None  # hold position until move succeeds
                )
                if new_reqs is None:
                    # Failed (should be rare with timeout=None); small backoff
                    yield self.env.timeout(0.2)
                    continue
                current_reqs = new_reqs
                curr_c = next_c
                p.curr_r, p.curr_c = curr_r, curr_c
        else:
            # Already at aisle column; current_reqs holds seat. Move into aisle cell.
            pass  # handled below

        # Ensure we are holding the aisle cell (if we are not already in it, move one step)
        if curr_c != p.aisle_col:
            raise ValueError("Unexpected: failed to reach aisle column in seat egress.")
        if curr_r != p.row or curr_c != p.aisle_col:
            # Move into target aisle cell if not already there
            new_reqs, old_reqs = yield from self.move_step(
                p, p.row, p.aisle_col, current_reqs, timeout=None
            )
            if new_reqs is not None:
                current_reqs = new_reqs
                curr_r, curr_c = p.row, p.aisle_col
                p.curr_r, p.curr_c = curr_r, curr_c

        # 4. Gradient Descent Movement with Re-Evaluation
        steps_since_eval = 0
        stuck_count = 0
        
        while (curr_r, curr_c) != (target_door.row, target_door.col):
            # Check neighbors logic again
            steps_since_eval += 1
            
            # --- Anti-Gridlock Logic ---
            # If we are stuck, maybe force a re-eval or random move
            force_random_move = False
            if stuck_count > 3:
                steps_since_eval = 999 # Force re-eval
                if random.random() < 0.3: force_random_move = True # Try to wiggle out
            
            def door_load(d):
                res = self.door_resources.get(d.name)
                if res is None:
                    return 0
                return res.count + len(res.queue)

            if steps_since_eval > 5:
                steps_since_eval = 0
                # Check Door Choice
                current_target_score = door_load(target_door) + dist_map.get((curr_r, curr_c), 999)
                
                # Scan other ACTIVE doors
                best_alt = target_door
                best_score = current_target_score
                
                for alt_d in doors:
                    if alt_d == target_door: continue
                    if alt_d.name not in self.door_maps: continue
                    alt_dist = self.door_maps[alt_d.name].get((curr_r, curr_c), 9999)
                    if alt_dist > 500: continue # Unreachable
                    
                    alt_score = door_load(alt_d) + alt_dist
                    
                    # Switch if SUBSTANTIALLY better (hysteresis to prevent flickering)
                    # If stuck, lower the bar for switching
                    threshold = 0.7 if stuck_count < 3 else 0.9
                    if alt_score < (best_score * threshold): 
                        best_alt = alt_d
                        best_score = alt_score
                        
                if best_alt != target_door:
                    target_door = best_alt
                    dist_map = self.door_maps[target_door.name]
            
            neighbors = self.geo.get_valid_neighbors(curr_r, curr_c)
            # Filter for valid moves using the distance map
            valid_n = []
            for n in neighbors:
                if n in dist_map:
                    n_type = self.geo.layout_map.get(n, '.')
                    if n_type != '|' and n not in self.geo.walls:
                        valid_n.append(n)
            
            # --- FIX: Monotonic Seat Egress ---
            # If in a Seat, allow movement to lower or equal distance (lateral movement when needed)
            if self.geo.layout_map.get((curr_r, curr_c), '.') == 'S':
                force_random_move = False
                cur_dist = dist_map.get((curr_r, curr_c))
                if cur_dist is None:
                    # Current position not in map - allow any valid neighbor (shouldn't happen)
                    print(f"WARNING: Passenger in seat at {(curr_r, curr_c)} not in distance map!")
                else:
                    # Allow equal or lower distance - enables lateral movement when forward is blocked
                    valid_n = [n for n in valid_n if dist_map.get(n, 9999) <= cur_dist]
                    # Prefer strictly decreasing distance when possible
                    lower_dist = [n for n in valid_n if dist_map.get(n, 9999) < cur_dist]
                    if lower_dist:
                        valid_n = lower_dist

            if not valid_n:
                # Allow a fallback wiggle using ANY non-wall neighbor only when badly stuck
                stuck_count += 1
                if stuck_count > 10:
                    alt_neighbors = [
                        n for n in neighbors
                        if self.geo.layout_map.get(n, '.') != '|' and n not in self.geo.walls
                    ]
                    if alt_neighbors:
                        valid_n = alt_neighbors
                        force_random_move = True
                # If still none, wait briefly and retry with forced re-eval
                if not valid_n:
                    if stuck_count > 8:
                        steps_since_eval = 999  # force door re-eval sooner
                        force_random_move = True
                    yield self.env.timeout(0.25)  # faster retry
                    continue

            # Move Strategy
            if force_random_move:
                 # Just pick ANY valid neighbor to break deadlock
                 next_step = random.choice(valid_n)
            else:
                 # Move to neighbor with MINIMUM distance
                 # Shuffle to prevent herds always picking Top-Left bias
                 random.shuffle(valid_n)
                 next_step = min(valid_n, key=lambda k: dist_map[k])
            
            nr, nc = next_step
            
            # Safety check: Ensure we're not trying to move to a wall
            next_type = self.geo.layout_map.get((nr, nc), '.')
            if next_type == '|' or (nr, nc) in self.geo.walls:
                stuck_count += 1
                yield self.env.timeout(random.uniform(0.02, 0.06))
                continue
            
            # Attempt Move with Timeout (Deadlock Fix)
            # More generous to allow progress under congestion
            # Stuck 0 -> ~1.0s, Stuck 5 -> ~3.0s (capped at 3.0s)
            wait_time = 1.0 + min(stuck_count, 5) * 0.4
            wait_time = min(wait_time, 3.0)
            
            # FORCE MERGE: If moving Seat -> Aisle, give long patience (never relinquish)
            curr_type = self.geo.layout_map.get((curr_r, curr_c), '.')
            next_type = self.geo.layout_map.get((nr, nc), '.')
            if curr_type == 'S' and next_type != 'S':
                 wait_time = None  # Infinite patience to hold merge spot
            
            new_reqs, old_reqs = yield from self.move_step(p, nr, nc, current_reqs, timeout=wait_time) 
            
            if new_reqs is None:
                # Move Failed (Timeout/Blocked)
                stuck_count += 1
                # Wait random time to desync
                yield self.env.timeout(random.uniform(0.1, 0.5))
                continue
            
            # Success - validate position before updating
            self._validate_position(nr, nc, p.id)
            stuck_count = 0     
            current_reqs = new_reqs
            curr_r, curr_c = nr, nc

        # 5. Door Physics & Flow Rate (serialized by door resource)
        door_res = self.door_resources[target_door.name]
        with door_res.request() as door_req:
            yield door_req  # FIFO, capacity=1

            q_size = door_res.count + len(door_res.queue)
            
            if target_door.exit_type == "Type A": base_delay = self.cfg.behavior.flow_rate_type_a
            elif target_door.exit_type == "Type III": base_delay = self.cfg.behavior.flow_rate_type_3
            else: base_delay = self.cfg.behavior.flow_rate_type_1
            
            # Override with Specific Door Rate if defined
            if target_door.name in self.cfg.behavior.door_flow_rates:
                 base_delay = self.cfg.behavior.door_flow_rates[target_door.name]
            
            # SLIDE DELAY: Cannot exit if slides aren't ready
            slide_ready_time = getattr(self.cfg.behavior, 'slide_delay_sec', 0.0)
            time_until_ready = max(0, slide_ready_time - self.env.now)
            if time_until_ready > 0:
                 yield self.env.timeout(time_until_ready)
            
            # Queue Density Penalty (Arching/Jamming) - gentler to maintain flow
            jam_factor = 1.0 + (self.cfg.behavior.panic_level * q_size * 0.02)
            yield self.env.timeout(base_delay * jam_factor)
            
            # Record exit stats
            p.t_exit = self.env.now
            p.exit_door = target_door.name
            self.exit_records.append({
                'door': target_door.name,
                't_exit': p.t_exit,
                'p_type': p.p_type
            })


        # 6. Escape
        for req in current_reqs: req.resource.release(req)
        p.curr_r, p.curr_c = -999, -999
        
        if self.pbar: self.pbar.update(1)
        evacuated = len([x for x in self.passengers if x.curr_r == -999])
        if evacuated == len(self.passengers):
            self.all_evacuated_event.succeed()

    def boarding_control(self):
        door_choice = self.cfg.primary_door
        split_row = self.cfg.lopa.cross_aisle_row
        def run_stream(pax_list, door_name):
            try: d_cfg = next(d for d in self.cfg.lopa.door_locations if d.name == door_name)
            except: return
            rate = self.cfg.behavior.arrival_rate_l1 if door_name=="L1" else self.cfg.behavior.arrival_rate_l2
            if self.pbar: print(f"Door {door_name} Start | Count: {len(pax_list)} | Rate: {rate}")
            for p in pax_list:
                self.env.process(self.passenger_process(p, d_cfg))
                gap = random.uniform(rate*0.8, rate*1.5)
                yield self.env.timeout(gap)

        if door_choice == "L1+L2":
            pax_l1 = [p for p in self.passengers if p.row < split_row]
            pax_l2 = [p for p in self.passengers if p.row >= split_row]
            self.env.process(run_stream(pax_l1, "L1"))
            self.env.process(run_stream(pax_l2, "L2"))
            yield self.env.timeout(0.1) 
        else:
            yield from run_stream(self.passengers, door_choice)

    def passenger_process(self, p, door):
        p.t_enter = self.env.now
        curr_r, curr_c = door.row, door.col
        current_reqs = yield from self.acquire_node(p, curr_r, curr_c)
        p.curr_r, p.curr_c = curr_r, curr_c
        main_cross = self.cfg.lopa.cross_aisle_row
        target_aisle = p.aisle_col # FIX: Use stored aisle
        
        path_row = main_cross
        if p.row < main_cross and door.row < main_cross: path_row = door.row

        yield self.env.timeout(random.uniform(1.0, 3.0))

        # Lateral
        if curr_c != target_aisle:
            d = 1 if target_aisle > curr_c else -1
            while curr_c != target_aisle:
                curr_c += d
                current_reqs = yield from self.move_step(p, curr_r, curr_c, current_reqs)
        
        # Vertical
        target_row_leg1 = path_row
        if curr_c == target_aisle: target_row_leg1 = p.row
        if curr_r != target_row_leg1:
            d = 1 if target_row_leg1 > curr_r else -1
            while curr_r != target_row_leg1:
                curr_r += d
                current_reqs = yield from self.move_step(p, curr_r, curr_c, current_reqs)
        
        # Final Lateral
        if curr_c != target_aisle:
            yield self.env.timeout(random.uniform(1.5, 3.0)) 
            d = 1 if target_aisle > curr_c else -1
            while curr_c != target_aisle:
                curr_c += d
                current_reqs = yield from self.move_step(p, curr_r, curr_c, current_reqs)
        
        # Final Vertical
        if curr_r != p.row:
            d = 1 if p.row > curr_r else -1
            while curr_r != p.row:
                curr_r += d
                current_reqs = yield from self.move_step(p, curr_r, curr_c, current_reqs)

        stow_duration = random.expovariate(1.0 / p.stow_time)
        yield self.env.timeout(stow_duration)
        
        step = 1 if p.col > target_aisle else -1
        if p.col != target_aisle:
            for check_c in range(target_aisle + step, p.col + step, step):
                if (p.row, check_c) in self.occupied_seats:
                    yield self.env.timeout(self.cfg.behavior.seat_shuffle_sec)
        
        p.t_seated = self.env.now
        for req in current_reqs: req.resource.release(req)
        p.curr_r, p.curr_c = -99, -99 
        self.occupied_seats[(p.row, p.col)] = True
        if self.pbar: self.pbar.update(1)
        if len(self.occupied_seats) == len(self.passengers):
            self.all_seated_event.succeed()

    def acquire_node(self, p, r, c):
        # EXPLICIT WALL CHECK: Never allow passengers to acquire wall nodes
        char = self.geo.layout_map.get((r, c), '.')
        if char == '|' or (r, c) in self.geo.walls:
            raise ValueError(f"CRITICAL: Passenger {p.id} tried to acquire WALL at ({r}, {c}). This should never happen!")
        node = self.geo.get_node(r, c)
        reqs = [node.request()]
        if p.width_units > 1: reqs.append(node.request()) 
        yield simpy.AllOf(self.env, reqs)
        return reqs

    def move_step(self, p, next_r, next_c, current_reqs, timeout=None):
        # Shorter per-hop reaction to improve flow
        reaction = random.uniform(0.2, 0.6)
        yield self.env.timeout(reaction)
        next_node = self.geo.get_node(next_r, next_c)
        
        # Deadlock Prevention: Timeout
        req1 = next_node.request()
        reqs = [req1]
        req2 = None
        if p.width_units > 1:
             req2 = next_node.request()
             reqs.append(req2)
        
        # Explicit AnyOf
        # Wait for (All Reqs) OR (Timeout)
        all_reqs_event = simpy.AllOf(self.env, reqs)
        timeout_event = self.env.timeout(timeout if timeout else 99999)
        
        results = yield simpy.AnyOf(self.env, [all_reqs_event, timeout_event])
        
        # Check if Reqs succeeded
        if not all(r.processed for r in reqs):
            # We timed out
            for r in reqs:
                if r.processed: r.resource.release(r)
                else: r.cancel() # Cancel pending request
            return None, current_reqs # Failed to move

        # Move physics
        yield self.env.timeout(0.8 / p.speed)
        
        # Release OLD spot
        for req in current_reqs: req.resource.release(req)
        
        # Validate position before setting
        self._validate_position(next_r, next_c, p.id)
        p.curr_r, p.curr_c = next_r, next_c
        return reqs, reqs

    def snapshot_loop(self):
        while True:
            if self.pbar and self.pbar.n >= self.pbar.total: break
            for p in self.passengers:
                if p.curr_r >= 0:
                    loc = (p.curr_r, p.curr_c)
                    self.heatmap_accum[loc] = self.heatmap_accum.get(loc, 0) + 1
            active = [{'r': p.curr_r, 'c': p.curr_c, 'type': p.p_type} for p in self.passengers if p.curr_r != -99 and p.curr_r != -999]
            seated = [{'r': p.row, 'c': p.col, 'type': p.p_type} for p in self.passengers if p.curr_r == -99]
            self.snapshots.append({'active': active, 'seated': seated})
            yield self.env.timeout(0.5)