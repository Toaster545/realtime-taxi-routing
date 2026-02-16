from dataclasses import dataclass, field
from typing import Any, Dict


from src.utilities.enums import (
    Algorithm,
    Objectives,
    SolutionMode,
)

@dataclass
class SimulationConfig:
    """
    objective : Objectives(Enum)
            The optimization objective to achieve (e.g., profit maximization).
                - total_profit: total profit of served requests (fare minus cost)
                - total_revenue: total fare (revenue) of served requests
                - total_cost: total driving cost of all routes
                - total_customers: total number of served customers
                - waiting_time: total wait time of customers
                - total_empty_travel_time: total travel time on empty legs only
                - multi_objective: weighted combination of multiple objectives (see algorithm_params)

        algorithm : Algorithm(Enum)
            The optimization algorithm to use for routing and assignment.
                - MIP_SOLVER : using the Gurobi MIP solver to solve the problem
                - GREEDY : greedy approach to assign requests to vehicles
                - RANDOM : random algorithm to assign arrival requests to vehicles
                - RANKING : ranking method to assign arrival requests to vehicles
                - CONSENSUS : consensus online stochastic algorithm to assign arrival requests to vehicles
                - RE_OPTIMIZE: Algorithm to re-optimize the solution based on destroy and repair
        solution_modes: SolutionMode(Enum)
            The optimization mode based on the availability of request information
                - offline : all the requests revealed (known) at the start (release time = 0 for all requests)
                - fully_online : All requests are released exactly at their ready time
                - advance_notice : All requests are known a fixed amount of time before their ready time.
                - partial : a random percentage of requests are known at the start and for the rest release time is equal to the ready time

        known_portion: int
            percentage of requests that are known in advance
        advance_notice: int
            Fixed amount of time (in minutes) the requests are released before their ready time.
        time_window : int
            Time window for picking up the requests
        algorithm_params : Dict[str, Any]
            algorithm-specific parameters like:
                - cust_node_hour: float
                    the average rate of customers per node (in the network) per hour
                        - for small size tests select 0.2
                        - for medium size tests select 0.3
                        - for large size tests select 0.7

                - nb_scenario: int
                    Total number of scenarios to be solved for consensus

                - consensus_param: ConsensusParams(Enum)
                    The type of consensus algorithm:
                        - QUALITATIVE : A counter is incremented for the best request to assign at each scenario.
                        - QUANTITATIVE : The best request to assign is credited by the optimal solution value,
                                         rather than merely incrementing a counter.

                - destroy_method: DestroyMethod(Enum)
                    Method used for destruction in re-optimizing
                        - DEFAULT: Default destruction method (Complete re-optimization)
                        - FIX_VARIABLES: fix some of the variables in the model
                        - FIX_ARRIVALS: fix a time window around the arrival time
                        - BONUS: arbitrary destroy method as bonus

                - weight: float (optional, for objective multi_objective)
                    Weight w in [0, 1] for profit in the combined objective (cost weight is 1-w).
                    Default 1.

    """
    objective: Objectives = Objectives.TOTAL_CUSTOMERS
    algorithm: Algorithm = Algorithm.MIP_SOLVER
    solution_mode: SolutionMode = SolutionMode.OFFLINE
    known_portion: int = 100
    advance_notice: int = 0
    time_window: int = 3
    # Dictionary to hold algorithm-specific parameters
    algorithm_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Validate common parameters if necessary
        if not (0.0 <= self.known_portion <= 100.0):
            raise ValueError("known_portion must be between 0 and 100.")
        if self.advance_notice < 0:
            raise ValueError("advance_notice cannot be negative.")
        if self.time_window <= 0:
            raise ValueError("time_window must be positive.")


