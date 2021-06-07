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
        'pytest>=5.1,<6',
        'pytest-django>=3.5,<4',
    ],
    'lint': [
        'flake8>=3.7,<4',
        'mypy==0.720',
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
    version='2.0.4-dev',
    description='Ethereum payment provider plugin for pretix software',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/esPass/pretix-eth-payment-plugin',
    author='Pretix Ethereum Plugin Developers',
    author_email='pretix-eth-payment-plugin@ethereum.org',
    license='Apache Software License',
    install_requires=[
        "pretix>=3.8.0",
        "web3>=5.7.0",
        "eth-abi>=2.1.1,<3",
        "eth-typing>=2.2.1,<3",
        "eth-utils>=1.8.4,<2",
        "eth-hash[pycryptodome]>=0.2.0,<0.3",
        # Requests requires urllib3 <1.26.0.  Can delete this later after
        # requests gets its act together.
        "urllib3<1.26.0",
    ],
    python_requires='>=3.6, <4',
    extras_require=extras_require,
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    cmdclass=cmdclass,
    entry_points="""
[pretix.plugin]
pretix_eth=pretix_eth:PretixPluginMeta
""",
)
