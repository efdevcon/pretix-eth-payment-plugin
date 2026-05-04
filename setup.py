import os
import re
from distutils.command.build import build  # type: ignore

from setuptools import setup, find_packages


with open(os.path.join(os.path.dirname(__file__), 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


# Single source of truth for the version — read from pretix_eth/__init__.py
# so version bumps happen in one file and flow to: pip's installed metadata,
# the Pretix plugin registry (apps.py PretixPluginMeta.version), and the
# browser-side cache-buster (?v=... on bundle.js / styles.css).
def _read_version() -> str:
    init_path = os.path.join(os.path.dirname(__file__), 'pretix_eth', '__init__.py')
    with open(init_path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^__version__\s*=\s*["\']([^"\']+)["\']', line)
            if m:
                return m.group(1)
    raise RuntimeError('Could not find __version__ in pretix_eth/__init__.py')


def _maybe_collectstatic():
    try:
        from django.core import management
        management.call_command('collectstatic', '--noinput', verbosity=1)
        print('[pretix_eth] collectstatic completed')
    except Exception as e:
        print(f'[pretix_eth] collectstatic skipped ({e})')


def _maybe_build_frontend():
    """Build dist/bundle.js if it doesn't already exist.

    Deliberately short-circuits when the bundle is present so that `pip install`
    doesn't run pnpm on every reinstall (CI / prod boxes may not even have pnpm).
    If you edit src/* and want `pip install -e --force-reinstall` to rebuild
    automatically, delete `pretix_eth/static/wc_inject/dist/` first, OR run
    `make frontend-build` / `pnpm run build` directly. See Makefile targets."""
    import shutil
    import subprocess
    wc_dir = os.path.join(os.path.dirname(__file__), 'pretix_eth', 'static', 'wc_inject')
    dist_file = os.path.join(wc_dir, 'dist', 'bundle.js')
    if os.path.isfile(dist_file):
        return
    if not shutil.which('pnpm'):
        print('[pretix_eth] pnpm not found; skipping frontend build')
        return
    print('[pretix_eth] Building frontend bundle via pnpm...')
    subprocess.check_call(['pnpm', 'install'], cwd=wc_dir)
    subprocess.check_call(['pnpm', 'run', 'build'], cwd=wc_dir)


class CustomBuild(build):
    def run(self):
        from django.core import management
        management.call_command('compilemessages', verbosity=1)
        _maybe_build_frontend()
        build.run(self)
        _maybe_collectstatic()


class CustomDevelop(object):
    """Mixin that runs collectstatic after 'pip install -e' (setup.py develop)."""
    def run(self):
        super().run()
        _maybe_collectstatic()


# Import develop command and create a subclass with our mixin
try:
    from setuptools.command.develop import develop as _develop

    class CustomDevelopCmd(CustomDevelop, _develop):
        pass

    cmdclass = {
        'build': CustomBuild,
        'develop': CustomDevelopCmd,
    }
except ImportError:
    cmdclass = {
        'build': CustomBuild,
    }


extras_require = {
    'test': [
        'pytest>=5',
        'pytest-django>=3.5',
        'celery>=5',
        'pytest-asyncio>=0.23',
    ],
    'lint': [
        'flake8>=3.7',
        'mypy>=0.931',
    ],
    'dev': [
        'tox>=3.14.5,<4',
    ],
}

extras_require['dev'] = (
    extras_require['dev']
    + extras_require['test']
    + extras_require['lint']
)


setup(
    name='pretix-eth-payment-plugin',
    version=_read_version(),
    description='Ethereum payment provider plugin for Pretix ticket sales with WalletConnect',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/efdevcon/pretix-eth-payment-plugin',
    author='Pretix Ethereum Plugin Developers',
    author_email='pretix-eth-payment-plugin@ethereum.org',
    license='Apache Software License',
    install_requires=[
        "pretix>=4.16",
        "web3>=7.12.0",
        "eth-typing",
        "eth-abi",
        "eth-account>=0.13.6",
        "setuptools>=68.0.0",
        "httpx>=0.27",
        # django-bootstrap3 22.2 under py3.8, added for pip legacy resolver to avoid conflicts
        'importlib-metadata<3; python_version<"3.8"',
    ],
    python_requires='>=3.7, <4',
    extras_require=extras_require,
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    cmdclass=cmdclass,
    entry_points="""
[pretix.plugin]
pretix_eth=pretix_eth:PretixPluginMeta
""",
)
