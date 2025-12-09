# FILE: bwb_sim/agents.py
from dataclasses import dataclass

@dataclass
class Passenger:
    id: int
    row: int
    col: int
    
    # Persona
    p_type: str = "economy" # economy, business, family, prm
    group_id: int = -1      # To keep families together
    
    # Navigation State
    aisle_col: int = 0
    
    # FIX: Initialize to -1 (Not in system yet). 
    # -99 is reserved for "Seated".
    curr_r: int = -1
    curr_c: int = -1
    
    # Physics Properties
    speed: float = 1.1
    stow_time: float = 3.0
    width_units: int = 1    # 1 = Standard, 2 = Wide (PRM)
    
    # Metrics
    t_enter: float = 0.0
    t_seated: float = 0.0