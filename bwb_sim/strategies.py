# FILE: bwb_sim/strategies.py
import random

def apply_strategy(passengers, strategy_name, lopa_sections):
    """Sorts the passenger list based on the chosen strategy, respecting Groups."""
    
    print(f"Applying Boarding Strategy: {strategy_name}")

    # 1. Group passengers so families stick together
    groups = {}
    for p in passengers:
        if p.group_id not in groups:
            groups[p.group_id] = []
        groups[p.group_id].append(p)
    
    # Convert map to list of lists [[p1], [p2, p3, p4], [p5]...]
    grouped_list = list(groups.values())

    # 2. Define Sort Keys for the GROUPS (using the first member as representative)
    def get_rep(grp): return grp[0]

    if strategy_name == "random" or strategy_name == "realistic_random":
        # Realistic Random: Business first, then Economy
        # We assume Business class is physically in the front rows
        biz_groups = [g for g in grouped_list if get_rep(g).row <= 5]
        eco_groups = [g for g in grouped_list if get_rep(g).row > 5]
        
        random.shuffle(biz_groups)
        random.shuffle(eco_groups)
        
        # Combine
        sorted_groups = biz_groups + eco_groups
        
    elif strategy_name == "front_to_back":
        sorted_groups = sorted(grouped_list, key=lambda g: get_rep(g).row)
        
    elif strategy_name == "back_to_front":
        sorted_groups = sorted(grouped_list, key=lambda g: -get_rep(g).row)
        
    elif strategy_name == "outside_in":
        # WilMA: Sort by distance from aisle
        sorted_groups = sorted(grouped_list, key=lambda g: -abs(get_rep(g).col - get_rep(g).aisle_col))
        
    elif strategy_name == "zones":
        # Shuffle first, then sort by zone blocks
        random.shuffle(grouped_list)
        for g in grouped_list:
            get_rep(g).zone_id = (get_rep(g).row // 5) * -1
        sorted_groups = sorted(grouped_list, key=lambda g: get_rep(g).zone_id)
        
    else:
        sorted_groups = grouped_list # Fallback

    # 3. Flatten back to single list
    passengers[:] = [p for grp in sorted_groups for p in grp]
    return passengers