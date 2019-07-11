import os
from distutils.command.build import build

from setuptools import setup, find_packages


with open(os.path.join(os.path.dirname(__file__), 'README.rst'), encoding='utf-8') as f:
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
        'pytest>=5.0.1,<6',
        'pytest-django>=3.5.1,<4',
    ],
    'lint': [
        'flake8>=3.5.0,<4',
        "mypy==0.701",
    ],
    'dev': [
        'tox>=1.8.0,<2',
    ],
}

extras_require['dev'] = (
    extras_require['dev']
    + extras_require['test']
    + extras_require['lint']
)


setup(
    name='pretix-eth-payment-plugin',
    version='1.0.1',
    description='An ethereum payment provider plugin for pretix software',
    long_description=long_description,
    url='https://github.com/esPass/pretix-eth-payment-plugin',
    author='Victor(https://github.com/vic-en)',
    author_email='victoreni14@gmail.com',
    license='Apache Software License',
    install_requires=[
        "Django==2.2.2",
        "pretix==2.8.2",
        "eth-typing>=2.1.0,<3",
        "eth-utils>=1.6.1,<2",
        "eth-hash[pycryptodome]>=0.2.0,<0.3",
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
