import numpy as np
from random import randint
from scipy.stats import expon
from src.simulation.ride_request import RideRequest
from multimodalsim.simulator.stop import LabelLocation


def create_random_requests(
        network,
        cust_node_hour,
        start_ID,
        start_time,
        durations,
        time_window,
        sim_time=30 * 60,
        hour_fare=60.0,
        advance_notice=30,
        known_portion=100,
        nb_requests=None):
    """ Function: Generate random customer ride requests based on a Poisson process.
        Input:
        ------------
            network : Network object
                The road network, including nodes representing stop points.
            cust_node_hour : float
                Average number of customers per node per hour (mean of the Poisson process).
            start_ID : int
                Starting ID for the generated trip requests.
            start_time : float
                The time in seconds after which requests are received.
            durations : dict
                A nested dictionary containing travel times between nodes, with outer keys as origin node IDs
                and inner keys as destination node IDs.
            sim_time : float, optional
                The total time in seconds for receiving requests. Defaults to 3600 (1 hour).
            hour_fare : float, optional
                Fare paid for serving request per hour of travel. Defaults to 80$.
            time_window : int, optional
                The time window in minutes within which customers are willing to be picked up after their
                ready time. Defaults to 5 minutes.
            advance_notice : int, optional
                The time in min before the ready time that customers call to make a request.
                Defaults to 30 minutes.
            known_portion : int, optional
                The percentage of requests that are known in advance (between 0 and 100). Defaults to 0.
            nb_requests : int, optional
                Maximum number of requests to generate. If None, generates requests up to sim_time.

        Output:
        ------------
            trips : list
                List of generated RideRequest objects.
    """
    request_id = start_ID
    trips = []

    # Calculate the mean inter-arrival time based on the customer rate
    mean_interarrival_time = 3600.0 / (cust_node_hour * len(network.nodes))
    interarrival_distribution = expon(scale=mean_interarrival_time)

    # Initialize the time of the first request
    t = start_time + round(interarrival_distribution.rvs(),1)

    while t <= start_time + sim_time:
        # Ensure dest_id != orig_id
        orig_id = np.random.randint(0, len(network.nodes))
        dest_id = np.random.randint(0, len(network.nodes) - 1)
        if orig_id == dest_id:
            dest_id += 1

        orig_location = LabelLocation(str(orig_id))
        dest_location = LabelLocation(str(dest_id))

        # Calculate travel time and fare
        try:
            travel_time = durations[str(orig_id)][str(dest_id)]
        except KeyError:
            # If travel time is not available, skip this iteration
            t += interarrival_distribution.rvs()
            continue

        # calculate fare based on time
        fare_value = (hour_fare / 3600) * travel_time

        t_ready = round(t, 3)

        # Determine the release time based on known_portion and advance_notice

        if known_portion == 100:
            t_release = start_time
        elif known_portion == 0 and advance_notice == 0:
            t_release = t_ready
        else:
            t_release = max(start_time, t_ready - advance_notice * 60)

        # Generate number of passengers (between 1 and 3)
        nb_passengers = randint(1, 4)

        # Create a new RideRequest object
        trip = RideRequest(str(int(request_id)),
                           origin=orig_location,
                           destination=dest_location,
                           nb_passengers=nb_passengers,
                           release_time=round(t_release, 3),
                           ready_time=t_ready,
                           due_time=100000,
                           latest_pickup=round(t_ready + time_window * 60, 3),
                           fare=round(fare_value, 3),
                           shortest_travel_time=travel_time)

        trips.append(trip)
        request_id += 1

        # Check if the maximum number of requests has been reached
        if nb_requests is not None and len(trips) >= nb_requests:
            break

        # Generate the time for the next request
        t += round(interarrival_distribution.rvs(),1)

    return trips
