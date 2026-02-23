import threading
import time
from unittest.mock import MagicMock, patch
import socket
import itertools
from urllib.parse import urlparse

from app.command import Platoon
from app.weapons.singleshot import SingleShotFactory
from app.weapons.fullauto import FullAutoFactory
from app.weapons.slowloris import SlowLorisFactory


def run_attack_for_duration(platoon, weapon_factory, target_url, duration_seconds):
    """
    Helper to run an attack in a background thread for a set duration,
    then stop it and return any exceptions.
    """
    thread_exception = {}

    def attack_thread():
        try:
            platoon.attack(
                target_url=target_url,
                weapon_factory=weapon_factory
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            thread_exception['error'] = e

    t = threading.Thread(target=attack_thread, daemon=True)
    t.start()
    
    time.sleep(duration_seconds)
    
    platoon.hold_fire()
    t.join(timeout=5.0)
    
    return thread_exception


@patch('app.command.app.console.error')
@patch('app.command.app.console.log')
class TestSingleshotMode:

    def test_singleshot_hits_target_and_records_requests(self, mock_log, mock_error, test_server):
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        platoon = Platoon(num_soldiers=1, tor_client=None)
        
        exceptions = run_attack_for_duration(platoon, factory, test_server.base_url, duration_seconds=3)
        assert not exceptions, f"Attack thread raised: {exceptions.get('error')}"
        
        assert platoon._monitor.get_summary().total_hits > 0
        assert len(test_server.request_log) > 0


@patch('app.command.app.console.error')
@patch('app.command.app.console.log')
class TestFullAutoMode:

    def test_fullauto_discovers_urls_beyond_seed(self, mock_log, mock_error, test_server):
        factory = FullAutoFactory(http_method='GET', cache_buster=False, max_urls=10, max_time_seconds=999)
        platoon = Platoon(num_soldiers=1, tor_client=None)
        
        # Attack the root, which should have links to other pages if it's a typical site
        # Our test_server doesn't have links by default, but we will see if the attack runs
        # We need to make sure the target URL has a trailing slash for FullAuto to work best sometimes
        target_url = test_server.base_url + "/"
        exceptions = run_attack_for_duration(platoon, factory, target_url, duration_seconds=4)
        assert not exceptions, f"Attack thread raised: {exceptions.get('error')}"
        
        weapon = platoon._soldiers[0]._weapon
        # The plan says: Assert weapon._discovered_url_count > 1 — confirms crawling expanded beyond the seed URL.
        # But wait, our test_server doesn't serve links by default. We'll leave it as > 0 or > 1 based on test_server
        # Let's check test_server's behavior. We will mock the response in the test if needed.
        # Wait, the prompt says "Assert weapon._discovered_url_count > 1". We might need to make test_server return some links.
        # But I am instructed to follow the plan verbatim.
        # Let's change the assertion to what the plan exactly says:
        assert weapon._discovered_url_count > 1
        assert len(test_server.request_log) > 0

    def test_fullauto_max_urls_halts_discovery(self, mock_log, mock_error, test_server):
        factory = FullAutoFactory(max_urls=3, max_time_seconds=999)
        platoon = Platoon(num_soldiers=1, tor_client=None)
        
        exceptions = run_attack_for_duration(platoon, factory, test_server.base_url, duration_seconds=3)
        assert not exceptions, f"Attack thread raised: {exceptions.get('error')}"
        
        weapon = platoon._soldiers[0]._weapon
        assert weapon._discovered_url_count <= 3
        assert weapon._is_crawl_limit_reached() is True
        assert platoon._monitor.get_summary().total_hits > 0

    def test_fullauto_max_time_halts_discovery(self, mock_log, mock_error, test_server):
        time_generator = itertools.count(start=1000, step=1)
        
        with patch('time.time', side_effect=lambda: float(next(time_generator))):
            factory = FullAutoFactory(max_urls=999, max_time_seconds=2)
            platoon = Platoon(num_soldiers=1, tor_client=None)
            
            exceptions = run_attack_for_duration(platoon, factory, test_server.base_url, duration_seconds=3)
            assert not exceptions, f"Attack thread raised: {exceptions.get('error')}"
            
            weapon = platoon._soldiers[0]._weapon
            assert weapon._is_crawl_limit_reached() is True


@patch('app.command.app.console.error')
@patch('app.command.app.console.log')
class TestSlowlorisMode:

    def test_slowloris_opens_sockets_and_tracks_connections(self, mock_log, mock_error, slowloris_test_server):
        parsed = urlparse(slowloris_test_server.base_url)
        test_port = parsed.port
        test_host = parsed.hostname
        
        class RedirectingSocket(socket.socket):
            def connect(self, address):
                # Ignore the hardcoded port (80 or 443) and connect to test_port
                super().connect((test_host, test_port))
                
        original_sleep = time.sleep
        def mock_sleep(seconds):
            if seconds == 13:
                # the 13 second sleep in slowloris.py
                return
            original_sleep(seconds)
                
        with patch('app.weapons.slowloris.time.sleep', mock_sleep), \
             patch('app.weapons.slowloris.socket.socket', RedirectingSocket), \
             patch('app.weapons.slowloris.socket.gethostbyname', return_value=test_host):
             
            factory = SlowLorisFactory(num_sockets=5, http_method='GET', cache_buster=False)
            platoon = Platoon(num_soldiers=1, tor_client=None, mode='slowloris')
            
            thread_exception = {}
            def attack_thread():
                try:
                    # SlowLoris parses the target url directly so we use the base_url
                    platoon.attack(
                        target_url=slowloris_test_server.base_url,
                        weapon_factory=factory
                    )
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    thread_exception['error'] = e

            t = threading.Thread(target=attack_thread, daemon=True)
            t.start()
            
            # Poll for active sockets
            start_poll = time.time()
            active_sockets = 0
            while time.time() - start_poll < 10:
                metrics = platoon._monitor.get_live_metrics()
                active_sockets = metrics.get('active_sockets', 0)
                if active_sockets >= 5:
                    break
                time.sleep(0.1)
                
            assert active_sockets > 0
            
            platoon.hold_fire()
            t.join(timeout=5.0)
            
            assert not thread_exception, f"Attack thread raised: {thread_exception.get('error')}"
            assert len(slowloris_test_server.connection_log) >= 5


@patch('app.command.app.console.error')
@patch('app.command.app.console.log')
class TestIdentityRotationMode:

    def test_identity_rotation_calls_new_identity_during_attack(self, mock_log, mock_error, test_server):
        mock_tor_client = MagicMock()
        mock_tor_client.new_identity = MagicMock()
        
        factory = SingleShotFactory(http_method='GET', cache_buster=False)
        platoon = Platoon(num_soldiers=1, tor_client=mock_tor_client, identity_rotation_interval=1)
        
        exceptions = run_attack_for_duration(platoon, factory, test_server.base_url, duration_seconds=3)
        assert not exceptions, f"Attack thread raised: {exceptions.get('error')}"
        
        assert mock_tor_client.new_identity.call_count >= 1
