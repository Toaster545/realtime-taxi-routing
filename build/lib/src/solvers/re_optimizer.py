from src.solvers.offline_solver import OfflineSolver
from src.utilities.enums import DestroyMethod
from src.solvers.solver import Solver
from src.utilities.config import SimulationConfig
from typing import Any, Dict, List



class ReOptimizer(Solver):
    """Re-optimize vehicle routing and trip-route assignment using destroy-and-repair (LNS) ideas.

    Includes three destroy methods:
        1. destroy_fix_arrival_times
        2. destroy_fix_variables
        3. destroy_bonus

    Attributes:
    ------------
        destroy_method : DestroyMethod(Enum)
            Method used for destruction in the LNS algorithm.
        initial_solution : dict
            Initial values for decision variables (X, Y, Z, U, assignment_dict).

        vehicle_request_assign : Dict[int, VehicleState]
            Mapping vehicle id to VehicleState (inherited from Solver). Each state holds: vehicle,
            assigned_requests, departure_stop, departure_time, last_stop, last_stop_time, assign_possible,
            random_number; used to save assignments and build route plans.

        durations : dictionary
            travel time matrix between possible stop points
            example: for duration between destination of trip_i and the origin of trip_j use:
                     self.durations[trip_i.destination.label][trip_i.origin.label]

        costs: dictionary
            driving costs (it works based on location ids like durations)
        algorithm: Algorithm(Enum)
            The optimization algorithm utilized for planning and assigning trips to vehicles.
        objective: Objectives(Enum)
            The objective used to evaluate the effectiveness of the plan (e.g., maximizing profit or minimizing wait time).
        objective_value: float
            The objective value from served requests.
        total_customers_served: int
            The count of customers successfully served.
    """

    def __init__(self,
                 network: Any,
                 vehicles: List[Any],
                 simulation_config: SimulationConfig) -> None:
        super().__init__(network, vehicles, simulation_config)
        self.initial_solution : Dict[str, Any] = {}
        self.destroy_method = simulation_config.algorithm_params["destroy_method"]


    def re_optimizer(self, K, P_not_served, rejected_trips):
        """Re-optimize the solution using destroy and repair (LNS).

        Input:
        ------------
            K : set of vehicles
            P_not_served : set of customers not yet served
            rejected_trips : list of trips rejected in the optimization process.

        Steps:
            1. Create the mathematical model (OfflineSolver).
            2. If initial_solution exists, destroy (fix) part of it according to destroy_method.
            3. Repair (re-optimize) with the MIP solver and extract solution.
            4. Save the final solution to initial_solution.
        """

        # Create and configure the offline model
        offline_model = OfflineSolver(self.network, self.objective)
        offline_model.create_model(K, P_not_served, self.vehicle_request_assign)

        if self.initial_solution:
            if self.destroy_method == DestroyMethod.FIX_ARRIVALS:
                # destroy by fixing a time window around the arrival times in the initial solution
                self.destroy_fix_arrival_times(P_not_served, offline_model)

            elif self.destroy_method == DestroyMethod.FIX_VARIABLES:
                # destroy by fixing some of the variables based on the initial solution
                self.destroy_fix_variables(K, P_not_served, offline_model)
            elif self.destroy_method == DestroyMethod.BONUS:
                # destroy the solution by your suggested function
                self.destroy_bonus(K, P_not_served, offline_model)

        # add objective
        offline_model.define_objective(K, P_not_served, self.vehicle_request_assign)

        # solve and get solution
        offline_model.solve()
        offline_model.extract_solution(K, P_not_served, rejected_trips, self.vehicle_request_assign)

        self.save_solution(offline_model)

    def save_solution(self, offline_model: OfflineSolver):
        """Save the solution from the offline model into initial_solution.

        Input:
        ------------
            offline_model : OfflineSolver instance (Gurobi MIP model).
        """
        # Extracting values of decision variables
        self.Y: Dict[Any, Dict[Any, float]] = {
            key[0]: {sub_key[1]: var.X for sub_key, var in offline_model.Y_var.items() if sub_key[0] == key[0]}
            for key in offline_model.Y_var.keys()
        }
        self.X: Dict[Any, Dict[Any, float]] = {
            key[0]: {sub_key[1]: var.X for sub_key, var in offline_model.X_var.items() if sub_key[0] == key[0]}
            for key in offline_model.X_var.keys()
        }
        self.Z: Dict[Any, float] = {key: var.X for key, var in offline_model.Z_var.items()}
        self.U: Dict[Any, float] = {key: var.X for key, var in offline_model.U_var.items()}

        assignment_dict: Dict[Any, Dict[str, List[Any]]] = {
            vehicle_id: {
                'assigned_requests': state.assigned_requests
            }
            for vehicle_id, state in self.vehicle_request_assign.items()
        }

        self.initial_solution = {
            'X': self.X,
            'Y': self.Y,
            'U': self.U,
            'Z': self.Z,
            'assignment_dict': assignment_dict
        }

    def destroy_fix_arrival_times(self, P, offline_model: OfflineSolver) -> None:
        """Fix pickup times to a time window around values in initial_solution (e.g. ±2 min).

        Input:
        ------------
            P : set of customers to serve
            offline_model : OfflineSolver instance (Gurobi MIP model).

        """
        WINDOW = 120  # ±2 minutes in seconds
        U_prev = self.initial_solution['U']
        for f_i in P:
            if f_i.id in U_prev:
                u_val = U_prev[f_i.id]
                lb = max(f_i.ready_time, u_val - WINDOW)
                ub = min(f_i.latest_pickup, u_val + WINDOW)
                offline_model.U_var[f_i.id].LB = lb
                offline_model.U_var[f_i.id].UB = ub
        offline_model.model.update()


    def destroy_fix_variables(self, K, P, offline_model: OfflineSolver):
        """ Fix some of Y_var, X_var variables based on the initial solution.

        Input:
        ------------
            K : set of vehicles
            P : set of customers to serve
            offline_model : OfflineSolver instance (Gurobi model).

        Hint:
            - Forbid the arcs that goes from one request to another one that were in different vehicle
            - Forbid the arcs that goes from departing node of a vehicle to other requests that were in different
                  vehicle
        """
        # Build trip -> vehicle mapping from previous solution
        trip_vehicle = {}
        for vehicle_id, data in self.initial_solution['assignment_dict'].items():
            for trip in data['assigned_requests']:
                trip_vehicle[trip.id] = vehicle_id

        # Forbid Y[k, i] when trip i was previously served by a different vehicle
        for f_k in K:
            for f_i in P:
                if f_i.id in trip_vehicle and trip_vehicle[f_i.id] != f_k.id:
                    offline_model.Y_var[f_k.id, f_i.id].UB = 0

        # Forbid X[i, j] when trips i and j were previously in different vehicles
        for f_i in P:
            for f_j in P:
                if f_i != f_j:
                    v_i = trip_vehicle.get(f_i.id)
                    v_j = trip_vehicle.get(f_j.id)
                    if v_i is not None and v_j is not None and v_i != v_j:
                        offline_model.X_var[f_i.id, f_j.id].UB = 0

        offline_model.model.update()


    def destroy_bonus(self, K, P, offline_model: OfflineSolver):
        """Custom destroy method: fix well-served trips, free poorly-served ones.

        Trips with low wait time in the previous solution are "well-served" and their
        vehicle assignments are fixed. Trips with high wait time are freed so the
        solver can find better placements for them.

        Input:
        ------------
            K : set of vehicles
            P : set of customers to serve
            offline_model : OfflineSolver instance (Gurobi model).
        """
        U_prev = self.initial_solution['U']
        Z_prev = self.initial_solution['Z']

        served_trips = [f for f in P if f.id in Z_prev and Z_prev[f.id] > 0.5]
        served_trips.sort(key=lambda f: U_prev.get(f.id, f.ready_time) - f.ready_time)

        fix_set = {f.id for f in served_trips[: len(served_trips) // 2]}

        trip_vehicle = {}
        for vehicle_id, data in self.initial_solution['assignment_dict'].items():
            for trip in data['assigned_requests']:
                trip_vehicle[trip.id] = vehicle_id

        for f_k in K:
            for f_i in P:
                if f_i.id in fix_set and trip_vehicle.get(f_i.id) != f_k.id:
                    offline_model.Y_var[f_k.id, f_i.id].UB = 0

        for f_i in P:
            for f_j in P:
                if f_i != f_j:
                    i_fixed = f_i.id in fix_set
                    j_fixed = f_j.id in fix_set
                    if i_fixed or j_fixed:
                        if trip_vehicle.get(f_i.id) != trip_vehicle.get(f_j.id):
                            offline_model.X_var[f_i.id, f_j.id].UB = 0

        offline_model.model.update()

