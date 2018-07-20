
import app.net
from . import Weapon, WeaponFactory


class SingleShotFactory(WeaponFactory):

    def make(self):

        return SingleShotWeapon(
            http_method=self._http_method,
            cache_buster=self._cache_buster
        )


class SingleShotWeapon(Weapon):

    def attack(self):

        target_url = app.net.url_ensure_valid(self._target_url)

        if self._cache_buster:
            target_url = app.net.url_cache_buster(target_url)

        response = app.net.request(self._http_method, target_url)
        status_code = response.getcode()

        return (1, status_code)  # 1 hit
