#!/usr/bin/env python
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from dateparser import parser as timedelta_parser
from datetime import datetime
import json
import subprocess
import ConfigParser


def query(gerritURL, query):
    config = check_server()
    cmd = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '\
          '-p 29418 %s gerrit query --format=JSON --all-approvals --comments '\
          '--dependencies %s' % (config.get('server', 'url'), query)
    with open('/dev/null', 'w') as NULLOUT:
        output = subprocess.check_output(cmd.split(' '),
                                         stderr=NULLOUT.fileno())
        for line in output.split('\n'):
            if line:
                yield json.loads(line)


class Change(object):

    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            if key == 'owner':
                value = Owner(**value)
            elif key == 'patchSets':
                value = [PatchSet(change=self, **patchset) for
                         patchset in value]
            elif key == 'dependsOn':
                value = [Dependency(**dependency) for dependency in value]
            setattr(self, key, value)

    def __str__(self):
        return self.subject

    def __repr__(self):
        return '(%s)%s: %s - (%s) - %s' % \
            (self.project, self.id[:6], self.subject,
             'UP TO DATE' if self._up_to_date else 'OUTDATED DEP', self.owner)

    @property
    def _up_to_date(self):
        if hasattr(self, 'dependsOn'):
            return all(dependency.up_to_date for dependency in self.dependsOn)
        else:
            return False


class Dependency(object):

    def __init__(self, isCurrentPatchSet, revision, ref, id, number):
        self.up_to_date = isCurrentPatchSet
        self.revision = revision
        self.ref = ref
        self.id = id
        self.number = number
        self.patchSet = PatchSet.getInstanceByRef(ref)

    def __repr__(self):
        return 'dependency: %s' % self.ref


class Owner(object):
    cache = set()

    @classmethod
    def __get_cached(cls, name, email, username):
        for obj in cls.cache:
            if obj.name == name and obj.email == email and \
                    obj.username == username:
                return obj
        return None

    def __new__(cls, name, email=None, username=None):
        cached = cls.__get_cached(name, email, username)
        if cached:
            return cached
        return super(Owner, cls).__new__(cls)

    def __init__(self, name, email=None, username=None):
        if self in self.cache:
            return
        self.name = name
        self.email = email
        self.username = username
        self.cache.add(self)

    def __str__(self):
        if self.username:
            return self.username
        elif self.email:
            return self.email[:self.email.index('@')]
        return self.name

    def __repr__(self):
        return '%s<%s>' % (self.name, self.email)

    def matches(self, name):
        name = name.lower()
        instance_name = self.name.lower()
        identifiers = []
        if self.email:
            identifiers.append(self.email[:self.email.index('@')])
        identifiers.append(instance_name.replace(' ', '').lower())
        parts = instance_name.split()
        identifiers.append(parts[0] + parts[-1])
        identifiers.append(parts[0][0] + parts[-1])
        identifiers.append(parts[0] + ''.join(part[0] for part in parts[1:]))
        identifiers.append(''.join(part[0] for part in parts))
        for word in identifiers:
            if word.startswith(name):
                return True
        return False


class PatchSet(object):
    instances = dict()

    def __init__(self, number, revision, ref, uploader, createdOn=None,
                 approvals=None, comments=None, change=None, parents=None):
        self.number = int(number)
        self.revision = revision
        self.ref = ref
        self.uploader = Owner(**uploader)
        if createdOn:
            self.createdOn = datetime.fromtimestamp(createdOn)
        if approvals:
            self.approvals = [Approval(**approval) for approval in approvals]
        else:
            self.approvals = ()
        if comments:
            self.comments = [Comment(**comment) for comment in comments]
        self.change = change
        self.instances[self.ref] = self

    def __str__(self):
        r, v = self.score()
        return 'P%s (v: %s, r: %s)' % (self.number, v, r)

    def __repr__(self):
        r, v = self.score()
        return 'P%s (v: %s, r: %s - %r)' % (self.number, v, r, self.approvals)

    def score(self):
        r = 0
        v = 0
        for approval in self.approvals:
            if approval.type == 'v':
                v += approval.value
            else:
                r += approval.value
        return (r, v)

    def reviewed(self, reviewer=None):
        if reviewer == 'any':
            reviewer = None
        for approval in self.approvals:
            if approval.type == 'r':
                if reviewer:
                    return approval.by.matches(reviewer)
                else:
                    return True

    def verified(self, reviewer=None):
        if reviewer == 'any':
            reviewer = None
        for approval in self.approvals:
            if approval.type == 'v':
                if reviewer:
                    return approval.by.matches(reviewer)
                else:
                    return True

    @classmethod
    def getInstanceByRef(cls, ref):
        return cls.instances.get(ref)


class Approval(object):
    typeTrans = {'VRIF': 'v', 'CRVW': 'r', 'SUBM': 's'}

    def __init__(self, type, value, grantedOn, by, description=None):
        self.type = self.typeTrans[type]
        self.description = description
        self.value = int(value)
        self.grantedOn = datetime.fromtimestamp(grantedOn)
        self.by = Owner(**by)

    def __repr__(self):
        return '%s(%s:%s)' % (self.by, self.type, self.value)


class Comment(object):

    def __init__(self, reviewer, line, message, file):
        if reviewer:
            self.reviewer = Owner(**reviewer)
        self.line = int(line)
        self.message = message
        self.file = file

    def __repr__(self):
        if len(self.message) < 40:
            summary = self.message
        else:
            summary = self.message[:38] + u'…'
        return '%s:%s: %s - %s' % (self.file, self.line, summary,
                                   self.reviewer)


def execute_search(search, format_output):
    information = list(query('gerrit.ovirt.org', search))
    queryInfo = information.pop()
    changes = [Change(**change) for change in information]
    changes = sorted(changes, key=lambda change: change.lastUpdated)
    print u'Results: %s(time: %sµs)' % (queryInfo['rowCount'],
                                        queryInfo['runTimeMilliseconds'])
    print '=' * 80 + '\n'
    format_output(changes)


def owner(owner, patchsets=None, status=None, since=None):
    search = 'status:%s owner:%s' % (status or 'open', owner)
    if since:
        cut_date = datetime.now() - timedelta_parser.parse(since)

    def format_output(changes):
        for change in changes:
            if patchsets == 'last':
                patchSets = [change.patchSets[-1]]
            else:
                patchSets = change.patchSets
            if cut_date:
                patchSets = [patchSet for patchSet in patchSets if
                             cut_date <= patchSet.createdOn]
            if patchSets:
                print '%r' % change
                print '\t%s' % change.url
                for patchSet in patchSets:
                    print '\t%r' % patchSet
                print '\n'

    execute_search(search, format_output)


def reviewer(reviewer, patchsets=None, reviewed=None, verified=None,
             status=None, since=None):
    search = 'status:%s reviewer:%s' % (status or 'open', reviewer)
    if since:
        cut_date = datetime.now() - timedelta_parser.parse(since)

    def format_output(changes):
        for change in changes:
            if patchsets == 'last':
                patchSets = [change.patchSets[-1]]
            else:
                patchSets = change.patchSets
            if cut_date:
                patchSets = [patchSet for patchSet in patchSets if
                             cut_date <= patchSet.createdOn]
            if reviewed is not None:
                patchSets = [patchSet for patchSet in patchSets if
                             patchSet.reviewed(reviewed)]
            if verified is not None:
                patchSets = [patchSet for patchSet in patchSets if
                             patchSet.verified(verified)]
            if patchSets:
                print '%r' % change
                print '\t%s' % change.url
                for patchSet in patchSets:
                    print '\t%r' % patchSet
                print '\n'

    execute_search(search, format_output)


def check_server():
    CONF_FILE = 'perryt.cfg'
    config = ConfigParser.RawConfigParser()
    read = config.read(CONF_FILE)
    if not read:
        config.add_section('server')
        server_url = raw_input('Enter the gerrit server url to save to '
                               'perryt.cfg: ')
        config.set('server', 'url', server_url)
        with open(CONF_FILE, 'w') as conf:
            config.write(conf)
    return config

if __name__ == '__main__':
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(
        title='actions', description='available gerrit actions.',
        help='owner searches by owner and reviewer by reviewer.',
        dest='action')

    owner_parser = subparsers.add_parser('owner')
    owner_parser.add_argument('owner', help='id of the owner of the patch set')
    owner_parser.add_argument('--patchsets', choices=('all', 'last'),
                              default='last', help='Whether to show all the '
                              'patch sets for a change.')
    owner_parser.add_argument(
        '--status', choices=('open', 'reviewed', 'submitted', 'merged',
        'closed', 'abandoned'), default='open', help='The state of the change')
    owner_parser.add_argument('--since', help='Human max age of the patch '
                              'set, e.g. 1week,2days')

    rev_parser = subparsers.add_parser('reviewer')
    rev_parser.add_argument('reviewer', help='id of the reviewer of the patch '
                            'set')
    rev_parser.add_argument('--patchsets', choices=('all', 'last'),
                            default='last', help='Whether to show all the '
                            'patch sets for a change.')
    rev_parser.add_argument(
        '--status', choices=('open', 'reviewed', 'submitted', 'merged',
        'closed', 'abandoned'), default='open', help='The state of the change')
    rev_parser.add_argument('--reviewed', help='Filter results by reviews '
                            'done by id.')
    rev_parser.add_argument('--verified', help='Filter results by '
                            'verifications done by id.')
    rev_parser.add_argument('--since', help='Human max age of the patch '
                            'set, e.g. 1week,2days')

    args = parser.parse_args()
    action = args.action
    delattr(args, 'action')
    if action == 'owner':
        owner(**vars(args))
    elif action == 'reviewer':
        reviewer(**vars(args))
