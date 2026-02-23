
"""
Single-shot weapon: fires one HTTP request per attack round.
"""

import time
from typing import Any, Optional

import app.net
from app.models import AttackResult
from app.net import NetworkClient, RequestException
from . import Weapon, WeaponFactory


class SingleShotFactory(WeaponFactory):
    """
    Factory that produces `SingleShotWeapon` instances.
    """

    def make(self, network_client: Optional[Any] = None) -> 'SingleShotWeapon':

        return SingleShotWeapon(
            http_method=self._http_method,
            cache_buster=self._cache_buster,
            network_client=network_client
        )


class SingleShotWeapon(Weapon):
    """
    Weapon that fires a single HTTP request per `attack()` call and reports the result.
    """

    def __init__(self, **kwargs: Any) -> None:
        Weapon.__init__(self, **kwargs)
        network_client = kwargs.get('network_client', None)
        if network_client is not None:
            self._network_client = network_client
        else:
            self._network_client = NetworkClient()
            self._network_client.rotate_user_agent()

    def attack(self) -> AttackResult:
        result = AttackResult()
        start_time = time.time()

        try:
            target_url = app.net.url_ensure_valid(self._target_url)

            if self._cache_buster:
                target_url = app.net.url_cache_buster(target_url)

            response, bytes_sent, bytes_received = self._network_client.request(self._http_method, target_url)
            response_time_ms = (time.time() - start_time) * 1000

            result.num_hits = 1
            result.http_status = response.getcode()
            result.bytes_sent = bytes_sent
            result.bytes_received = bytes_received
            result.response_time_ms = response_time_ms

        except RequestException:
            result.errors = 1
            result.http_status = None
        except Exception:
            result.errors = 1
            result.http_status = None

        return result
