perryt
======

perryt is a command line client for gerrit that allows you to query a gerrit server.

## Usage
There are two ways of searching. The first is by owner.

    ./perryt.py owner <owner name> [--patchsets all|last] [--status open|reviewed|submitted|merged|closed|abandoned]

Example for getting all the merged changes (only displaying the merged patchset) for the user foobar

    ./perryt.py owner foobar --status merged

The second way is by reviewer.

    ./perryt.py reviewer <reviewer name> [--patchsets all|last] [--reviewed any|<reviewer name>] [--verified any|<verifier name>] [--status open|reviewed|submitted|merged|closed|abandoned]

Example for getting all the open changes and patchsets that have foobar as a reviewer and have been reviewed by somebody verified by tomas:

    ./perryt.py reviewer foobar --reviewed any --verified tomas --status open

## Requirements
- Python 2.7 (2.6 if you install argparse)
- ssh gerrit.ovirt.org in your shell works (username is correct, key has been added to gerrit)

## Future work
- It would be nice if the server was configurable and not hardcoded to gerrit.ovirt.org (DONE)
- Integrate with pygit to provide gitlog and diff info.
