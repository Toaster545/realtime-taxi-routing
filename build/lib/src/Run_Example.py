import os
import logging
import argparse
from src.utilities.tools import (print_dict_as_table, match_enum, determine_cust_node_hour, print_result_as_table)
from src.utilities.enums import (Algorithm, Objectives, DestroyMethod, ConsensusParams, SolutionMode)
from src.simulation.run_simulation import run_taxi_simulation
from src.utilities.config import SimulationConfig


def run_example(test_folder: str, config: SimulationConfig) -> None:
    """
    Runs a taxi dispatch simulation with the specified parameters.

    Parameters:
    ----------------------
    test_folder: str
        folder of the instance to test

    config: SimulationConfig
        Configuration object containing all simulation parameters.
    """
    logging.getLogger().setLevel(logging.WARN)  # INFO

    # Define base paths
    base_folder = "data/Instances"
    graph_file_path = "data/Instances/network.json"
    test_path = os.path.join(base_folder, test_folder)


    # Run the simulation
    info_dict, output_dict = run_taxi_simulation(
        test_path,
        graph_file_path,
        config=config,
    )

    # Combine and print the results
    result = {**info_dict, **output_dict}
    print_result_as_table(result)


def parse_arguments() -> tuple[str, SimulationConfig]:
    """
    Parses command-line arguments and returns test_folder and a SimulationConfig object.

    Returns:
        SimulationConfig: Configured simulation parameters.
        test_folder: The directory path where the test files are located.
    """
    parser = argparse.ArgumentParser(
        description='Run a taxi simulation',
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument("-i", "--instance", type=str, default="Med_1",
                        help="Folder of the instance to test. Default: Med_1")

    parser.add_argument("-o", "--objective", type=str, default="total_customers",
                        help=("The optimization objective to achieve:\n"
                              "- total_profit: Maximizes the total profit of served requests.\n"
                              "- waiting_time: Minimizes the total wait time of served requests.\n"
                              "- total_customers: Maximizes the total number of served customers.\n"
                              "- multi_objective: Weighted combination of profit and wait time (use -wp for weight).\n"
                              "Default: total_customers"))

    parser.add_argument("-a", "--algorithm", type=str, default="mip_solver",
                        help=("Algorithm used to optimize the dispatch plan:\n"
                              "- mip_solver: Uses the Gurobi MIP solver to solve the problem.\n"
                              "- greedy: Greedy approach to assign requests to vehicles.\n"
                              "- random: Random approach to assign requests to vehicles.\n"
                              "- ranking: Ranking approach to assign requests to vehicles.\n"
                              "- consensus: Consensus approach to assign requests to vehicles.\n"
                              "- re_optimize: Re-optimize the solution based on destroy and repair.\n"
                              "Default: mip_solver"))
    parser.add_argument("-m", "--sol-mode", type=str, default="offline",
                        help="The mode of solution:\n"
                             "- offline : all the requests revealed at the start (release time = 0 for all requests).\n"
                             "- fully_online : release time is equal to the ready time for all requests.\n"
                             "- advance_notice : requests are known 30 minutes before the ready time.\n"
                             "- partial_online : a portion of requests are known in adavnce.\n"
                             "- custom_scenario : a mix of advance_notice and partial_online.\n"
                             "Default: offline")

    parser.add_argument("-kp", "--known-portion", type=float, default=100,
                        help="Portion of requests that are known in advance (0-100%). Default: 100")

    parser.add_argument("-an", "--advance-notice", type=int, default=0,
                        help="Fixed amount of time (minutes) the requests are released before their ready time. Default: 0")

    parser.add_argument("-tw", "--time-window", type=int, default=3,
                        help="Size of the time window in minutes to serve a request. Default: 3")

    parser.add_argument("-ns", "--nb-scenario", type=int, default=5,
                        help="Total number of scenarios to be solved for consensus. Default: 20")

    parser.add_argument("-cr", "--cust-rate", type=float, default=0.35,
                        help=("The average rate of customers per node per hour:\n"
                              "- 0.2 for small-size tests.\n"
                              "- 0.3 for medium-size tests.\n"
                              "- 0.7 for large-size tests.\n"
                              "Default: 0.35"))

    parser.add_argument("-cp", "--consensus-params", type=str, default="quantitative",
                        help=("Type of consensus algorithm:\n"
                              "- qualitative: Increment a counter for the best request in each scenario.\n"
                              "- quantitative: Credit the best request with the optimal solution value.\n"
                              "Default: quantitative"))

    parser.add_argument("-dm", "--dest-method", type=str, default="default",
                        help=("Method used for destruction in re-optimizing:\n"
                              "- default: Default destruction method (Complete re-optimization)\n"
                              "- fix_variables: fix some of the variables in the model\n"
                              "- fix_arrivals: Fix a time window around the arrival time\n"
                              "- bonus: arbitrary destroy method as bonus\n"
                              "Default: default"))

    parser.add_argument("-wp", "--weight", type=float, default=1,
                        help=("Weight w in [0, 1] for profit in multi-objective. Default: 0.5"))

    args = parser.parse_args()

    # Map string inputs to enums
    try:
        objective_enum = match_enum(args.objective, Objectives)
        algorithm_enum = match_enum(args.algorithm, Algorithm)
        dest_method_enum = match_enum(args.dest_method, DestroyMethod)
        consensus_param_enum = match_enum(args.consensus_params, ConsensusParams)
        solution_mode_enum = match_enum(args.sol_mode, SolutionMode)
        if solution_mode_enum == SolutionMode.OFFLINE:
            known_portion = 100
            advance_notice = 0
        elif solution_mode_enum == SolutionMode.FULLY_ONLINE:
            known_portion = 0
            advance_notice = 0
        elif solution_mode_enum == SolutionMode.PARTIAL_ONLINE:
            known_portion = args.known_portion
            advance_notice = 0
        elif solution_mode_enum == SolutionMode.ADVANCE_NOTICE:
            known_portion = 0
            advance_notice = 30
        else:
            known_portion = args.known_portion
            advance_notice = 30
    except ValueError as e:
        parser.error(str(e))

    # Create a SimulationConfig object
    config = SimulationConfig(
        objective=objective_enum,
        algorithm=algorithm_enum,
        known_portion=known_portion,
        advance_notice=advance_notice,
        time_window=args.time_window,
        solution_mode=solution_mode_enum,
    )

    # Populate algorithm_params based on the chosen algorithm
    if algorithm_enum == Algorithm.CONSENSUS:
        config.algorithm_params["nb_scenario"] = args.nb_scenario
        config.algorithm_params["cust_node_hour"] = determine_cust_node_hour(args.instance)
        config.algorithm_params["consensus_param"] = consensus_param_enum

    if algorithm_enum == Algorithm.RE_OPTIMIZE:
        config.algorithm_params["destroy_method"] = dest_method_enum

    config.algorithm_params["weight"] = args.weight

    return args.instance, config


def main():
    """
    Main function to run the taxi simulation based on command-line arguments.
    """
    test_folder, config = parse_arguments()
    run_example(test_folder, config)

if __name__ == '__main__':
    main()