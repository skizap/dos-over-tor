
import random
import threading
import time
import app.console
from app.net import RequestException


class Monitor:
    """
    Attack status monitor, records analytics on the attack and maintains the statsu displayed in the status line
    """

    BUCKET_SECS = 3  # number of seconds each hit bucket covers

    def __init__(self):

        # lock used when modifying the monitor state
        self._lock = threading.Lock()

        # monitor status / state

        self._last_http_status = 0
        self._start_time = 0

        self._hit_buckets = []
        self._hit_buckets_index = 0

    def start(self):
        """
        Start monitoring. This will reset the internal state of the monitor so hits per sec
        will be calculated from now on.
        """

        self._lock.acquire()

        self._last_http_status = 200
        self._start_time = time.time()

        # initialise all of the hit buckets
        self._hit_buckets_index = 0
        for i in range(0, self._num_buckets()):
            self._hit_buckets.append(0)

        self._lock.release()

    def report_hit(self, thread, num_hits, http_status):
        """
        Report a hit on the target from a soldier thread
        :param thread: The ID of the soldier thread which is reporting the hit
        :param num_hits: The number of hits to record, ussually 1 but can be more if a compund attack
        :param http_status: The status the server returned (e.g. 200 for OK etc.)
        """

        self._lock.acquire()

        self._last_http_status = http_status

        # add the hits to the current bucket
        hit_bucket_index = self._current_bucket()
        self._hit_buckets[hit_bucket_index] += num_hits

        # clear the next bucket, so they always restart at 0
        hit_bucket_index = (hit_bucket_index+1) % self._num_buckets()
        self._hit_buckets[hit_bucket_index] = 0

        self._lock.release()

    def get_status(self):
        """
        Returns the monitor status.
        :return: tuple (last_http_status, hits_per_second)
        """

        # get hits from the previous hit bucket, while the current one is being populated
        hit_bucket_index = (self._current_bucket()-1) % self._num_buckets()
        num_hits = self._hit_buckets[hit_bucket_index]

        return (
            self._last_http_status,
            num_hits / self.BUCKET_SECS
        )

    def _num_buckets(self):
        return 3  # 1 being counted, 1 being used by get_status() and 1 cleared ready for the next round

    def _current_bucket(self):
        return int(time.time()/self.BUCKET_SECS) % self._num_buckets()


class SoldierThread(threading.Thread):

    def __init__(self, tid, monitor):
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

    def attack(self, **kwargs):
        """
        Start an attack on the given target. Will call the soldier threads start()
        :param target_url: The target URL to attack
        :param weapon: The app.weapons.Weapon instance to use in the attack
        """

        self._target_url = kwargs['target_url'] if 'target_url' in kwargs else None
        self._weapon = kwargs['weapon'] if 'weapon' in kwargs else None

        self._weapon.target(self._target_url)

        self._is_attacking = True
        self.start()

    def hold_fire(self):
        """
        Signal to the soldier thread to stop attacking. Will finish its last round then will stop.
        """

        app.console.log("stopping soldier thread #%d" % self._id)

        self._is_attacking = False

    def wait_done(self):
        """
        Wait for the soldier thread to finish its last round. Calls .join() on the soldier thread.
        """

        app.console.log("waiting for soldier thread #%d" % self._id)

        if self.isAlive():
            self.join()

    def run(self):

        app.console.log("starting soldier thread #%d" % self._id)

        while self._is_attacking:

            try:

                (num_hits, http_status) = self._weapon.attack()
                self._monitor.report_hit(self, num_hits, http_status)

            except RequestException as ex:

                app.console.error(str(ex))
                http_status = 0

                self._monitor.report_hit(self, 1, http_status)


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

            if self._is_attacking:
                # NOTE we check is_attacking here, just incase the user hit ctrl-c during the startup process

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

        # first request all the soldiers to hold fire
        for soldier in self._soldiers:
            soldier.hold_fire()

        # then wait for each of them to finish
        for soldier in self._soldiers:
            soldier.wait_done()
