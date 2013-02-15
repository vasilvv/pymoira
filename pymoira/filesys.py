#
## PyMoira client library
##
## This file contains the more abstract methods which allow user to work with
## lists and list members.
#

import protocol
import constants
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
    quota_query_description = (
        ('filesys', str),
        ('type', str),
        ('name', str),
        ('size', int),
        ('dir', str),
        ('machine', str),
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

        try:
            self.loadQuota()
        except MoiraError as err:
            if err.code == constants.MR_NO_MATCH:
                self.quota = None
            else:
                raise err

    def loadQuota(self):
        """Loads the information about the quota on the filesystem."""

        response, = self.client.query( 'get_quota_by_filesys', (self.label, ), version = 14 )
        result = utils.responseToDict(self.quota_query_description, response)
        self.quota, self.quota_lastmod_datetime, self.quota_lastmod_by, self.quota_lastmod_with = result['size'], result['lastmod_datetime'], result['lastmod_by'], result['lastmod_with']
