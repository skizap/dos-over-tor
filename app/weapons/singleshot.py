
from . import Weapon, WeaponFactory
import time


class SingleShotFactory(WeaponFactory):

    def make(self):
        return SingleShotWeapon()


class SingleShotWeapon(Weapon):

    def __init__(self):
        Weapon.__init__(self)

    def attack(self, target_url):

        print("hello %s" % target_url)

        time.sleep(1)


