#!/usr/bin/env python
# -*- coding: utf-8 -*-
from datetime import datetime
import json
import subprocess
import sys

def query(gerritURL, query):
    cmd = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '\
          '-p 29418 %s gerrit query --format=JSON --all-approvals %s' % (gerritURL, query)
    with open('/dev/null', 'w') as NULLOUT:
        output = subprocess.check_output(cmd.split(' '), stderr=NULLOUT.fileno())
        for line in output.split('\n'):
            if line:
                yield json.loads(line)

class Change(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            if key == 'owner':
                value = Owner(**value)
            elif key == 'patchSets':
                value = [PatchSet(**patchset) for patchset in value]
            setattr(self, key, value)

    def __str__(self):
        return self.subject

    def __repr__(self):
        return '(%s)%s: %s - %r' % (self.project, self.id[:6], self.subject, self.owner)

class Owner(object):
    cache = set()

    @classmethod
    def __get_cached(cls, name, email):
        for obj in cls.cache:
            if obj.name == name and obj.email == email:
                return obj
        return None

    def __new__(cls, name, email=None):
        cached = cls.__get_cached(name, email)
        if cached:
            return cached
        return super(Owner, cls).__new__(cls)

    def __init__(self, name, email=None):
        if self in self.cache:
            return
        self.name = name
        self.email = email
        self.cache.add(self)

    def __str__(self):
        if self.email:
            return self.email[:self.email.index('@')]
        return self.name

    def __repr__(self):
        return '%s<%s>' % (self.name, self.email)

class PatchSet(object):
    def __init__(self, number, revision, ref, uploader, createdOn=None,
                 approvals=None):
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

    def __str__(self):
        r, v = self.score()
        return '%s(r: %s, v: %s)' % (self.number, r, v)

    def __repr__(self):
        r, v = self.score()
        return '%s(r: %s, v: %s - %r)' % (self.number, r, v, self.approvals)

    def score(self):
        r = 0
        v = 0
        for approval in self.approvals:
            if approval.type == 'v':
                v += approval.value
            else:
                r += approval.value
        return (r, v)

class Approval(object):
    def __init__(self, type, description, value, grantedOn, by):
        self.type = 'v' if type == 'VRIF' else 'r'
        self.description = description
        self.value = int(value)
        self.grantedOn = datetime.fromtimestamp(grantedOn)
        self.by = Owner(**by)

    def __repr__(self):
        return '%s(%s:%s)' % (self.by, self.type, self.value)

def changesOf(owner):
    output = query('gerrit.ovirt.org', 'status:open owner:%s' % owner)
    information = [info for info in output]
    queryInfo = information.pop()
    changes = [Change(**change) for change in information]
    changes = sorted(changes, key=lambda change: change.lastUpdated)
    print u'Results: %s(time: %sµs)' % (queryInfo['rowCount'],
                                     queryInfo['runTimeMilliseconds'])
    print '=================================================================='\
          '==============\n'
    for change in changes:
        print '%r' % change
        for patchSet in change.patchSets:
            print '\t%r' % patchSet
        print '\n'

def awaitingReview(reviewer, reviewed=True):
    output = query('gerrit.ovirt.org', 'status:open reviewer:%s' % reviewer)
    information = [info for info in output]
    queryInfo = information.pop()
    changes = [Change(**change) for change in information]
    changes = sorted(changes, key=lambda change: change.lastUpdated)
    print u'Results: %s(time: %sµs)' % (queryInfo['rowCount'],
                                     queryInfo['runTimeMilliseconds'])
    print '=================================================================='\
          '==============\n'
    for change in changes:
        if not change.patchSets[-1].approvals:
            print '%r' % change
            for patchSet in change.patchSets:
                print '\t%r' % patchSet
            print '\n'


if __name__ == '__main__':
    #changesOf(sys.argv[1])
    awaitingReview(sys.argv[1])
