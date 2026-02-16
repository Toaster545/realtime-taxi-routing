import difflib
import networkx as nx
import matplotlib.pyplot as plt
from src.utilities.enums import SolutionMode


def get_solution_mode(known_portion, advance_notice):
    """
    Determines the operational scenario (solution mode) based on
    known_portion and advance_notice.

    Parameters:
    -----------------
    known_portion : int
        Percentage of requests known in advance (0 to 100).
    advance_notice : int
        Advance notice in minutes for request release.

    Returns:
    -----------------
    SolutionMode
        The corresponding solution mode.
    """
    if known_portion == 100:
        return SolutionMode.OFFLINE
    elif known_portion == 0 and advance_notice == 0:
        return SolutionMode.FULLY_ONLINE
    elif known_portion == 0 and 1 <= advance_notice <= 30:
        return SolutionMode.ADVANCE_NOTICE
    elif 100 > known_portion > 0 == advance_notice:
        return SolutionMode.PARTIAL_ONLINE
    else:
        return SolutionMode.CUSTOM_SCENARIO


def determine_cust_node_hour(instance_name: str) -> float:
    """
    Determines the cust_node_hour parameter based on the instance name.

    Parameters:
    -----------------
        instance_name (str): The name of the instance (e.g., 'Low_1', 'Med_2', 'High_3').

    Returns:
        float: The cust_node_hour value.
    """
    if instance_name.startswith("1-Low"):
        return 0.4
    elif instance_name.startswith("2-Med"):
        return 0.6
    elif instance_name.startswith("3-High"):
        return 0.8
    else:
        raise ValueError(f"Unknown instance prefix in '{instance_name}'")

def match_enum(arg, enum):
    enum_values = {e.value.lower(): e for e in enum}
    match = difflib.get_close_matches(arg.lower(), enum_values.keys(), n=1, cutoff=.2)
    if match:
        return enum_values[match[0]]

    raise ValueError("Not found in enum: " + arg)


def get_distances(network):
    """
    Function: calculate the shortest distance between each pair of stop nodes in the network graph
        network : routing network graph
    """
    distances = {}
    for node1, data in network.nodes(data=True):
        if node1 not in distances:
            distances[node1] = {}
        for node2 in network.nodes():
            distances[node1][node2] = round(data['shortest_paths'][node2]['total_distance'],0)

    return distances


def get_durations(network):
    """ Function: calculate the shortest travel time between each pair of stop nodes in the network graph
        network : routing network graph
    """
    durations = {}
    for node1, data in network.nodes(data=True):
        if node1 not in durations:
            durations[node1] = {}
        for node2 in network.nodes():
            durations[node1][node2] = round(data['shortest_paths'][node2]['total_duration'],0)

    return durations


def get_costs(network):
    """ Function: calculate the cost of driving between each pair of stop nodes in the network graph
        here the cost is $5 per hour of driving
        network : routing network graph
    """
    costs = {}
    for node1, data in network.nodes(data=True):
        if node1 not in costs:
            costs[node1] = {}
        for node2 in network.nodes():
            costs[node1][node2] = round(round(data['shortest_paths'][node2]['total_duration'],0) / 3600 * 5,2)
    return costs


def print_dict_as_table(input_dict):
    """Function: print a dictionary in a tabular format
    """
    # Find the maximum length of the keys for formatting
    max_key_length = max(len(str(key)) for key in input_dict.keys())
    max_value_length = max(len(str(value)) for value in input_dict.values())

    header_key = "Attribute"
    header_value = "Value"
    max_key_length = max(max_key_length, len(header_key))
    max_value_length = max(max_value_length, len(header_value))

    # Print table headers
    print(f"{header_key}{' ' * (max_key_length - len(header_key) + 2)} | {header_value}")
    print("-" * (max_key_length + 2) + "+" + "-" * (max_value_length + 2))

    # Print each item in the dictionary
    for key, value in input_dict.items():
        # Adjust spacing based on key and value length
        key_spacing = " " * (max_key_length - len(str(key)) + 2)
        print(f"{key}{key_spacing} | {value}")

def print_result_as_table(results: dict):
    """
    Print a selected subset of a results dictionary in a neat 2-column table.
    """
    rows = [
        ("Test", results.get("Test", "")),
        ("# Trips", results.get("# Trips", results.get("Trips", ""))),
        ("# Vehicles", results.get("# Vehicles", results.get("Vehicles", ""))),
        ("Solution Mode", results.get("Solution Mode", "")),
        ("Time window (min)", results.get("Time window (min)", "")),
        ("weight", results.get("weight", "")),
        ("Algorithm", results.get("Algorithm", "")),
        ("Objective type", results.get("Objective type", "")),
        ("Objective value", results.get("Objective value", "")),
        ("% of Service", results.get("% of Service", "")),
        ("runtime (s)", results.get("runtime (s)", "")),
    ]

    # Convert values to strings (safe for None, numbers, etc.)
    rows = [(k, "" if v is None else str(v)) for k, v in rows]

    # Column widths
    left_w = max(len(k) for k, _ in rows)
    right_w = max(len(v) for _, v in rows)

    # Print table
    print(f"{'Attribute'.ljust(left_w)} | {'Value'.ljust(right_w)}")
    print(f"{'-' * left_w}-+-{'-' * right_w}")
    for k, v in rows:
        print(f"{k.ljust(left_w)} | {v}")


def draw_network(network, save_path):
    """Function : Draw the network graph.
    """
    plt.figure(figsize=(10, 10))

    # Extract positions from node attributes
    pos = nx.get_node_attributes(network, 'pos')
    road_types = nx.get_edge_attributes(network, 'roadType')
    color_map = {1: 'red', 2: 'blue', 3: 'gray'}
    edge_colors = [color_map.get(road_types[edge], 'black') for edge in network.edges()]

    nx.draw_networkx(
        network,
        pos=pos,
        with_labels=True,
        node_size=80,
        width=1,
        font_size=6,
        node_color='yellowgreen',
        edge_color=edge_colors,
        arrows=True
    )

    # Add edge labels for edges with length > 1000
    labels = {
        (u, v): f"{attrs['length']:.0f}"
        for (u, v, attrs) in network.edges(data=True)
        if attrs['length'] > 1000
    }
    nx.draw_networkx_edge_labels(network, pos=pos, edge_labels=labels, font_size=7)


    plt.tight_layout()

    # Save the figure
    plt.savefig(save_path + '/Network.png', dpi=1000)
    plt.show(block=False)  # Show plot without blocking the script
    plt.pause(2)  # Pause for 2 seconds
    plt.close()


def create_solution_description(row):
    if row['Solution Mode'] == 'partial_online':
        if row['Known portion (%)'] == 0:
            return "Fully Online"
        else:
            return f"Partial Online ({row['Known portion (%)']}%)"
#    elif row['Solution Mode'] == 'advance_notice':
#        return f"Advance Notice ({row['Advance Notice (min)']} min)"
    else:
        return row['Solution Mode']

def merge_algorithms_param(row):
    if row['Algorithm'] == 'Consensus':
 #       return f"{row['Consensus type']}"
        return f"Consensus ({row['Consensus type']})"
    elif row['Algorithm'] == 'Re_Optimize':
        return f"LNS ({row['Destroy Method']})"
    else:
        return row['Algorithm']


def add_data_labels(ax, metric, y_min, y_max, threshold=0.15):
    """
    Adds data labels to the bars in a bar plot with intelligent positioning.

    Parameters:
        ax (matplotlib.axes.Axes): The Axes object to add labels to.
        metric (str): The name of the metric being plotted, used for formatting.
        y_min (float): The minimum y-axis limit.
        y_max (float): The maximum y-axis limit.
        threshold (float, optional): The ratio of the y-axis range to determine label placement.
                                     Defaults to 0.15 (15%).

    Returns:
        None
    """
    for container in ax.containers:
        # Iterate over each bar in the container
        for bar in container:
            height = bar.get_height()

            # Define the threshold based on the y-axis range
            if y_max - y_min == 0:
                # Prevent division by zero
                threshold_ratio = 0
            else:
                threshold_ratio = (height - y_min) / (y_max - y_min)

            # Determine label position based on threshold
            if threshold_ratio > 2 * threshold:
                # Place label inside the bar
                label_y = height - (0.05 * (y_max - y_min))  # Slightly below the top
                va = 'top'
                color = 'white'
            else:
                # Place label outside the bar
                label_y = height + (0.02 * (y_max - y_min))  # Slightly above the bar
                va = 'bottom'
                color = 'black'

            # Format the label based on the metric
            if y_max > 100:
                label = f"{height:.0f}"
            else:
                label = f"{height:.2f}"

            # Add the label to the bar
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                label_y,
                label,
                ha='center',
                va=va,
                fontsize=7,
                color='darkslategray',
                rotation=90,
                fontweight='bold',
            )


def find_shortest_paths(network) -> None:
    """
    Function: Computes the shortest paths between all pairs of nodes in the network
        and stores the results in the nodes' 'shortest_paths' attribute

        network : routing network graph
    """

    if not network:
        raise ValueError("Network is not initialized.")

    # Ensure the network is connected
    if not nx.is_weakly_connected(network):
        raise ValueError("The network is not connected.")

    # Initialize the 'shortest_paths' attribute for nodes
    for node in network.nodes:
        network.nodes[node]['shortest_paths'] = {}

    # Compute the shortest paths and lengths using Dijkstra's algorithm
    for source in network.nodes:
        source_node_data = network.nodes[source]
        for target in network.nodes:
            if source != target:
                # Find the shortest path based on duration
                shortest_path = nx.shortest_path(network, source=source, target=target, weight='duration')

                # Access the edges along the path
                path_edges = [(shortest_path[i], shortest_path[i + 1]) for i in range(len(shortest_path) - 1)]

                # Calculate the sum of 'duration', 'length', and 'cost'
                total_duration = sum(network[u][v]['duration'] for u, v in path_edges)
                total_distance = sum(network[u][v]['length'] for u, v in path_edges)
                total_cost = sum(network[u][v]['cost'] for u, v in path_edges)
            else:
                shortest_path = {}
                path_edges = []

                total_duration = 0
                total_distance = 0
                total_cost = 0

            source_node_data['shortest_paths'][target] = {
                'path_edges': path_edges,
                'path_nodes': shortest_path,
                'total_duration': total_duration,
                'total_distance': total_distance,
                'total_cost': total_cost
            }