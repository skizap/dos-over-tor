
class WeaponFactory:
    """
    Weapons factory which produces Weapon instances. Should be extended for each type of weapon.
    """

    def make(self):
        """
        Create a Weapon instance
        """
        pass


class Weapon:
    """
    A weapon which can be used in an attack
    """

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
