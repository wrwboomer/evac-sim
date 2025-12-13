# FILE: bwb_sim/reports.py
import datetime
import numpy as np
from collections import defaultdict

def _time_str(seconds: float) -> str:
    return f"{seconds:.1f} sec"

def get_report_string(sim):
    """Generates the text content of the simulation report."""
    cfg = sim.cfg
    total_pax = len(sim.passengers)
    lines = []
    lines.append("==========================================")
    if cfg.mode == "egress":
        lines.append("     BWB EMERGENCY EVACUATION REPORT      ")
    else:
        lines.append("       BWB BOARDING SIMULATION REPORT     ")
    lines.append("==========================================")
    lines.append(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Aircraft:         {cfg.lopa.name}")
    lines.append(f"Load Factor:      {cfg.load_factor * 100:.0f}%")
    lines.append("")

    if cfg.mode != "egress":
        # Boarding report (legacy)
        seated_pax = len([p for p in sim.passengers if p.curr_r == -99])
        duration = sim.env.now if seated_pax != total_pax else max([p.t_seated for p in sim.passengers]) if sim.passengers else 0
        lines.append("--- RESULTS ---")
        lines.append(f"Total Time:       {_time_str(duration)}")
        if total_pax > 0:
            spp = duration / total_pax
            lines.append(f"Avg sec/pax:      {spp:.1f} sec/pax")
        lines.append(f"Passengers:       {seated_pax} / {total_pax}")
        lines.append(f"Completion:       {(seated_pax/total_pax)*100:.1f}%")
        lines.append("")
        lines.append("--- CONFIGURATION ASSUMPTIONS ---")
        lines.append(f"Boarding Door:    {cfg.primary_door}")
        lines.append(f"Strategy:         {cfg.strategy}")
        lines.append("")
        lines.append("--- BEHAVIOR SETTINGS ---")
        lines.append(f"Avg Walk Speed:   {cfg.behavior.speed_mps_mean} m/s")
        lines.append(f"Avg Stow Time:    {cfg.behavior.stow_time_mean} sec")
        lines.append(f"Seat Shuffle:     {cfg.behavior.seat_shuffle_sec} sec")
        lines.append("")
        lines.append("--- DOOR SETTINGS ---")
        lines.append(f"L1 Entry Rate:    {cfg.behavior.arrival_rate_l1} sec/pax")
        lines.append(f"L2 Entry Rate:    {cfg.behavior.arrival_rate_l2} sec/pax")
        lines.append("==========================================")
        return "\n".join(lines)

    # EGRESS REPORT
    evac_pax = [p for p in sim.passengers if getattr(p, "t_exit", 0) > 0]
    evacuated = len(evac_pax)
    duration = sim.env.now
    spp = duration / total_pax if total_pax else 0
    faa_pass_90 = (evacuated == total_pax and duration <= 90.0)

    lines.append("--- RESULTS ---")
    lines.append(f"Total Time:       {_time_str(duration)}")
    lines.append(f"Avg sec/pax:      {spp:.1f} sec/pax")
    lines.append(f"Evacuated:        {evacuated} / {total_pax}")
    lines.append(f"FAA 90s Pass:     {'YES' if faa_pass_90 else 'NO'}")
    lines.append("")
    
    # --- FAA CERTIFICATION CHECK ---
    # Calculate Metrics
    cnt_female = sum(1 for p in sim.passengers if getattr(p, "is_female", False))
    cnt_over50 = sum(1 for p in sim.passengers if getattr(p, "is_over_50", False))
    cnt_both = sum(1 for p in sim.passengers if getattr(p, "is_female", False) and getattr(p, "is_over_50", False))
    cnt_infants = sim.cfg.pax_mix.simulated_infants
    
    pct_female = (cnt_female / total_pax) * 100 if total_pax else 0
    pct_over50 = (cnt_over50 / total_pax) * 100 if total_pax else 0
    pct_both = (cnt_both / total_pax) * 100 if total_pax else 0
    
    lines.append("--- FAA APPENDIX J CERTIFICATION CHECK ---")
    lines.append(f"1. Total Count:   {total_pax}")
    lines.append(f"2. Female >= 40%:  {pct_female:.1f}%  [{'PASS' if pct_female >= 39.9 else 'FAIL'}]")
    lines.append(f"3. Over 50 >= 35%: {pct_over50:.1f}%  [{'PASS' if pct_over50 >= 34.9 else 'FAIL'}]")
    lines.append(f"4. Overlap >= 15%: {pct_both:.1f}%  [{'PASS' if pct_both >= 14.9 else 'FAIL'}]") # 14.9 tolerance for rounding
    lines.append(f"5. Infants >= 3:   {cnt_infants}      [{'PASS' if cnt_infants >= 3 else 'FAIL'}]")
    lines.append(f"6. Time <= 90s:    {duration:.1f}s   [{'PASS' if duration <= 90.0 else 'FAIL'}]")
    
    all_passed = (pct_female >= 39.9 and pct_over50 >= 34.9 and pct_both >= 14.9 and cnt_infants >= 3 and duration <= 90.0)
    lines.append(f"OVERALL STATUS:   {'[ CERTIFIED ]' if all_passed else '[ FAILED ]'}")
    lines.append("")

    # Door stats
    door_times = defaultdict(list)
    for p in evac_pax:
        door_times[p.exit_door].append(p.t_exit)
    lines.append("--- DOOR EVACUATION ---")
    for d in cfg.lopa.door_locations:
        times = door_times.get(d.name, [])
        count = len(times)
        t_door = max(times) if times else 0
        lines.append(f"{d.name}: {count:3d} pax | Time: {_time_str(t_door)}")
    lines.append("")

    # Passenger type stats
    type_times = defaultdict(list)
    for p in evac_pax:
        type_times[p.p_type].append(p.t_exit)
    lines.append("--- PASSENGER TYPES ---")
    for t, vals in type_times.items():
        arr = np.array(vals)
        lines.append(f"{t}: avg {_time_str(np.mean(arr))} | fastest {_time_str(np.min(arr))} | slowest {_time_str(np.max(arr))}")
    lines.append("")

    # Demographics (female / over 50)
    demo_times = {"Female": [], "Over 50": [], "Other": []}
    for p in evac_pax:
        if getattr(p, "is_over_50", False):
            demo_times["Over 50"].append(p.t_exit)
        elif getattr(p, "is_female", False):
            demo_times["Female"].append(p.t_exit)
        else:
            demo_times["Other"].append(p.t_exit)
    lines.append("--- DEMOGRAPHICS ---")
    for label, vals in demo_times.items():
        if vals:
            arr = np.array(vals)
            lines.append(f"{label}: avg {_time_str(np.mean(arr))} | fastest {_time_str(np.min(arr))} | slowest {_time_str(np.max(arr))}")
        else:
            lines.append(f"{label}: no data")

    lines.append("==========================================")
    return "\n".join(lines)