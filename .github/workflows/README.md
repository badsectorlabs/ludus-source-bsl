# Automated submodule updates

The Ansible content this source ships (`ansible/roles/*`, `ansible/collections/*`)
is vendored as git submodules pinned to each upstream's latest **release tag**.
The [`bump-submodules.yml`](./bump-submodules.yml) workflow keeps those pins
current — every run is a full sweep of all submodules:

- a weekly `schedule` re-pins anything that has drifted from its latest release tag;
- you can also run it on demand from the Actions tab (`workflow_dispatch`).

It opens (or updates) a single rolling PR on the fixed branch
`automation/bump-submodules`; merge it to adopt the new pins. If nothing is stale,
no PR is opened.
