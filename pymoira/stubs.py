#
## PyMoira client library
##
## This file contains the StubCommons which are not yet implemented in the system,
## but still have to be represented in the system. All have 'name' property.
#

class StubCommon(object):
    stub_type_title = '???'

    def __repr__(self):
        '%s %s' % (self.stub_type_title, self.name)

    def __cmp__(self, other):
        return cmp(self.name, other.name)

class Container(StubCommon):
    stub_type_title = 'Container'

    pass

class ContainerMembershipACL(StubCommon):
    stub_type_title = 'Container membership ACL'

    pass

class Query(StubCommon):
    stub_type_title = 'Query'

    pass

class Quota(StubCommon):
    stub_type_title = 'Quota'

    pass

class Service(StubCommon):
    stub_type_title = 'Service'

    pass

class ZephyrClass(StubCommon):
    stub_type_title = 'Zephyr class'

    pass

