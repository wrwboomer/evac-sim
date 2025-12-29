# Bottleneck Analysis: Why do Heatmaps still show congestion?

## The "Funnel" Physics
You are observing a classic "Funnel Effect" in fluid dynamics and crowd simulation.

1.  **The Ultimate Bottleneck is the Door**:
    *   Even with **Dual Flow**, the Door allows **2 people** to exit at a time (Limit: ~200 pax/min).
    *   The **Cross-Aisle** (Double Width) allows **6 people** to stand side-by-side (Capacity 6).
    *   **The Mismatch**: The Cross-Aisle can deliver people to the door *faster* than the door can process them.
    *   **Result**: Passengers pile up at the door threshold. Even though the aisle is wide, the flow stops at the door.

2.  **Heatmap Interpretation**:
    *   The Heatmap visualizes **Time Spent** in a location.
    *   Because **EVERYONE** must pass through the door and the cross-aisle to exit, and they spend the most time waiting there (due to the queue), these areas will **ALWAYS** appear as the "hottest" spots.
    *   A "Red" cross-aisle doesn't mean the widening failed; it means that's where the line for the exit is.

## Did the changes help?
Yes, significantly, but visual "redness" persists because the queueing moved:
*   **Before (Single/Single)**: The queue backed up all the way into the seat rows because the single aisle was slow.
*   **Now (Double/Dual)**: The cross-aisle acts as a "Waiting Room". It holds more people closer to the door. This clears the main cabin faster, even if they still have to wait at the door itself.

## Conclusion
The persistence of the bottleneck at the door and cross-aisle is **physically correct**.
*   If we did *not* see a bottleneck at the door, it would mean the aisles were too slow to feed it (Bad).
*   Seeing the bottleneck at the door means the aisles are flowing efficiently and the door is properly maximizing its output (Good).
