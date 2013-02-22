#
## PyMoira client library
##
## This file contains the more abstract methods which allow user to work with
## users.
#

import protocol
import constants
import utils
import datetime
from lists import ListMember
from errors import *

class User(ListMember):
    Registerable = 0
    Active = 1
    HalfRegistered = 2
    Deleted = 3
    NotRegisterable = 4
    Enrolled_Registerable = 5
    Enrolled_NonRegisterable = 6
    HalfEnrolled = 7
    Registerable_KerberosOnly = 8
    Active_KerberosOnly = 9
    Suspended = 10

    info_query_description = (
        ('name', str),
        ('uid', int),
        ('shell', str),
        ('windows_shell', str),
        ('last_name', str),
        ('first_name', str),
        ('middle_name', str),
        ('status', int),
        ('mit_id', str),
        ('user_class', str),
        ('comments', str),
        ('signature', str), # have to be always empty
        ('secure', bool),
        ('windows_home_dir', str),
        ('windows_profile_dir', str),
        ('sponsor_name', str),
        ('sponsor_type', str),
        ('expiration', str),
        ('alternate_email', str),
        ('alternate_phone', str),
        ('lastmod_datetime', datetime.datetime),
        ('lastmod_by', str),
        ('lastmod_with', str),
        ('created_date', datetime.datetime),
        ('created_by', str),
    )

    def __init__(self, client, username):
        super(User, self).__init__(client, ListMember.User, username)
    
    def loadInfo(self):
        """Loads the information about the list from the server into the object."""
        
        response, = self.client.query( 'get_user_account_by_login', (self.name, ), version = 14 )
        result = utils.responseToDict(self.info_query_description, response)
        self.__dict__.update(result)

        if self.sponsor_type != 'NONE':
            self.sponsor = ListMember.create(self.client, self.sponsor_type, self.sponsor_name)
        else:
            self.sponsor = None

