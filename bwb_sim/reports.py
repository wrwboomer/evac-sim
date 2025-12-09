# FILE: bwb_sim/reports.py
import datetime

def get_report_string(sim):
    """Generates the text content of the simulation report."""
    
    cfg = sim.cfg
    
    # Calculate Stats
    total_pax = len(sim.passengers)
    seated_pax = len([p for p in sim.passengers if p.curr_r == -99])
    
    # Calculate completion time
    if seated_pax == total_pax:
        # Get the max seated time
        duration = max([p.t_seated for p in sim.passengers]) if sim.passengers else 0
    else:
        duration = sim.env.now

    mins = int(duration // 60)
    secs = int(duration % 60)
    time_str = f"{mins:02d}:{secs:02d}"

    # Build Report Content
    lines = []
    lines.append("==========================================")
    lines.append("       BWB BOARDING SIMULATION REPORT     ")
    lines.append("==========================================")
    lines.append(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("--- RESULTS ---")
    lines.append(f"Total Time:       {time_str}")
    lines.append(f"Passengers:       {seated_pax} / {total_pax}")
    lines.append(f"Completion:       {(seated_pax/total_pax)*100:.1f}%")
    lines.append("")
    lines.append("--- CONFIGURATION ASSUMPTIONS ---")
    lines.append(f"Aircraft:         {cfg.lopa.name}")
    lines.append(f"Boarding Door:    {cfg.primary_door}")
    lines.append(f"Strategy:         {cfg.strategy}")
    lines.append(f"Load Factor:      {cfg.load_factor * 100:.0f}%")
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