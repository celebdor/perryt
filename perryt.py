#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
import json
import subprocess
import sys


def query(gerritURL, query):
    cmd = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '\
          '-p 29418 %s gerrit query --format=JSON --all-approvals --comments '\
          '--dependencies %s' % (gerritURL, query)
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
        identifiers.append(parts[0]+parts[-1])
        identifiers.append(parts[0][0]+parts[-1])
        identifiers.append(parts[0]+''.join(part[0] for part in parts[1:]))
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
        self.reviewer = Owner(**reviewer)
        self.line = int(line)
        self.message = message
        self.file = file

    def __repr__(self):
        if len(self.message) < 40:
            summary = self.message
        else:
            summary = self.message[:37] + '...'
        return '%s:%s: %s - %s' % (self.file, self.line, summary,
                                   self.reviewer)

def owner(owner, patchsets=None, status=None):
    if status is None:
        status = 'status:open'
    else:
        status = 'status:%s' % status
    output = query('gerrit.ovirt.org', '%s owner:%s' % (status, owner))
    information = [info for info in output]
    queryInfo = information.pop()
    changes = [Change(**change) for change in information]
    changes = sorted(changes, key=lambda change: change.lastUpdated)
    print 'Results: %s(time: %sµs)' % (queryInfo['rowCount'],
                                     queryInfo['runTimeMilliseconds'])
    print '=================================================================='\
          '==============\n'
    for change in changes:
        print '%r' % change
        print '\t%s' % change.url
        if patchsets == 'all':
            for patchSet in change.patchSets:
                print '\t%r' % patchSet
        else:
            print '\t%r' % change.patchSets[-1]
        print '\n'


def reviewer(reviewer, patchsets=None, reviewed=None, verified=None,
             status=None):
    if status is None:
        status = 'status:open'
    else:
        status = 'status:%s' % status
    output = query('gerrit.ovirt.org', '%s reviewer:%s' % (status, reviewer))
    information = [info for info in output]
    queryInfo = information.pop()
    changes = [Change(**change) for change in information]
    changes = sorted(changes, key=lambda change: change.lastUpdated)
    print 'Results: %s(time: %sµs)' % (queryInfo['rowCount'],
                                     queryInfo['runTimeMilliseconds'])
    print '=================================================================='\
          '==============\n'
    for change in changes:
        if patchsets == 'last':
            patchSets = [change.patchSets[-1]]
        else:
            patchSets = change.patchSets
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


def parseArgs(args):
    return dict(args[i:i+2] for i in range(0, len(args)-1, 2))


if __name__ == '__main__':
    if len(sys.argv) % 2 == 0:
        print 'wrong usage'
        sys.exit(1)
    else:
        opts = parseArgs(sys.argv[1:])
    if opts.get('owner'):
        owner(**opts)
    elif opts.get('reviewer'):
        reviewer(**opts)
