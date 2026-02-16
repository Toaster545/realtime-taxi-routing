import json
import pickle
import random
import networkx as nx
from typing import Optional

from multimodalsim.reader.data_reader import DataReader
from multimodalsim.simulator.vehicle import Vehicle
from multimodalsim.simulator.stop import LabelLocation, Stop
from src.utilities.config import SimulationConfig

from src.simulation.ride_request import RideRequest
from src.utilities.enums import SolutionMode
from src.utilities.tools import find_shortest_paths


class TaxiDataReader(DataReader):
    """
    TaxiDataReader is responsible for reading and processing input data from files,
    including trip requests, vehicle information, and the transportation network.

    Additional Attributes:
    ------------
    requests_file_path : str
        File path to the JSON file containing trip requests.
    vehicles_file_path : str
        File path to the JSON file containing vehicle data.
    graph_from_json_file_path : str
        File path to the JSON file containing the transportation network graph.
    sim_end_time : int
        Simulation end time.
    vehicles_end_time : int
        End time for vehicles' operations.
    """

    def __init__(self, requests_file_path: str, vehicles_file_path: str,
                 graph_from_json_file_path: Optional[str] = None,
                 sim_end_time: Optional[int] = None,
                 vehicles_end_time: Optional[int] = None) -> None:

        super().__init__()
        self.__network = None
        self.__requests_file_path = requests_file_path
        self.__vehicles_file_path = vehicles_file_path
        self.__graph_from_json_file_path = graph_from_json_file_path

        # The time difference between the arrival and the departure time.
        self.__boarding_time = 0
        self.__sim_end_time = sim_end_time
        self.__vehicles_end_time = vehicles_end_time

    def get_json_trips(self, config: SimulationConfig):
        """ Function: read trip from a file
            Input:
            ------------
            solution_mode : The mode of solution (offline, fully online, etc.).
            time_window : Time window for requests pickup
            known_portion: percentage of requests that are known in advance

            Output:
            ------------
            trips : A list of RideRequest objects.
        """
        trips = []
        with open(self.__requests_file_path, 'r') as rFile:
            js_data = json.load(rFile)
            nb_passengers = 1  # Each request corresponds to 1 passenger.
            # random.seed(42)
            # Shuffle the indices and select known_portion of them
            indices = list(range(len(js_data)))
            random.shuffle(indices)
            known_trip_indices = indices[:int(len(js_data) * config.known_portion/100)]

            for idx, entry in enumerate(js_data):
                # Process trip data
                orig_id = str(int(entry['orig']))
                dest_id = str(int(entry['dest']))
                fare_value = float(entry['fare'])

                # Optionally get longitude and latitude if available
                lon_orig = lat_orig = None
                lon_dest = lat_dest = None

                orig_location = LabelLocation(orig_id, lon=lon_orig, lat=lat_orig)
                dest_location = LabelLocation(dest_id, lon=lon_dest, lat=lat_dest)

                travel_time = None
                if self.__network is not None:
                    path_info = self.__network.nodes[orig_id]['shortest_paths'][dest_id]
                    travel_time = path_info['total_duration']

                ready_time = round(float(entry['tmin']), 3)
                # Determine release_time
                if config.solution_mode == SolutionMode.OFFLINE:
                    release_time = 0
                elif config.solution_mode == SolutionMode.FULLY_ONLINE:
                    release_time = ready_time
                elif config.solution_mode == SolutionMode.PARTIAL_ONLINE:
                    if idx in known_trip_indices:
                        release_time = 0
                    else:
                        release_time = ready_time
                elif config.solution_mode == SolutionMode.ADVANCE_NOTICE:
                    release_time = max(0.0, ready_time - config.advance_notice * 60)


                # Create and append RideRequest object
                trip = RideRequest(
                    id=entry['id'],
                    origin=orig_location,
                    destination=dest_location,
                    nb_passengers=nb_passengers,
                    release_time=release_time,
                    ready_time=ready_time,
                    due_time=100000.0,  # Adjust as needed
                    latest_pickup=round(ready_time + config.time_window * 60, 3),
                    fare=fare_value,
                    shortest_travel_time=travel_time
                )
                trips.append(trip)
        random.seed(None)
        return trips

    def get_json_vehicles(self):
        """ Function: read vehicles from a file
                Output:
                ------------
                vehicles: a list of Vehicle objects
                routes_by_vehicle_id : a dictionary of routes by vehicle ID
        """
        vehicles = []
        routes_by_vehicle_id = {}  # Remains empty

        with open(self.__vehicles_file_path, 'r') as rFile:
            js_data = json.load(rFile)
            for entry in js_data:
                # Process vehicle data
                vehicle_id = entry['id']
                start_time = float(entry['initTime'])
                stop_departure_time = start_time + self.__boarding_time
                capacity = 4
                stop_id = str(int(entry['initPos']))

                lon, lat, mode = None, None, None
                start_stop_location = LabelLocation(stop_id, lon=lon, lat=lat)

                start_stop = Stop(
                    arrival_time=start_time,
                    departure_time=stop_departure_time,
                    location=start_stop_location
                )

                # reusable=True since the vehicles are shuttles.
                # Create and append Vehicle object
                vehicle = Vehicle(
                    veh_id = vehicle_id,
                    start_time= start_time,
                    start_stop=start_stop,
                    capacity=capacity,
                    release_time= start_time,
                    end_time=self.__vehicles_end_time,
                    mode=mode, reusable=True)

                vehicles.append(vehicle)

        return vehicles, routes_by_vehicle_id

    def get_json_graph(self) -> nx.DiGraph:
        """ Function: Reads the transportation network from a JSON file and processes it into a NetworkX graph.
                Output:
                ------------
                network: routing network graph
        """
        if not self.__graph_from_json_file_path:
            raise ValueError("Graph file path is not provided.")

        with open(self.__graph_from_json_file_path, 'r') as rFile:
            data = json.load(rFile)
            nodes = data.get("network", {}).get("nodes", [])
            roads = data.get("network", {}).get("roads", {})
            costs = data.get("times", {})

            self.__network = nx.DiGraph()
            pos = {}

            # Process nodes
            for i, node_data in enumerate(nodes):
                node_id = str(i)
                x = float(node_data.get("x", 0.0))
                y = float(node_data.get("y", 0.0))

                node_dict = {
                    "id": node_id,
                    "coordinates": [x, y],
                    "in_arcs": [],
                    "out_arcs": []
                }
                pos[node_id] = (x, y)
                self.__network.add_node(node_id, pos=(x, y), Node=node_dict)

            # Process edges
            precision = 0
            for road_key, road_data in roads.items():
                orig, dest = eval(road_key)
                orig_id = str(orig)
                dest_id = str(dest)
                length = round(float(road_data.get('distance', 0.0)), precision)
                duration = float(costs[orig][dest])
                cost = round(duration / 3600 * 5, precision)

                self.__network.add_edge(
                    orig_id, dest_id,
                    cost=cost,
                    duration=round(duration, precision),
                    length=length
                )
            find_shortest_paths(self.__network)

        return self.__network

    def load_graph(self, file_path: str) -> nx.DiGraph:
        """Load the graph with all its data from a file."""
        with open(file_path, 'rb') as f:
            self.__network = pickle.load(f)
        f.close()
        return self.__network


