# Dual Flow Door Impact Analysis

## Observation
The user noted that changing Type A doors from Single Flow (Capacity 1) to Dual Flow (Capacity 2) did not significantly reduce the total evacuation time.

## Root Cause Analysis
This behavior indicates that the **doors were not the bottleneck** in the original simulation. The bottleneck lies upstream in the **aisles**.

### 1. Throughput Comparison
*   **Door Capacity (Original):**
    *   Processing Time: 0.6 seconds/person (Config: `flow_rate_type_a`)
    *   Max Throughput: ~100 passengers/minute.
*   **Door Capacity (Dual Flow):**
    *   Processing Time: 0.6 seconds/person (2 parallel streams)
    *   Max Throughput: ~200 passengers/minute.
*   **Aisle Throughput (Bottleneck):**
    *   The Economy section (`SSS-SSS`) relies on single-width aisles (`-`).
    *   Passenger Movement Speed: ~1.0 m/s.
    *   Movement "Step" Overhead in Simulation: ~0.8 seconds/step.
    *   **Max Aisle Feed Rate:** ~75 passengers/minute (1 person every 0.8s).

### 2. Conclusion
Since the single-file aisles can only deliver passengers to the door at a rate of **~75 pax/min**, the door (even at single capacity of **100 pax/min**) was already waiting for people. Increasing the door capacity to **200 pax/min** widens the "pipe" at the exit, but the "flow" entering that pipe remains limited by the narrow aisles.

To see the benefit of Dual Flow doors, the arrival rate at the doors must exceed 100 pax/min. This would happen if:
1.  Multiple aisles converged on a single door (e.g., Cross-Aisles).
2.  The aisles themselves were wider (allowing parallel movement).
3.  Passenger walking speed was significantly strictly higher.

### 3. Verification
The total evacuation time is essentially:
`Total Time = Time_for_last_person_to_reach_door + Door_Processing_Time`

For the last person, who is likely far back in the cabin, they walk into a door with **near-zero queue** because the door has been clearing people faster than they arrived. Thus, their exit time is dominated purely by their walking speed, which didn't change.
