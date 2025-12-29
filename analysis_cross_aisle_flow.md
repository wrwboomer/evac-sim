# Analysis: Why are the Cross-Aisles Empty?

You observed that when **L1 and L3 are blocked**, there is **no traffic flow** across the top (Row 0) and bottom (Row 19) cross-aisles (the red ovals).

This is **correct and expected behavior** caused by the pathfinding logic minimizing travel distance.

## The Logic (Path of Least Resistance)
Passengers always choose the **closest active exit**. Let's check the math for a passenger in the Left Aisle:

### 1. Top Left Passenger (near blocked L1) needs to find an exit.
*   **Option A (Go across to R1):** They must walk across the entire width of the plane (Row 0).
    *   Distance: **~26 meters/steps** (Width of fuselage).
*   **Option B (Go down to L2):** They must walk down the aisle to the L2 door.
    *   Distance: **~8 meters/steps** (Rows 1 to 8).
*   **Result:** **8 is much less than 26**.
*   **Behavior:** Passengers realize R1 is too far away. They turn around and flow **South** down the aisle to L2.
*   **Visual Consequence:** The top cross-aisle stays empty because no one "needs" to cross it. L2 is closer.

### 2. Bottom Left Passenger (near blocked L3) needs to find an exit.
*   **Option A (Go across to R3):** Walk across the back row.
    *   Distance: **~26 meters/steps**.
*   **Option B (Go up to L2):** Walk up the aisle to L2.
    *   Distance: **~10 meters/steps** (Rows 9 to 18).
*   **Result:** **10 is much less than 26**.
*   **Behavior:** Passengers flow **North** up the aisle to L2.
*   **Visual Consequence:** The bottom cross-aisle stays empty.

## Summary
The simulation shows that in a Blended Wing Body, the **fuselage is so wide** that it is often faster to go to a different exit on the *same side* (Forward/Aft) than to cross to the *opposite side* (Left/Right). The empty cross-aisles confirm the agents are making the smart, energy-efficient choice!
