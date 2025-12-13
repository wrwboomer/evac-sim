# FILE: bwb_sim/config.py
from typing import List, Dict, Optional, Literal
from pydantic import BaseModel

class DoorLocation(BaseModel):
    name: str
    row: int
    col: int
    side: str
    exit_type: str = "Type A" 
    active: bool = True

class RowSection(BaseModel):
    class_name: str
    start_row: int
    end_row: int
    layout_string: str
    seat_pitch_m: float

class AircraftLOPA(BaseModel):
    name: str
    rows_total: int
    cross_aisle_row: int
    sections: List[RowSection]
    door_locations: List[DoorLocation]

class PassengerMix(BaseModel):
    # FAA Appendix J Demographics
    female_pct: int = 40      # FAA requires >= 40%
    over_50_pct: int = 35     # FAA requires >= 35%
    simulated_infants: int = 3  # FAA requires 3 dolls carried by passengers
    
    # Custom Mix
    business_pct: float = 15.0
    family_pct: float = 15.0
    prm_pct: float = 2.0

class Behavior(BaseModel):
    # --- BOARDING SPEEDS (Granular) ---
    speed_business: float = 1.4
    speed_economy: float = 0.8
    speed_family: float = 0.7
    speed_prm: float = 0.4
    
    # --- BOARDING FRICTION ---
    speed_mps_mean: float = 0.6 # Fallback
    stow_time_mean: float = 20.0       
    seat_shuffle_sec: float = 20.0     
    arrival_rate_l1: float = 2.5       
    arrival_rate_l2: float = 2.0   
    
    # --- EGRESS PHYSICS ---
    evac_speed_mean: float = 1.5       
    reaction_time_mean: float = 2.0    
    panic_level: float = 0.5
    
    # --- EGRESS: CERTIFICATION VARS ---
    visibility_factor: float = 1.0     # 1.0=Clear, 0.5=Smoke
    slide_delay_sec: float = 10.0      # Inflation time
    active_exits: Dict[str, bool] = {} # Override LOPA Active stats
    door_flow_rates: Dict[str, float] = {} # Specific rates per door (sec/pax)

    # --- FLOW RATES (Defaults) ---
    flow_rate_type_a: float = 0.6
    flow_rate_type_1: float = 1.3
    flow_rate_type_3: float = 4.0

class SimConfig(BaseModel):
    lopa: AircraftLOPA
    behavior: Behavior = Behavior()
    pax_mix: PassengerMix = PassengerMix()
    primary_door: str = "L2"
    strategy: str = "random"
    load_factor: float = 1.0
    animation: bool = True
    save_dir: str = "output"
    mode: str = "egress" 

    @classmethod
    def from_json(cls, path: str):
        import json
        with open(path, 'r') as f:
            return cls(**json.load(f))