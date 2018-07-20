
from abc import abstractmethod


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
        Create a new Weapon instance
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

        self._target_url = ''

    def target(self, target_url):
        """
        Set the target URL/domain to be attacked
        :param target_url: The target URL/domain to be attacked
        """

        self._target_url = target_url

    @abstractmethod
    def attack(self):
        """
        Run a single round of attacks against the target (set via target(target_url=XXX))
        """
        pass

    def hold_fire(self):
        """
        Stop attacking the target
        """
        pass
