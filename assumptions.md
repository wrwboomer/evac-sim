# Evacuation Simulation Assumptions

## FAA Appendix J Demographics
To comply with **14 CFR Part 25 Appendix J** for Emergency Evacuation Demonstrations, the simulation enforces the following demographic distribution:

1.  **Female Passengers:** At least **40%** of the total passenger count.
2.  **Over 50 Years Old:** At least **35%** of the total passenger count.
3.  **Overlap Requirement:** At least **15%** of the total passengers are **BOTH** Female and Over 50 Years Old.
4.  **Infants:** Three life-size dolls (simulating infants) are carried by passengers (not included in total headcount).

*Note: The simulation engine explicitly constructs the passenger list to ensure these overlap requirements are met or exceeded, provided the user-configured percentages allow for it (e.g., if you set Females to 10%, strictly meeting the 15% overlap is impossible).*

## Passenger Mix
The user can additionally configure "Behavioral" categories which determine base walking speeds:
-   **Business:** Fast walkers, quick stowage.
-   **Families:** Slower groups, longer stowage.
-   **PRM (Persons with Reduced Mobility):** Significantly slower speed, wider path.
-   **Economy:** Standard speed (remainder of passengers).

*These behavioral types are independent of the demographic flags (Female/Over 50). A Business passenger can be Female, Over 50, both, or neither.*
