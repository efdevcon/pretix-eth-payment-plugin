Pretix Ethereum Payment Provider
==========================

!! This plugin is not ready for simple 3rd party production use *yet* - if you want to use it you must really understand the code !!
PRs to make it production ready and more eyes on this code are most welcome!

This is a plugin for `pretix`_. This plugin supports both Ethereum and DAI.

Development setup
-----------------

1. Make sure that you have a working `pretix development setup`_.

2. Clone this repository, eg to ``local/pretix-eth-payment-plugin``.

3. Activate the virtual environment you use for pretix development.

4. Execute ``python setup.py develop`` within this directory to register this application with pretix's plugin registry.

5. Restart your local pretix server. You can now use the plugin from this repository for your events by enabling it in
   the 'plugins' tab in the settings.

6. Head to the plugin settings page to set deposit addresses for both Ethereum and DAI.

License
-------


Copyright 2019 Victor(https://github.com/vic-en)

Released under the terms of the Apache License 2.0



.. _pretix: https://github.com/pretix/pretix
.. _pretix development setup: https://docs.pretix.eu/en/latest/development/setup.html
