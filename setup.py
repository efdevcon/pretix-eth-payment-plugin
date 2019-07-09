import os
from distutils.command.build import build

from setuptools import setup, find_packages


try:
    with open(os.path.join(os.path.dirname(__file__), 'README.rst'), encoding='utf-8') as f:
        long_description = f.read()
except:
    long_description = ''


class CustomBuild(build):
    def run(self):
        from django.core import management
        management.call_command('compilemessages', verbosity=1)
        build.run(self)


cmdclass = {
    'build': CustomBuild
}


setup(
    name='pretix-eth-payment-plugin',
    version='1.0.0',
    description='An ethereum payment provider plugin for pretix software',
    long_description=long_description,
    url='https://github.com/vic-en/pretix-eth-payment-plugin',
    author='Victor(https://github.com/vic-en)',
    author_email='victoreni14@gmail.com',
    license='Apache Software License',

    install_requires=[
        "Django==2.2.2",
        "pretix==2.8.2",
    ],
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    cmdclass=cmdclass,
    entry_points="""
[pretix.plugin]
pretix_eth=pretix_eth:PretixPluginMeta
""",
)
