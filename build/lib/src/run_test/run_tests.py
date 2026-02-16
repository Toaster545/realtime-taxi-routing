import itertools
import os
import logging
from typing import Any, Dict, List
import pandas as pd
from src.utilities.enums import (Algorithm,Objectives,SolutionMode,DestroyMethod,ConsensusParams)
from src.simulation.run_simulation import run_taxi_simulation
from src.utilities.config import SimulationConfig
from src.utilities.tools import print_dict_as_table, determine_cust_node_hour, match_enum, print_result_as_table


BASE_FOLDER = "data/Instances"
GRAPH_FILE_PATH = os.path.join(BASE_FOLDER, "network.json")
RESULTS_FOLDER = os.path.join(BASE_FOLDER, "Results")
os.makedirs(RESULTS_FOLDER, exist_ok=True)

# Constants for solution mode defaults
KNOWN_PORTION_OFFLINE = 100
KNOWN_PORTION_ONLINE = 0
ADVANCE_NOTICE_DEFAULT = 30  # minutes
ADVANCE_NOTICE_NONE = 0
DEFAULT_NB_SCENARIO = 10

# Scenario group mappings
SCENARIO_GROUPS = {
    "TP4": ["TP4_CONSENSUS", "TP4_GREEDY"],
    "TP2": ["TP2_1", "TP2_2"],
}

def run_single_test(config_data: Dict[str, Any]):
    """Runs a single test based on configuration."""
    test_folder = config_data["instances"]
    config = create_simulation_config(config_data)

    logging.info(f"Running single test for instance '{test_folder}'.")

    test_path = os.path.join(BASE_FOLDER, test_folder)
    info_dict, output_dict = run_taxi_simulation(
        test_folder=test_path,
        graph_file_path=GRAPH_FILE_PATH,
        config=config
    )

    combined_result = {**info_dict, **output_dict}
    print_result_as_table(combined_result)


def run_scenarios(part: str, SCENARIOS: Dict[str, Dict[str, Any]]):
    """
    Runs scenarios based on the provided part.
    If part is a group (e.g., TP2), it runs all associated sub-scenarios.
    """
    if part in SCENARIO_GROUPS:
        # Handle grouped scenarios (e.g., TP4, TP2)
        group_scenarios = SCENARIO_GROUPS[part]
        all_combinations = []
        for group_scenario in group_scenarios:
            scenario = SCENARIOS.get(group_scenario, {})
            if scenario:
                all_combinations.extend(generate_combinations(scenario))
    elif part in SCENARIOS:
        # Single scenario
        scenario = SCENARIOS[part]
        all_combinations = generate_combinations(scenario)
    else:
        logging.error(f"Scenario part '{part}' is not defined.")
        available = list(SCENARIOS.keys()) + list(SCENARIO_GROUPS.keys())
        print(f"Invalid scenario part. Please choose from: {', '.join(available)}")
        return

    logging.info(f"Running scenarios for {part}")
    logging.info(f"Total combinations to run for {part}: {len(all_combinations)}")

    results = []
    for idx, comb in enumerate(all_combinations, 1):
        logging.info(f"Running combination {idx}/{len(all_combinations)}")
        instance = comb["instances"]
        test_path = os.path.join(BASE_FOLDER, instance)

        if not os.path.isdir(test_path):
            logging.warning(f"Instance folder '{test_path}' does not exist. Skipping.")
            continue

        config = create_simulation_config(comb)
        try:
            info_dict, output_dict = run_taxi_simulation(
                test_folder=test_path,
                graph_file_path=GRAPH_FILE_PATH,
                config=config
            )

            combined_result = {**info_dict, **output_dict}
            results.append(combined_result)
            print_result_as_table(combined_result)


        except Exception as e:
            logging.error(f"Error running simulation for {part} - Instance: {instance} - Error: {e}")
            continue

    # Save results to CSV
    df = pd.DataFrame(results)
    csv_file_path = os.path.join(RESULTS_FOLDER, f"{part}_simulation_results.csv")
    df.to_csv(csv_file_path, index=False)
    logging.info(f"Results for '{part}' saved to {csv_file_path}.")

    # Print results
    # Print results
    cols_to_print = [
        "Test", "# Trips", "# Vehicles", "Solution Mode",
        "Time window (min)", "weight", "Algorithm", "Objective type",
        "Objective value", "% of Service", "runtime (s)"
    ]
    with pd.option_context('display.colheader_justify', 'center'):
        # to_markdown will print headers on top, values below
        print(df[cols_to_print].to_markdown(tablefmt="pipe", index=False))

def generate_combinations(params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generates all parameter combinations for scenarios."""
    keys = list(params.keys())
    values = list(params.values())

    if "algorithm_params" in params and params["algorithm_params"]:
        algorithm_param_keys = list(params["algorithm_params"].keys())
        algorithm_param_values = list(params["algorithm_params"].values())

        algo_param_combinations = list(itertools.product(*algorithm_param_values))
        keys_no_algo = [k for k in keys if k != "algorithm_params"]
        values_no_algo = [params[k] for k in keys_no_algo]
        base_combinations = list(itertools.product(*values_no_algo))

        all_combinations = []
        for base_comb in base_combinations:
            base_dict = dict(zip(keys_no_algo, base_comb))
            for algo_comb in algo_param_combinations:
                algo_dict = dict(zip(algorithm_param_keys, algo_comb))
                all_combinations.append({**base_dict, **algo_dict})
    else:
        # Simple case: generate all combinations without nested algorithm_params
        all_combinations = [
            dict(zip(keys, combination))
            for combination in itertools.product(*values)
        ]
    return all_combinations


def create_simulation_config(comb: Dict[str, Any]) -> SimulationConfig:
    """Creates a SimulationConfig object from a parameter combination."""
    # Map string inputs to enums
    try:
        objective_enum = match_enum(comb["objectives"], Objectives)
        algorithm_enum = match_enum(comb["algorithms"], Algorithm)
        solution_mode_enum = match_enum(comb["solution_mode"], SolutionMode)
        if solution_mode_enum == SolutionMode.OFFLINE:
            known_portion = KNOWN_PORTION_OFFLINE
            advance_notice = ADVANCE_NOTICE_NONE
        elif solution_mode_enum == SolutionMode.FULLY_ONLINE:
            known_portion = KNOWN_PORTION_ONLINE
            advance_notice = ADVANCE_NOTICE_NONE
        elif solution_mode_enum == SolutionMode.PARTIAL_ONLINE:
            known_portion = comb["known_portion"]
            advance_notice = ADVANCE_NOTICE_NONE
        elif solution_mode_enum == SolutionMode.ADVANCE_NOTICE:
            known_portion = KNOWN_PORTION_ONLINE
            advance_notice = ADVANCE_NOTICE_DEFAULT
        else:
            known_portion = comb["known_portion"]
            advance_notice = ADVANCE_NOTICE_DEFAULT
    except ValueError as e:
        logging.error(f"Error creating SimulationConfig object - {e}")
        raise

    config = SimulationConfig(
        objective=objective_enum,
        algorithm=algorithm_enum,
        known_portion=known_portion,
        advance_notice=advance_notice,
        time_window=comb["time_windows"],
        solution_mode=solution_mode_enum,
    )

    if algorithm_enum == Algorithm.CONSENSUS:
        consensus_param_enum = match_enum(comb["consensus_params"], ConsensusParams)
        config.algorithm_params["nb_scenario"] = comb.get("nb_scenario", DEFAULT_NB_SCENARIO)
        config.algorithm_params["consensus_param"] = consensus_param_enum
        config.algorithm_params["cust_node_hour"] = determine_cust_node_hour(comb["instances"])

    if algorithm_enum == Algorithm.RE_OPTIMIZE:
        dest_method_enum = match_enum(comb["destroy_method"], DestroyMethod)
        config.algorithm_params["destroy_method"] = dest_method_enum

    # Weight for multi-objective (profit vs wait ime); used when objective is MULTI_OBJECTIVE
    config.algorithm_params["weight"] = comb.get("weight", 1)

    return config

