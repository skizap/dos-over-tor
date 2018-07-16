
from abc import abstractmethod
import random


class WeaponFactory:
    """
    Weapons factory which produces Weapon instances. Should be extended for each type of weapon.
    """

    def __init__(self, **kwargs):
        """

        :param http_method: HTTP method to use when making HTTP requests
        :param cache_buster: Whether to add cache busting query strings to queries
        """

        self._http_method = kwargs['http_method'] if 'http_method' in kwargs else 'GET'
        self._cache_buster = kwargs['cache_buster'] if 'cache_buster' in kwargs else False

    @abstractmethod
    def make(self):
        """
        Create a Weapon instance
        """
        pass


class Weapon:
    """
    A weapon which can be used in an attack
    """

    def __init__(self, **kwargs):
        """

        :param http_method: HTTP method to use when making HTTP requests
        :param cache_buster: Whether to add cache busting query strings to queries
        """

        self._http_method = kwargs['http_method'] if 'http_method' in kwargs else 'GET'
        self._cache_buster = kwargs['cache_buster'] if 'cache_buster' in kwargs else False

    @abstractmethod
    def attack(self, target_url):
        """
        Start attacking the given target URL
        :param target_url: The target URL/domain to be attacked
        """
        pass

    def hold_fire(self):
        """
        Stop attacking the target.
        """
        pass
