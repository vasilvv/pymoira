#
## PyMoira client library
##
## This file contains the more abstract methods which allow user to work with
## lists and list members.
#

from . import protocol
from . import constants
from . import utils
from . import stubs
import datetime
import re
from .errors import *
from .filesys import Filesys

class ListMember(object):
    User = 'USER'
    Kerberos = 'KERBEROS'
    List = 'LIST'
    String = 'STRING'
    Machine = 'MACHINE'
    No = 'NONE'
    
    types = (User, Kerberos, List, String, Machine, No)
    
    def __init__(self, client, mtype, name):
        if mtype not in self.types:
            raise UserError("Invalid list member type specified: %s" % mtype)
        
        self.client = client
        self.mtype = mtype.upper()
        self.name = name

    @staticmethod
    def create(client, mtype, name):
        """Constructs the specific object for a given list member type."""

        # Types are imported here in order to avoid circular dependencies
        if mtype == ListMember.List:
            return List(client, name)
        elif mtype == ListMember.User:
            from .user import User
            return User(client, name)
        elif mtype == ListMember.Machine:
            from .host import Host
            return Host(client, name, canonicalize = False)
        else:
            return ListMember(client, mtype, name)

    @staticmethod
    def fromTuple(client, member):
        """Constructs the relevant Moira list member object out of a type-name[-tag] tuple"""
        
        if len(member) not in {2, 3}:
            raise UserError("Moira list member tuple must has a type-name[-tag] format")
        
        mtype, name = member[0:2]
        
        result = ListMember.create(client, mtype, name)

        if len(member) > 2:
            result.tag = member[2]
        
        return result
    
    def toTuple(self):
        if hasattr(self, 'tag'):
            return (self.mtype, self.name, self.tag)
        else:
            return (self.mtype, self.name)
    
    def __str__(self):
        types = {
            'USER' : 'user',
            'LIST' : 'list',
            'KERBEROS' : 'Kerberos principal',
            'STRING' : 'string/email address',
            'MACHINE' : 'machine',
            'NONE' : '(none)',
        }
        return "%s %s" % (types[self.mtype], self.name)
    
    def __repr__(self):
        return "%s:%s" % self.toTuple()[0:2]
    
    def __hash__(self):
        return self.__repr__().__hash__()
    
    def __eq__(self, other):
        return self.mtype == other.mtype and self.name == other.name
    
    def __cmp__(self, other):
        if self.mtype == other.mtype:
            return cmp(self.name, other.name)
        else:
            return cmp(self.mtype, other.mtype)
    
    def getMemberships(self, recursive = False):
        """Returns the list of lists on which this member is on. If recursive is set to true,
        this means that all lists will be returned, otherwise only lists on which member is explicitly
        on will be returned."""
        
        mtype = ('R' if recursive else '') + self.mtype
        
        response = self.client.query( 'get_lists_of_member', (mtype, self.name), version = 14 )
        result = []
        for entry in response:
            name, active, public, hidden, is_mailing, is_afsgroup = entry
            list_obj = List(self.client, name)
            list_obj.active = active
            list_obj.hidden = hidden
            list_obj.is_mailing = is_mailing
            list_obj.is_afsgroup = is_afsgroup
            result.append(list_obj)
        
        return frozenset(result)
    
    def exists(self):
        # FIXME: this should be seperated into subclasses when they all exist
        if self.mtype == self.User:
            error_code = self.client.probe( 'get_user_account_by_login', (self.name,), version = 14 )
            return error_code != constants.MR_NO_MATCH
        if self.mtype == self.List:
            error_code = self.client.probe( 'get_list_info', (self.name,), version = 14 )
            return error_code != constants.MR_NO_MATCH
        if self.mtype == self.String:
            return True
        return True # FIXME
    
    @staticmethod
    def resolveName(client, name):
        """For a given name, attempts to determine the list member it suits.
        Currently it recognizes user names, list names and Athena Kerberos
        principals. Returns None if unable to determine."""
        
        match = re.match( "^(list|user|kerberos|string|machine):(.+)$", name, re.IGNORECASE )
        if match:
            mlist, name = match.groups()
            return ListMember(client, mlist.upper(), name)
        
        if re.match( "^[a-z0-9_]{3,8}$", name ):
            attempt = ListMember(client, ListMember.User, name)
            if attempt.exists():
                return attempt
        
        if re.match( "^[^A-Z@:]+$", name ):
            attempt = List(client, name)
            if attempt.exists():
                return attempt
        
        if re.match( "^[a-z0-9_]{3,8}/[a-z0-9_]+$", name):
            return ListMember(client, ListMember.Kerberos, "%s@ATHENA.MIT.EDU" % name)

        # Yes, valid email address may actually contain "/", I know about it.
        # However, if do this, you already probably break a lot of things,
        # and Moira will not allow that as a string entry anyways.
        match = re.match( r"^([a-z0-9_]+/[a-z0-9_]+)@([a-z0-9.\-]+)$", name, re.IGNORECASE)
        if match:
            principal, hostname = match.groups()
            return ListMember(client, ListMember.Kerberos, "%s@%s" % (principal, hostname.upper()))
        
        # FIXME: host support should be here
        
        return None

# Users and lists are only object capable of owning other objects
class Owner(ListMember):
    """This class provides a getOwnedObjects() method which allows to determine which
    objects are owned by this object."""

    # Currently known ownable objects:
    # CONTAINER
    # CONTAINER-MEMACL
    # FILESYS
    # LIST
    # MACHINE
    # QUERY
    # QUOTA (alleged by source, was not able to find in real life)
    # SERVICE (alleged by source)
    # ZEPHYR

    def getOwnedObjects(self, recursive = False):
        """Return all the objects owned by this owner."""

        owner_type = ('R' + self.mtype) if recursive else self.mtype

        response = self.client.query( 'get_ace_use', (owner_type, self.name), version = 14 )

        result = []
        for mtype, name in response:
            if mtype == 'CONTAINER':
                m = stubs.Container()
                m.name = name
                result.append(m)
            if mtype == 'CONTAINER-MEMACL':
                m = stubs.ContainerMembershipACL()
                m.name = name
                result.append(m)
            if mtype == 'FILESYS':
                result.append( Filesys(self.client, name) )
            if mtype == 'LIST':
                result.append( List(self.client, name) )
            if mtype == 'MACHINE':
                from .host import Host
                result.append( Host(self.client, name, canonicalize = False) )
            if mtype == 'QUERY':
                m = stubs.Query()
                m.name = name
                result.append(m)
            if mtype == 'QUOTA':
                m = stubs.Quota()
                m.name = name
                result.append(m)
            if mtype == 'SERVICE':
                m = stubs.Service()
                m.name = name
                result.append(m)
            if mtype == 'ZEPHYR':
                m = stubs.ZephyrClass()
                m.name = name
                result.append(m)

        return result

class List(Owner):
    info_query_description = (
        ('name', str),
        ('active', bool),
        ('public', bool),
        ('hidden', bool),
        ('is_mailing', bool),
        ('is_afsgroup', bool),
        ('gid', int),
        ('is_nfsgroup', bool),
        ('is_mailman_list', bool),
        ('mailman_server', str),
        ('owner_type', str),
        ('owner_name', str),
        ('memacl_type', str),
        ('memacl_name', str),
        ('description', str),
        ('lastmod_datetime', datetime.datetime),
        ('lastmod_by', str),
        ('lastmod_with', str),
    )

    def __init__(self, client, listname):
        # FIXME: name validation should go here
        
        try:
            listname.decode('ascii')
            super(List, self).__init__( client, ListMember.List, listname )
        except UnicodeDecodeError:
            idn = listname.decode('utf-8').encode('idna')
            super(List, self).__init__( client, ListMember.List, idn )
    
    def getMembersViaQuery(self, query_name):
        """Returns all the members of the list which are included into it explicitly,
        that is, not by other lists."""
        
        response = self.client.query( query_name, (self.name,), version = 14 )
        result = []
        for member in response:
            result.append( ListMember.fromTuple(self.client, member) )
        
        return frozenset(result)

    def getExplicitMembers(self, tags = False):
        query_name = "get_tagged_members_of_list" if tags else "get_members_of_list"
        return self.getMembersViaQuery(query_name)

    def getAllMembers(self, server_side = False, include_lists = False, tags = False):
        """Performs a recursive expansion of the given list. This may be done both
        on the side of the client and on the side of the server. In the latter case,
        the server does not communicate the list of the nested lists to which user
        does not have access, so only the resulting list of members is returned.
        In case of the client-side expansion however, it causes the method to return
        the (members, inaccessible_lists, lists) tuple instead of just the member list.
        The inaccessible_lists is a set of lists to which the access was denied, and
        the lists is the dictionary with the memers of all lists encountered during
        the expansion process."""
        
        if server_side:
            if tags:
                raise UserError("Server-side expansion does not support member tag retrieval")
            
            members = self.getMembersViaQuery("get_end_members_of_list")
            if include_lists:
                return members
            else:
                return frozenset( [m for m in members if type(m) != List] )

        else:
            # Already expanded lists
            known = {}
            denied = set()
            
            # We need seperate handling for the first list, because if access to it is denied,
            # we are supposed to return the error message
            members = self.getExplicitMembers(tags = tags)
            known[self.name] = members
            
            to_expand = True
            current_depth = 0
            max_depth = protocol.MOIRA_MAX_LIST_DEPTH
            while to_expand:
                current_depth += 1
                if current_depth > max_depth:
                    raise UserError("List expansion depth limit exceeded")
                
                to_expand = {member.name for member in members if type(member) == List} - set(known)
                for sublist_name in to_expand:
                    try:
                        new_members = List(self.client, sublist_name).getExplicitMembers()
                    except MoiraError as err:
                        if err.code == constants.MR_PERM:
                            denied.add(sublist_name)
                            known[sublist_name] = None
                            continue
                        else:
                            raise err
                            
                    known[sublist_name] = new_members
                    members |= new_members
            
            if not include_lists:
                members = [m for m in members if type(m) != List]
            
            return (members, denied, known)
    
    def loadInfo(self):
        """Loads the information about the list from the server into the object."""
        
        response, = self.client.query( 'get_list_info', (self.name, ), version = 14 )
        result = utils.responseToDict(self.info_query_description, response)
        self.__dict__.update(result)
        self.owner  = ListMember.create( self.client, self.owner_type, self.owner_name )
        self.memacl = ListMember.create( self.client, self.memacl_type, self.memacl_name ) if self.memacl_type != 'NONE' else None
    
    def updateParams(self, **updates):
        """Updates a certain parameter in user information."""

        fields = [name for name, mtype in self.info_query_description]
        fields = fields[:-3]
        if not all(field in fields for field in updates):
            raise UserError('Invalid list parameter specified')

        args, = self.client.query( 'get_list_info', (self.name, ), version = 14 )
        args = list(args)[:-3]
        for field, value in updates.items():
            args[fields.index(field)] = utils.convertToMoiraValue(value)

        self.client.query( 'update_list', [self.name] + args, version = 14 )

    def countMembers(self):
        """Returns the amount of explicit members of the list."""
        
        return int( self.client.query( 'count_members_of_list', (self.name, ), version = 14 )[0][0] )
    
    def addMember(self, member, tag = None):
        """Adds a member into the list."""

        if not tag and hasattr(member, 'tag'):
            tag = member.tab
        
        if tag:
            self.client.query( 'add_tagged_member_to_list', (self.name, member.mtype, member.name, tag), version = 14 )
        else:
            self.client.query( 'add_member_to_list', (self.name, member.mtype, member.name), version = 14 )
    
    def removeMember(self, member):
        """Removes a member from the list."""
        
        self.client.query( 'delete_member_from_list', (self.name, member.mtype, member.name), version = 14 )
    
    def tagMember(self, member, tag):
        """Sets a tag on the member of the list."""
        
        self.client.query( 'tag_member_of_list', (self.name, member.mtype, member.name, tag), version = 14 )
    
    def untagMember(self, member):
        """Removes the tag from the member of the list."""
        
        self.tagMember(member, "")
    
    def rename(self, new_name):
        """Changes the name of the list."""

        self.updateParams(name = new_name)

    def setActiveFlag(self, new_value):
        """Marks the list as either active or inactive."""

        self.updateParams(active = new_value)
    
    def setPublicFlag(self, new_value):
        """Marks the list as either public or private. Public lists are lists
        on which users are able to add or remove themselves without being on ACL."""

        self.updateParams(public = new_value)
    
    def setHiddenFlag(self, new_value):
        """Marks the list as either visible or hidden. If a list is hidden,
        it is harder to get information about this list or even to find that it exists."""

        self.updateParams(hidden = new_value)
    
    def setMailingListFlag(self, new_value):
        """Marks the list as a mailing list."""

        self.updateParams(is_mailing = new_value)
    
    def setAFSGroupFlag(self, new_value):
        """Mark the list as an AFS group."""

        self.updateParams(is_afsgroup = new_value)
    
    def setNFSGroupFlag(self, new_value):
        """Mark the list as an NFS group. NFS groups are exposed as Unix groups
        through Hesiod. Note that currently, due to the issues with Hesiod, if
        user is on too many NFS groups, the group list is truncated."""

        self.updateParams(is_nfsgroup = new_value)

    def setOwner(self, new_owner):
        """Change the owner of the list."""

        self.updateParams(owner_type = new_owner.mtype, owner_name = new_owner.name)

    def setMembershipACL(self, new_memacl):
        """Set the membership ACL of the list. Membership ACL is able to add members
        to the list or remove them from it, but cannot change other properties.
        It may be set to None."""

        if new_memacl:
            self.updateParams(memacl_type = new_memacl.mtype, memacl_name = new_memacl.name)
        else:
            self.updateParams(memacl_type = 'NONE', memacl_name = 'NONE')
    
    def setDescription(self, new_value):
        """Updates the description of the list."""

        self.updateParams(description = new_value)

    def serialize(self):
        """Stores all list settings inside a dictionary, which may then
        be stored in JSON or other machine-readable format and reset from it."""

        self.loadInfo()
        members = self.getExplicitMembers(tags = True)
        result = {}
        for field, field_type in self.info_query_description:
            result[field] = getattr(self, field)

            # datetime is not serialized by JSON and other modules
            if field_type == datetime.datetime:
                result[field] = str(result[field])

        result['members'] = [member.toTuple() for member in members]
        return result

class ListTracer(object):
    """A class which for a given list allows to determine why the certain member is on that list.
    When you initialize it, it does the recursive expansion of the list on the client side,
    and then you may ask the class for the inclusion paths for different members."""
    
    def __init__(self, mlist, tags = False, max_pathways = 65536):
        self.mlist = mlist
        self.members, self.inaccessible, self.lists = mlist.getAllMembers(include_lists = True, tags = tags)
        self.max_pathways = max_pathways
        self.createInverseMap()
    
    def createInverseMap(self):
        """Creates the [member -> lists on which it is explicitly on] dictionary."""
        
        result = {}
        for listname, members in self.lists.items():
            if not members:
                continue

            for member in members:
                if member not in result:
                    result[member] = []
                result[member].append(listname)
        
        self.inverse = result
        self.inverseLists = { member.name : contents for member, contents in self.inverse.items() if type(member) == List }
    
    def trace(self, member):
        """Returns the pathways by which user is included into a list. The pathways
        are tuples in which the first element is the root list and the last one is
        the list into which the member is actually included."""
        
        if member not in self.inverse:
            return []
        
        pathways = []
        for mlist in self.inverse[member]:
            self.recursiveTrace(member, mlist, tuple(), pathways)
        return pathways
        
    def recursiveTrace(self, member, curlist, curway, output):
        newway = curway + (curlist,)
        if curlist == self.mlist.name:
            if len(output) == self.max_pathways:
                raise UserError("Maximum number (%s) of possible inclusion pathways reached" % self.max_pathways)
            output.append( newway[::-1] )
            return
        
        for listname in self.inverseLists[curlist]:
            # Protect ourselves from recursions
            if listname in newway:
                continue
            
            self.recursiveTrace(member, listname, newway, output)
