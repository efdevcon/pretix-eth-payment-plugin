import os
from distutils.command.build import build  # type: ignore

from setuptools import setup, find_packages


with open(os.path.join(os.path.dirname(__file__), 'README.md'), encoding='utf-8') as f:
    long_description = f.read()


class CustomBuild(build):
    def run(self):
        from django.core import management
        management.call_command('compilemessages', verbosity=1)
        build.run(self)


cmdclass = {
    'build': CustomBuild
}


extras_require = {
    'test': [
        'pytest>=5',
        'pytest-django>=3.5',
        'celery>=5',
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
    version='4.0.0-dev',
    description='Ethereum payment provider plugin for Pretix ticket sales, using Daimo Pay',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/daimo-eth/pretix-eth-payment-plugin',
    author='Pretix Ethereum Plugin Developers',
    author_email='pretix-eth-payment-plugin@ethereum.org',
    license='Apache Software License',
    install_requires=[
        "pretix>=4.16",
        "web3>=6",
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
