
import app.net
from . import Weapon, WeaponFactory
import time
import urllib.request


class SingleShotFactory(WeaponFactory):

    def make(self, **kwargs):

        return SingleShotWeapon(
            http_method=self._http_method,
            cache_buster=self._cache_buster
        )


class SingleShotWeapon(Weapon):

    def attack(self, target_url):

        target_url = app.net.url_ensure_valid(target_url)

        if self._cache_buster:
            target_url = app.net.url_cache_buster(target_url)

        response = app.net.request(self._http_method, target_url)
        status_code = response.getcode()

        return status_code
