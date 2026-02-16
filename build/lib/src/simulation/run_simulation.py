import os
import pandas as pd
from multimodalsim.simulator.simulation import Simulation
from multimodalsim.optimization.optimization import Optimization
from multimodalsim.observer.environment_observer import StandardEnvironmentObserver

from src.simulation.data_reader import TaxiDataReader
from src.simulation.taxi_dispatcher import TaxiDispatcher
from src.utilities.enums import Algorithm, SolutionMode
from src.utilities.config import SimulationConfig

def run_taxi_simulation(
        test_folder: str,
        graph_file_path: str,
        config: SimulationConfig
    ) -> tuple[dict, dict]:

    """ Function: Conducts a simulation of taxi dispatching, based on specified parameters.
        Input:
        ------------
        test_folder : str
            The directory path where the test files are located.
        graph_file_path : str
            The file path to the transportation network graph.

        config: SimulationConfig
            Configuration object containing all simulation parameters.

        Output:
        ------------
        info_dict : dict
            Summary of test inputs and simulation parameters.
        output_dict : dict
            Simulation output metrics and results.
    """

    # Display simulation parameters
    print("==================================================")
    print("Run Taxi Simulation with the following settings:")
    print(f"  Instance: {test_folder}")
    print(f"  Objective: {config.objective.value}")
    print(f"  Algorithm: {config.algorithm.value}")
    print(f"  Solution Mode: {config.solution_mode.value}")
    print(f"  Percentage Known (%): {config.known_portion}")
    print(f"  Advance Notice (min): {config.advance_notice}")
    print(f"  Time Window (min): {config.time_window}")
    if "weight" in config.algorithm_params:
        print(f"  Weight: {config.algorithm_params.get('weight', 0.5)}")

    if config.algorithm in [Algorithm.CONSENSUS]:
        print(f"  Number of Scenarios: {config.algorithm_params["nb_scenario"]}")
        print(f"  Customers per Node per Hour: {config.algorithm_params["cust_node_hour"]}")
        print(f"  Type of consensus algorithm:: {config.algorithm_params["consensus_param"].value}")

    if config.algorithm == Algorithm.RE_OPTIMIZE:
        print(f"  Re-optimizer Destroy Method: {config.algorithm_params["destroy_method"].value}")
    print("==================================================")

    # Run the simulation
    # Define file paths for requests, vehicles, and output directory
    requests_file_path = f"{test_folder}/customers.json"
    vehicles_file_path = f"{test_folder}/taxis.json"

    # Read and prepare data
    data_reader = TaxiDataReader(
        requests_file_path=requests_file_path,
        vehicles_file_path=vehicles_file_path,
        graph_from_json_file_path=graph_file_path,
        vehicles_end_time=10000,
    )
    network_graph = data_reader.load_graph(os.path.dirname(graph_file_path) + '/network.pkl')
    #    ut.draw_network(network_graph, os.path.dirname(graph_file_path))

    vehicles, routes_by_vehicle_id = data_reader.get_json_vehicles()
    trips = data_reader.get_json_trips(config)

    # Initialize simulation components
    dispatcher = TaxiDispatcher(
        network=network_graph,
        vehicles=vehicles,
        simulation_config=config,
    )
    opt = Optimization(dispatcher, freeze_interval=10)
    environment_observer = StandardEnvironmentObserver()

    # Initialize and run the simulation
    simulation = Simulation(
        optimization=opt,
        trips=trips,
        vehicles=vehicles,
        routes_by_vehicle_id=routes_by_vehicle_id,
        network=network_graph,
        environment_observer=environment_observer,
    )
    simulation.simulate()

    # Extract and process simulation output
    output_dict = dispatcher.extract_output()
    # Build a shorter, compact key: <instance>_<tw>_<obj_abbr>
    obj_type = str(output_dict['Objective type'])
    obj_abbr_map = {
        "total_profit": "tp",
        "total_revenue": "tr",
        "total_cost": "tc",
        "total_customers": "nc",
        "waiting_time": "wt",
        "total_empty_travel_time": "et",
        "multi_objective": "mo",
    }
    obj_abbr = obj_abbr_map.get(obj_type, obj_type[:3])
    unique_key = f"{os.path.basename(test_folder)}_{config.time_window}_{obj_abbr}"

    # Compile information about the test and results
    info_dict = {
        'Key': unique_key,
        'Test': os.path.basename(test_folder),
        '# Trips': len(trips),
        '# Vehicles': len(vehicles),
        'Solution Mode': config.solution_mode.value,
        'Time window (min)': config.time_window
    }
    if config.solution_mode == SolutionMode.PARTIAL_ONLINE:
        info_dict.update({'Known portion (%)': config.known_portion})

    if config.algorithm == Algorithm.CONSENSUS:
        info_dict.update({'# Scenarios': config.algorithm_params["nb_scenario"],
                          'Customer rate': config.algorithm_params["cust_node_hour"],
                          'Consensus type': config.algorithm_params["consensus_param"].value})

    if config.algorithm == Algorithm.RE_OPTIMIZE:
        info_dict.update({'Destroy Method': config.algorithm_params["destroy_method"].value})

    if "weight" in config.algorithm_params:
        info_dict.update({'weight': config.algorithm_params.get('weight', 0.5)})

    if config.solution_mode != SolutionMode.OFFLINE:
        Results_folder = os.path.join(os.path.dirname(test_folder), "Results")
        Offline_Solution_path = os.path.join(Results_folder, "TP1_simulation_results.csv")
        if os.path.exists(Offline_Solution_path):
            offline_df = pd.read_csv(Offline_Solution_path, index_col='Key')
            if unique_key in offline_df.index:
                offline_value = offline_df.loc[unique_key, 'Objective value']
                competitive_ratio = round(output_dict['Objective value'] / offline_value, 2) if\
                    offline_value != 0 else 0
                info_dict.update({'Competitive Ratio': competitive_ratio})



    return info_dict, output_dict