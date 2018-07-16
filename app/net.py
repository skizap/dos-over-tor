
import random
import urllib.request
import user_agent


_user_agent = None


class RequestException(Exception):
    """
    Exception thrown when a call to request() fails.
    """

    pass


def new_user_agent():
    """
    Generates a new fake user agent for use with request()
    """

    global _user_agent

    _user_agent = user_agent.generate_user_agent(os=('mac', 'win'))


def get_user_agent():
    """
    Returns the fake user agent which will be used with request()
    """

    global _user_agent

    return _user_agent


def request(method, url):
    """
    Make a HTTP request to the given URL.
    :param method: The HTTP method to use when making the request
    :param url: The URL to request
    """

    response = None

    try:

        headers = {
            'User-Agent': get_user_agent()
        }

        request_obj = urllib.request.Request(
            url,
            method=method.upper(),
            headers=headers
        )

        response = urllib.request.urlopen(request_obj)

    except urllib.error.HTTPError as ex:

        response = ex

    except Exception as ex:
        # assume all other exceptions thrown are errors of some sort

        raise RequestException(str(ex))

    return response


def lookupip():
    """
    Poll a third party service to see what our public facing IP is.
    """

    ourip = urllib.request.urlopen('https://icanhazip.com').read()
    ourip = ourip.decode("utf-8")
    ourip = ourip.strip("\n")

    return ourip

def url_ensure_valid(url):
    """
    Ensure the given URL is valid and contains the correct scheme etc.
    :param url: The URL to validate
    """

    scheme, netloc, path, params, query, fragment = urllib.parse.urlparse(url)

    if not netloc:
        netloc, path = path, ''

    if not scheme:
        scheme = 'https'

    return urllib.parse.urlunparse(
        (scheme, netloc, path, params, query, fragment)
    )


def url_cache_buster(url):
    """
    Add a cache busting query string to the given URL
    :param url: The URL to add the query string to.
    """

    scheme, netloc, path, params, query, fragment = urllib.parse.urlparse(url)

    query = "%d" % (
        random.randint(1, 999999999)
    )

    return urllib.parse.urlunparse(
        (scheme, netloc, path, params, query, fragment)
    )
