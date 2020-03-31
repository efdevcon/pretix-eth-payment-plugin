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
it is semi-automatic. But it now has ERC-681 and Web3Modal
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

## Automatic payment confirmation with the `confirm_payments` command

This plugin includes a [django management
command](https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/#module-django.core.management)
that can be used to automatically confirm orders from Ethereum transactions and
ERC20 token transfers.  By default, this command will perform a dry run which
only displays payment records that would be modified and why but without
actually modifying them.  Here are some example invocations of this command:
```bash
# Using the pretix module
python -m pretix confirm_payments --event-slug=devcon-5 --no-dry-run

# Using a django manage.py file
python manage.py confirm_payments --event-slug=devcon-5 --no-dry-run
```
Above, the `confirm_payments` command uses the `--event-slug` argument to
determine the wallet address to which ticket payments for the `devcon-5` event
were sent.  It then inspects *all* external and internal transactions sent to
the event's wallet address to determine if sufficient payments were made for
payment records identified by the payment IDs encoded in the transactions' wei
values.  It also inspects all token transfer events targeting the event's
wallet address for the DAI stablecoin's mainnet contract address.  The
`--no-dry-run` flag directs the command to modify and confirm payments
identified by transactions and transfers.  Without this flag, the command will
only display which records would be modified.  Alternatively, the same command
above could have been invoked as follows:
```bash
python manage.py confirm_payments --wallet-address=<devcon-5-wallet-address> --no-dry-run
```
...where `<devcon-5-wallet-address>` is replaced with the explicit
`0x`-prefixed wallet address for the Devcon 5 event.

The `confirm_payments` command also supports a number of other arguments.  Here
are some example uses of them:
```bash
python manage.py confirm_payments \
    --event-slug=<slug> \
    --token-address=<token-address> \
    --api=blockscout-mainnet \
    --start-block=<start-block> \
    --end-block=<end-block> \
```
The above command confirms payments for the event identified by `<slug>` using
the ERC20 token at address `<token-address>` on the Ethereum mainnet queried
through Blockscout.  It only considers transactions and token transfers that
occurred between and within blocks `<start-block>` and `<end-block>`.  Also,
because the `--no-dry-run` flag is absent, it simply prints the payments that
*would be* confirmed by the command without confirming them.

For more details about the `confirm_payments` command and its options, the
command may be invoked with `--help`:
```bash
python manage.py confirm_payments --help
```

## License

Copyright 2019 Victor (https://github.com/vic-en)

Released under the terms of the Apache License 2.0
