import json
import math
import os
import pickle
from typing import Any, Dict
import networkx as nx
import pandas as pd
from multimodalsim.simulator.vehicle import Vehicle
from multimodalsim.simulator.stop import LabelLocation, Stop
import random

from src.utilities.create_scenario import create_random_requests
from src.utilities.tools import find_shortest_paths, draw_network, get_durations, determine_cust_node_hour

BASE_FOLDER = "data/Instances"
GRAPH_FILE_PATH = os.path.join(BASE_FOLDER, "network.json")

# Define road types and their maximum speeds (km/h)
ROAD_TYPES = [1, 2, 3]
MAX_SPEEDS_KMH = {
    1: 130.0,  # Highways around downtown
    2: 110.0,  # Connecting roads between main city and suburbs
    3: 50.0    # Internal roads within main city and suburbs
}

# Constants for speed calculations
SPEED_REDUCTION_FACTOR = 0.6  # 60% of max speed (accounts for traffic)
KMH_TO_MS_CONVERSION = 3.6  # Convert km/h to m/s
HOURLY_COST_RATE = 5.0  # $5 per hour
SECONDS_PER_HOUR = 3600.0

def get_speed_m_s(road_type):
    """
    Get effective speed in m/s for a given road type, considering speed reduction factor.
    """
    max_speed_kmh = MAX_SPEEDS_KMH.get(road_type, 0)
    if max_speed_kmh == 0:
        return 0  # Non-traversable road
    effective_speed_kmh = max_speed_kmh * SPEED_REDUCTION_FACTOR
    effective_speed_m_s = effective_speed_kmh / KMH_TO_MS_CONVERSION
    return effective_speed_m_s

def add_random_vehicles(
        network,
        start_ID,
        nb_vehicles,
        start_time=0,
        vehicles_end_time=100000,
        boarding_time=10,
        capacity=4):
    """ Function: Adds random vehicles (taxis) to the system with uniformly distributed initial positions.
        Input:
        ------------
        network : Network object
            The road network, including nodes representing stop points.
        start_ID : int
            Starting ID for the vehicles.
        nb_vehicles : int
            The number of vehicles (taxis) to add with uniform initial positions and specified availability times.
        start_time : float, optional
            The time in seconds after which vehicles become available. Defaults to 0.0.
        vehicles_end_time : float, optional
            The time in seconds after which vehicles are no longer available. Defaults to 100000.0.
        boarding_time : float, optional
            The time in seconds required for boarding passengers. Defaults to 10.0.
        capacity : int, optional
            The passenger capacity of each vehicle. Defaults to 4.

        Output:
        ------------
            taxis: List of generated Vehicle objects.
    """
    vehicles = []

    for i in range(nb_vehicles):
        vehicle_id = str(start_ID + i)

        # Randomly select a stop ID ensuring it's within the network nodes
        stop_id = str(random.randint(0, len(network.nodes) - 1))
        start_stop_location = LabelLocation(stop_id)

        # Calculate arrival and departure times
        arrival_time = start_time
        departure_time = start_time + boarding_time

        start_stop = Stop(
            arrival_time=arrival_time,
            departure_time=departure_time,
            location=start_stop_location
        )

        # Create the Vehicle object
        vehicle = Vehicle(vehicle_id,
                          start_time=start_time,
                          start_stop=start_stop,
                          capacity=capacity,
                          release_time=start_time,
                          end_time=vehicles_end_time,
                          reusable=True)

        vehicles.append(vehicle)

    return vehicles

def save_trips_to_json(trips, save_file_path):
    """ Function: save list of requests in a json file
        Input:
        ------------
            trips: List of trip objects or dictionaries.
            save_file_path: String specifying the path to the output JSON file.
    """
    # Convert trip objects to dictionaries
    trips_data = []
    for trip in trips:
        trip_dict = {
            "id": trip.id,
            "orig": trip.origin.label,
            "dest": trip.destination.label,
            "tcall": trip.release_time,
            "tmin": trip.ready_time,
            "tmax": trip.latest_pickup,
            "fare": trip.fare
        }
        trips_data.append(trip_dict)

    # Save the list of dictionaries to a JSON file
    with open(save_file_path, 'w') as f:
        json.dump(trips_data, f, indent=4)

def save_vehicles_to_json(vehicles, save_file_path):
    """ Function: save list of vehicles in a json file
        Input:
        ------------
            vehicles: List of vehicle objects or dictionaries.
            save_file_path: String specifying the path to the output JSON file.
    """
    # Convert vehicle objects to dictionaries
    vehicle_data = []
    for vehicle in vehicles:
        vehicle_dict = {
            "id": vehicle.id,
            "initPos": vehicle.start_stop.location.label,
            "initTime": vehicle.start_time,
        }
        vehicle_data.append(vehicle_dict)

    # Save the list of dictionaries to a JSON file
    with open(save_file_path, 'w') as f:
        json.dump(vehicle_data, f, indent=4)

def save_network_graph(network, file_path: str) -> None:
    """Save the graph with all its data to a file."""
    with open(f'{file_path}/network.pkl', 'wb') as f:
        pickle.dump(network, f)


def add_bidirectional_road(G, u_id, v_id, road_type):
    """
        Adds a bidirectional road between two nodes with the specified road type.

        Parameters:
        - G: The NetworkX graph.
        - u_id: Integer ID of the first node.
        - v_id: Integer ID of the second node.
        - road_type: Integer representing the road type (1, 2, or 3).
    """
    # Convert to string
    u = str(u_id)
    v = str(v_id)
    # Compute length as Euclidean distance
    ux, uy = G.nodes[u]['pos']
    vx, vy = G.nodes[v]['pos']
    length = round(math.sqrt((vx - ux) ** 2 + (vy - uy) ** 2), 0)
    # Get effective speed in m/s
    speed = get_speed_m_s(road_type)
    duration = round(length / speed, 0)  # seconds
    cost = round((duration / SECONDS_PER_HOUR) * HOURLY_COST_RATE, 2)

    # Add edge from u to v with roadType attribute
    G.add_edge(u, v, cost=cost, duration=duration, length=length, roadType=road_type)
    G.nodes[u]['Node']['out_arcs'].append(v)
    G.nodes[v]['Node']['in_arcs'].append(u)

    # Add edge from v to u with roadType attribute
    G.add_edge(v, u, cost=cost, duration=duration, length=length, roadType=road_type)
    G.nodes[v]['Node']['out_arcs'].append(u)
    G.nodes[u]['Node']['in_arcs'].append(v)

def generate_urban_network(num_suburbs: int = 8, suburb_width: int = 4, city_width: int = 8, block_distance: float = 800.0) -> nx.DiGraph:
    """
    Generates an urban-like network composed of a main city and surrounding suburbs arranged in a circular pattern.
    The main city is a square grid of size city_width x city_width, and we add `num_suburbs` suburban areas,
    each a square grid of size suburb_width x suburb_width, placed around the city.

    Parameters
    ----------
    num_suburbs : int
        Number of suburb areas to generate around the city.
    suburb_width : int
        Width (and height) of each suburban grid (suburb is a square of size suburb_width x suburb_width).
    city_width : int, optional
        Width (and height) of the main city grid, by default 8.
    block_distance : float, optional
        Distance between adjacent nodes within a grid, by default 200.0 meters.

    Returns
    -------
    nx.DiGraph
        The generated transportation network graph with nodes and edges.
    """

    # Helper functions for indexing the grids
    def city_coord_to_id(i, j):
        # Convert city coordinates (0-based) to linear index
        return i * city_width + j

    def suburb_coord_to_id(i, j, c):
        # c in [0, num_suburbs-1] for each suburb
        base = city_width * city_width + c * (suburb_width * suburb_width)
        return base + i * suburb_width + j

    def rotate_point(x, y, angle):
        radians = math.radians(angle)
        cos_a, sin_a = math.cos(radians), math.sin(radians)
        return x * cos_a - y * sin_a, x * sin_a + y * cos_a

    def random_shift(max_shift: float = 20.0):
        """
        Generates a random (dx, dy) shift within a circle of radius max_shift.

        Parameters
        ----------
        max_shift : float
            Maximum shift in meters.

        Returns
        -------
        tuple
            A tuple (dx, dy) representing the shift.
        """
        angle = random.uniform(0, 2 * math.pi)
        radius = random.uniform(0, max_shift)
        dx = radius * math.cos(angle)
        dy = radius * math.sin(angle)
        return dx, dy

    # Create an empty directed graph
    G = nx.DiGraph()

    # Create main city nodes (center)
    city_nodes = city_width * city_width

    # Position city nodes centered at (0,0)
    # City layout: a grid of city_width x city_width
    city_offset = (city_width - 1) / 2.0
    # Store node data in the format used in this project
    for i in range(city_width):
        for j in range(city_width):
            node_id = city_coord_to_id(i, j)
            node_id_str = str(node_id)
            x = (j - city_offset) * block_distance
            y = (city_offset - i) * block_distance

            # Apply random shift
            dx, dy = random_shift(10.0)
            x += dx
            y += dy

            node_dict = {
                "id": node_id_str,
                "coordinates": [x, y],
                "in_arcs": [],
                "out_arcs": []
            }
            G.add_node(node_id_str, pos=(x, y), Node=node_dict)

    # Place suburbs around the city in a circular pattern
    # For simplicity, we place them evenly spaced by angle around the city center.
    # Each suburb is also a suburb_width x suburb_width grid.
    angle_step = (2 * math.pi / num_suburbs) if num_suburbs > 0 else 0
    # Distance from city center to suburb center
    # We place suburbs so they do not overlap. As a simple heuristic:
    # suburbs start at some radius that accounts for city size + some offset
    radius = round((city_width + suburb_width) * block_distance * random.uniform(0.7, 0.8), 0)

    for c in range(num_suburbs):
        angle = c * angle_step + random.uniform(-0.1, 0.1)
        # Center of this suburb:
        cx = radius * math.cos(angle)
        cy = radius * math.sin(angle)

        suburb_offset = (suburb_width - 1) / 2.0
        rotation_angle = random.randint(0, 45)
        for i in range(suburb_width):
            for j in range(suburb_width):
                node_id = suburb_coord_to_id(i, j, c)
                node_id_str = str(node_id)
                x = (j - (suburb_width - 1) / 2.0) * block_distance
                y = (i - (suburb_width - 1) / 2.0) * block_distance
                x, y = rotate_point(x, y, rotation_angle)
                x += cx
                y += cy

                # Apply random shift
                dx, dy = random_shift(10.0)
                x += dx
                y += dy

                node_dict = {
                    "id": node_id_str,
                    "coordinates": [x, y],
                    "in_arcs": [],
                    "out_arcs": []
                }
                G.add_node(node_id_str, pos=(x, y), Node=node_dict)

    # Function to add roads between two sets of nodes forming a grid
    def add_grid_edges(width, height, base_func, road_type):
        # Vertical edges
        for i in range(height - 1):
            for j in range(width):
                n1 = base_func(i, j)
                n2 = base_func(i + 1, j)
                add_bidirectional_road(G,n1, n2, road_type)

        # Horizontal edges
        for i in range(height):
            for j in range(width - 1):
                n1 = base_func(i, j)
                n2 = base_func(i, j + 1)
                add_bidirectional_road(G,n1, n2, road_type)

    # Add edges within the main city
    add_grid_edges(city_width, city_width, city_coord_to_id, road_type=3)

    # Add edges within each suburb (roadType=3)
    for c in range(num_suburbs):
        # Define a helper function to capture the current value of c
        def suburb_base_func(i, j, current_c=c):
            return suburb_coord_to_id(i, j, current_c)

        add_grid_edges(suburb_width, suburb_width, suburb_base_func, road_type=3)

    # Connect suburbs to the main city (roadType=2)
    for c in range(num_suburbs):
        suburb_edge_nodes = [suburb_coord_to_id(i, 0, c) for i in range(suburb_width)] + \
                            [suburb_coord_to_id(i, suburb_width - 1, c) for i in range(suburb_width)] + \
                            [suburb_coord_to_id(0, j, c) for j in range(suburb_width)] + \
                            [suburb_coord_to_id(suburb_width - 1, j, c) for j in range(suburb_width)]

        # Find the closest city node to connect
        min_distance = float('inf')
        nearest_city_node = None
        chosen_suburb_node = None

        for suburb_node in suburb_edge_nodes:
            suburb_node_str = str(suburb_node)
            for city_node in range(city_width * city_width):
                city_node_str = str(city_node)
                ux, uy = G.nodes[city_node_str]['pos']
                vx, vy = G.nodes[suburb_node_str]['pos']
                distance = math.sqrt((vx - ux) ** 2 + (vy - uy) ** 2)
                if distance < min_distance:
                    min_distance = distance
                    nearest_city_node = city_node
                    chosen_suburb_node = suburb_node

        if nearest_city_node is not None and chosen_suburb_node is not None:
            add_bidirectional_road(G, nearest_city_node, chosen_suburb_node, road_type=2)

    # Add highways around downtown (roadType=2)
    for c in range(num_suburbs):
        next_suburb = (c + 1) % num_suburbs

        current_suburb_edge_nodes = [suburb_coord_to_id(i, 0, c) for i in range(suburb_width)] + \
                                    [suburb_coord_to_id(i, suburb_width - 1, c) for i in range(suburb_width)] + \
                                    [suburb_coord_to_id(0, j, c) for j in range(suburb_width)] + \
                                    [suburb_coord_to_id(suburb_width - 1, j, c) for j in range(suburb_width)]

        next_suburb_nodes = [suburb_coord_to_id(i, 0, next_suburb) for i in range(suburb_width)] + \
                                    [suburb_coord_to_id(i, suburb_width - 1, next_suburb) for i in range(suburb_width)] + \
                                    [suburb_coord_to_id(0, j, next_suburb) for j in range(suburb_width)] + \
                                    [suburb_coord_to_id(suburb_width - 1, j, next_suburb) for j in range(suburb_width)]

        representative_node = min(current_suburb_edge_nodes, key=lambda n: sum(math.sqrt(
            (G.nodes[str(n)]['pos'][0] - G.nodes[str(next_node)]['pos'][0]) ** 2 + (
                        G.nodes[str(n)]['pos'][1] - G.nodes[str(next_node)]['pos'][1]) ** 2) for next_node in
                                                                               next_suburb_nodes))
        closest_next_node = min(next_suburb_nodes, key=lambda n: math.sqrt(
            (G.nodes[str(representative_node)]['pos'][0] - G.nodes[str(n)]['pos'][0]) ** 2 + (
                        G.nodes[str(representative_node)]['pos'][1] - G.nodes[str(n)]['pos'][1]) ** 2))

        add_bidirectional_road(G,representative_node, closest_next_node, road_type=2)


    # Compute the shortest paths
    find_shortest_paths(G)

    return G


def create_instances(config_data: Dict[str, Any]):

    # Generate the network
    network = generate_urban_network(
        config_data["num_suburbs"], config_data["suburb_width"],
        config_data["city_width"], config_data["block_distance"])

    save_network_graph(network, os.path.dirname(GRAPH_FILE_PATH))

    # Extract durations from computed shortest_paths for request generation
    durations = get_durations(network)

    draw_network(network, os.path.dirname(GRAPH_FILE_PATH))

    # Dynamically generate test names
    instances = [
        f"{group}_{i + 1}"
        for group in config_data["group_name"]
        for i in range(config_data["num_tests_per_group"])
    ]

    # Initialize table data
    table_data = []

    for test_name in instances:
        cust_node_hour = determine_cust_node_hour(test_name)
        # Create random requests
        requests = create_random_requests(
            network=network,
            cust_node_hour=cust_node_hour,
            start_ID=0,
            start_time= config_data["start_time"],
            durations=durations,
            time_window=3,
            sim_time=config_data["sim_time"],
            hour_fare=config_data["hour_fare"],
            advance_notice=config_data["advance_notice"],
            known_portion=config_data["known_portion"],
        )

        # Add random vehicles
        vehicles = add_random_vehicles(
            network=network,
            start_ID=0,
            nb_vehicles=config_data["nb_vehicles"],
            start_time=0,
            vehicles_end_time=100000,
            boarding_time=10,
            capacity=4
        )

        # Save generated data to JSON
        test_path = os.path.join(BASE_FOLDER, test_name)
        os.makedirs(test_path, exist_ok=True)
        customers_file_path = os.path.join(test_path, "customers.json")
        vehicles_file_path = os.path.join(test_path, "taxis.json")
        save_trips_to_json(requests, customers_file_path)
        save_vehicles_to_json(vehicles, vehicles_file_path)

        # Append to table data
        table_data.append({
            "Instance": test_name,
            "# Requests": len(requests),
            "# Vehicles": len(vehicles)
        })

    # Print results
    df = pd.DataFrame(table_data)
    with pd.option_context('display.colheader_justify', 'center'):
        print(df.to_markdown(tablefmt="pipe", headers="keys"))
