# Automated submodule updates

The Ansible content this source ships (`ansible/roles/*`, `ansible/collections/*`)
is vendored as git submodules pinned to each upstream's latest **release tag**.
The [`bump-submodules.yml`](./bump-submodules.yml) workflow keeps those pins
current — every run is a full sweep of all submodules:

- a daily `schedule` (08:17 UTC, ~3am US Eastern) re-pins anything that has
  drifted from its latest release tag;
- you can also run it on demand from the Actions tab (`workflow_dispatch`).

**Releasing a role?** After tagging the release, trigger the sweep right away
instead of waiting for the nightly run:

    gh workflow run bump-submodules.yml -R badsectorlabs/ludus-source-bsl

The sweep opens (or updates) a single rolling PR on the fixed branch
`automation/bump-submodules`; merge it to adopt the new pins. Review the submodule pin moves in the PR body before
merging.
