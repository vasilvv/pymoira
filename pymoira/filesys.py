#
## PyMoira client library
##
## This file contains the more abstract methods which allow user to work with
## lists and list members.
#

import protocol
import utils
import datetime
from errors import *

class Filesys(object):
    info_query_description = (
        ('label', str),
        ('type', str),
        ('machine', str),
        ('name', str),
        ('mountpoint', str),
        ('access_mode', str),
        ('description', str),
        ('owner_user', str),
        ('owner_group', str),
        ('create', bool),
        ('locker_type', str),
        ('lastmod_datetime', datetime.datetime),
        ('lastmod_by', str),
        ('lastmod_with', str),
    )

    def __init__(self, client, name):
        self.client = client
        self.name = name

    def loadInfo(self):
        """Loads the information about the list from the server into the object."""
        
        response, = self.client.query( 'get_filesys_by_label', (self.name, ), version = 14 )
        result = utils.responseToDict(self.info_query_description, response)
        self.__dict__.update(result)
