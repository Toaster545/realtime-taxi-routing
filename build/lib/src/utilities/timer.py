from datetime import datetime, timedelta

class Timer:
    """
    A simple Timer class to measure elapsed time.
    """
    def __init__(self):
        """
        Initializes the Timer object with default values.
        """
        self._elapsed_since_start = timedelta(0)
        self._total_elapsed = timedelta(0)
        self._initial_time = datetime.now()
        self._start_time = None
        self._is_started = False

    def start(self):
        """
        Starts the timer. Resets the elapsed time since the last start.

        Raises:
            RuntimeError: If the timer is already running.
        """
        if self._is_started:
            raise RuntimeError("Timer is already running.")
        self._start_time = datetime.now()
        self._is_started = True

    def stop(self):
        """
        Stops the timer and calculates the elapsed time since it was last started.
        Accumulates the total elapsed time.

        Raises:
            RuntimeError: If the timer is not running.
        """
        if not self._is_started:
            raise RuntimeError("Timer is not running.")
        end_time = datetime.now()
        self._elapsed_since_start = end_time - self._start_time
        self._total_elapsed += self._elapsed_since_start
        self._is_started = False

    def elapsed_since_init(self):
        """
        Returns the total elapsed time since the Timer was initialized.
        This includes all cumulative intervals recorded by the Timer.

        Returns:
            float: Total elapsed time in seconds.
        """
        return self._total_elapsed.total_seconds()

    def elapsed_since_start(self):
        """
        Returns the elapsed time since the Timer was last started.
        If the Timer is currently running, it calculates the time up to now.

        Returns:
            float: Elapsed time in seconds.
        """
        if not self._is_started:
            return self._elapsed_since_start.total_seconds()
        current_elapsed = datetime.now() - self._start_time
        return current_elapsed.total_seconds()

    def reset(self):
        """
        Resets the Timer, clearing all recorded times.
        """
        self._elapsed_since_start = timedelta(0)
        self._total_elapsed = timedelta(0)
        self._is_started = False
        self._start_time = None
        self._initial_time = datetime.now()

    # Getters and setters
    @property
    def total_elapsed(self):
        return self._total_elapsed


    @property
    def initial_time(self):
        return self._initial_time

    @property
    def is_started(self):
        return self._is_started
