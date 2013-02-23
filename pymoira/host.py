#
## PyMoira client library
##
## This file contains the classes which aid in dealing with Moira hosts.
#

from .lists import ListMember
import socket

class Host(ListMember):
    def __init__(self, client, name, canonicalize = True):
        name = name.upper()
        if '.MIT.EDU' not in name:
            name += '.MIT.EDU'

        super(Host, self).__init__(client, ListMember.Machine, name)
        if canonicalize:
            self.canonicalize()
    
    def canonicalize(self):
        """Replaces the alias form of the host with the proper name."""

        self.name = socket.getfqdn(self.name)

