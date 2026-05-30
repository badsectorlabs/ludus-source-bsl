# Ludus Templates

Self-contained [Packer](https://www.packer.io/) templates shipped by the
[Bad Sector Labs Ludus source](https://github.com/badsectorlabs/ludus-source-bsl).
Each directory builds one Ludus VM template. See
https://docs.ludus.cloud/docs/templates for details.

## Installing

Add this source to Ludus — its templates appear in the catalog, ready to sync
and build:

```
ludus source add https://github.com/badsectorlabs/ludus-source-bsl.git
```

Then build a template with `ludus templates build -n <template-name>`.

## Templates needing manual setup

`commando-vm`, `flare-vm`, and `remnux` build on a base image and need their
companion roles installed first:

```
ludus ansible role add badsectorlabs.ludus_commandovm
ludus ansible role add badsectorlabs.ludus_flarevm
ludus ansible role add badsectorlabs.ludus_remnux
```
