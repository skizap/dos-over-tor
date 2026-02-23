
"""
Full-auto weapon: crawls the target domain and fires at every discovered URL.
"""

import random
import time
import urllib
from typing import Any, Optional
from bs4 import BeautifulSoup
import app.net
from app.models import AttackResult
from app.net import NetworkClient, RequestException
from . import Weapon, WeaponFactory


class FullAutoFactory(WeaponFactory):
    """
    Factory that produces `FullAutoWeapon` instances with crawl limits.
    """

    def __init__(self, **kwargs: Any) -> None:
        WeaponFactory.__init__(self, **kwargs)

        self._max_urls = kwargs['max_urls'] if 'max_urls' in kwargs else 500
        self._max_time_seconds = kwargs['max_time_seconds'] if 'max_time_seconds' in kwargs else 180

    def make(self, network_client: Optional[Any] = None) -> 'FullAutoWeapon':

        return FullAutoWeapon(
            http_method=self._http_method,
            cache_buster=self._cache_buster,
            max_urls=self._max_urls,
            max_time_seconds=self._max_time_seconds,
            network_client=network_client
        )


class FullAutoWeapon(Weapon):
    """
    Weapon that crawls the target domain and attacks all discovered URLs. Respects `max_urls` and `max_time_seconds` crawl limits.
    """

    def __init__(self, **kwargs: Any) -> None:
        Weapon.__init__(self, **kwargs)

        self._urls = []
        network_client = kwargs.get('network_client', None)
        if network_client is not None:
            self._network_client = network_client
        else:
            self._network_client = NetworkClient()
            self._network_client.rotate_user_agent()

        self._max_urls = kwargs['max_urls'] if 'max_urls' in kwargs else 500
        self._max_time_seconds = kwargs['max_time_seconds'] if 'max_time_seconds' in kwargs else 180
        self._start_time = None
        self._discovered_url_count = 0

    def target(self, target_url: str, monitor: Optional[Any] = None) -> None:
        super().target(target_url, monitor=monitor)

        # add the target URl as the first URL in our running list

        target_url = app.net.url_ensure_valid(target_url)

        # set start time if this is the first URL being targeted
        if self._start_time is None:
            self._start_time = time.time()

        self._add_url(
            parent_url=target_url,
            new_url=target_url
        )

    def _is_crawl_limit_reached(self) -> bool:
        """
        Check if the crawl limit has been reached based on URL count or elapsed time.
        :return: True if limits are reached, False otherwise
        """
        # If crawling hasn't started yet, no limit is reached
        if self._start_time is None:
            return False

        # Check URL count limit
        if self._discovered_url_count >= self._max_urls:
            return True

        # Check time limit
        elapsed_time = time.time() - self._start_time
        if elapsed_time >= self._max_time_seconds:
            return True

        return False

    def _add_url(self, **kwargs: Any) -> None:
        """
        Add a new URL to our internal list for attack
        :param parent_url: The URL which the new_url was scraped from
        :param new_url: The new URL to add to our list. Relative URLs will be automatically resolved based on the
        parent_url
        """

        # Check if crawl limits are reached before adding new URLs
        if self._is_crawl_limit_reached():
            return

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
                    self._discovered_url_count += 1

    def _hit(self, target_url: str) -> tuple[int, int, int]:
        """
        Hit a URL and parse it for more links.
        Bytes sent and received are best-effort estimates based on request headers and Content-Length.
        Actual wire bytes may differ.
        """

        target_url = app.net.url_ensure_valid(target_url)

        if self._cache_buster:
            target_url = app.net.url_cache_buster(target_url)

        # hit the URL and get HTML content for parsing

        response, bytes_sent, bytes_received = self._network_client.request(self._http_method, target_url)
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

        return (status_code, bytes_sent, bytes_received)

    def attack(self) -> AttackResult:
        result = AttackResult()
        start_time = time.time()

        try:
            # select a random target URL from our list and hit it
            this_target_url = self._urls[random.randint(0, len(self._urls)-1)]
            status_code, bytes_sent, bytes_received = self._hit(this_target_url)
            response_time_ms = (time.time() - start_time) * 1000

            result.num_hits = 1
            result.http_status = status_code
            result.bytes_sent = bytes_sent
            result.bytes_received = bytes_received
            result.response_time_ms = response_time_ms

        except Exception:
            result.errors = 1
            result.http_status = None

        return result
