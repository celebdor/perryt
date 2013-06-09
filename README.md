perryt
======

perryt is a command line client for gerrit that allows you to query a gerrit server.

## Requirements
- Python 2
- ssh key in ~/.ssh/id_rsa the public part of which has been added to the target gerrit server

The usage is as follows (as of today it is hardcoded to work with gerrit.ovirt.org):

./perryt owner <owner name> [patchsets all] [status open|closed|merged]

Example for getting all the merged changes (only displaying the merged patchset) for the user foobar
./perryt owner foobar status merged

./perryt reviewer <reviewer name> [patchsets last] [reviewer any|<reviewer name>] [verifier any|<verifier name>] [status open|closed|merged]
Example for getting all the open changes and patchsets that have foobar as a reviewer and have been reviewed by somebody verified by tomas:
./perryt reviewer foobar reviewer any verified tomas status open
