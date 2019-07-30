# Pretix Ethereum Payment Provider

## **Warning**

**!! This plugin is not ready for 3rd party production use *yet*.  If you want
to use it you must really understand the code !!  PRs to make it production
ready and more eyes on this code are most welcome!**

## What is this

This is a plugin for [pretix](https://github.com/pretix/pretix). This plugin
supports both Ethereum and DAI.

## History

It started with [ligi](https://ligi) suggesting [pretix for Ethereum
Magicians](https://ethereum-magicians.org/t/charging-for-tickets-participant-numbers-event-ticketing-for-council-of-paris-2019/2321/2).

Then it was used for Ethereum Magicians in Paris (shout out to
[boris](https://github.com/bmann) for making this possible) - but accepting ETH
or DAI was a fully manual process there.

Afterwards boris [put up some funds for a gitcoin
bounty](https://github.com/spadebuilders/community/issues/30) to make a plugin
that automates this process. And [nanexcool](https://github.com/nanexcool)
increased the funds and added the requirement for DAI.

The initial version was developed by [vic-en](https://github.com/vic-en) but he
vanished from the project after cashing in the bounty money and left the plugin
in a non-working state.

Then the idea came up to use this plugin for DevCon5 and the plugin was forked
to this repo and [ligi](https://ligi.de), [david
sanders](https://github.com/davesque), [piper
meriam](https://github.com/pipermerriam), [rami](https://github.com/raphaelm),
[Pedro Gomes](https://github.com/pedrouid), and [Jamie
Pitts](https://github.com/jpitts) brought it to a state where it is usable for
DevCon5 (still a lot of work to be done to make this a good plugin). Currently,
it is semi-automatic. But it now has ERC-681 and Web3Connect/WalletConnect
support. If you want to dig a bit into the problems that emerged short before
the launch you can have a look at [this
issue](https://github.com/esPass/pretix-eth-payment-plugin/pull/49)

## Development setup

1. Make sure that you have a working [pretix development
   setup](https://docs.pretix.eu/en/latest/development/setup.html).
2. Clone this repository, e.g. to `local/pretix-eth-payment-plugin`.
3. Activate the virtual environment you created for your local pretix site that
   was created in step 1.
4. Execute `pip install -e .[dev]` within the `pretix-eth-payment-plugin` repo
   directory.
5. Restart your local pretix server. You can now use the plugin from this
   repository for your events by enabling it in the 'plugins' tab in the pretix
   site's admin settings.
6. Head to the plugin settings page to set the deposit address for both
   Ethereum and DAI.

## License

Copyright 2019 Victor (https://github.com/vic-en)

Released under the terms of the Apache License 2.0
