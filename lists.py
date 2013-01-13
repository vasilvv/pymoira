#
## PyMoira client library
##
## This file contains the more abstract methods which allow user to work with
## lists and list members.
#

import protocol
import moira_constants
import utils
import datetime
from errors import *

class MoiraListMember(object):
	User = 'USER'
	Kerberos = 'KERBEROS'
	List = 'LIST'
	String = 'STRING'
	Machine = 'MACHINE'
	
	types = (User, Kerberos, List, String, Machine)
	
	def __init__(self, client, mtype, name):
		if mtype not in self.types:
			raise MoiraUserError("Invalid list member type specified: %s" % mtype)
		
		self.client = client
		self.mtype = mtype
		self.name = name
	
	@staticmethod
	def fromTuple(client, member):
		"""Constructs the relevant Moira list member object out of a type-name[-tag] tuple"""
		
		if len(member) not in {2, 3}:
			raise MoiraUserError("Moira list member tuple must has a type-name[-tag] format")
		
		mtype, name = member[0:2]
		
		if mtype == MoiraListMember.List:
			result = MoiraList(client, name)
		else:
			result = MoiraListMember(client, mtype, name)
		
		if len(member) > 2:
			result.tag = member[2]
		
		return result
	
	def toTuple(self):
		if hasattr(self, 'tag'):
			return (self.mtype, self.name, self.tag)
		else:
			return (self.mtype, self.name)
	
	def __repr__(self):
		return "%s:%s" % self.toTuple()[0:2]
	
	def __hash__(self):
		return self.__repr__().__hash__()
	
	def __eq__(self, other):
		return self.mtype == other.mtype and self.name == other.name
	
	def getMemberships(self, recursive = False):
		"""Returns the list of lists on which this member is on. If recursive is set to true,
		this means that all lists will be returned, otherwise only lists on which member is explicitly
		on will be returned."""
		
		mtype = ('R' if recursive else '') + self.mtype
		
		response = self.client.query( 'get_lists_of_member', (mtype, self.name), version = 14 )
		result = []
		for entry in response:
			name, active, public, hidden, is_mailing, is_afsgroup = entry
			list_obj = MoiraList(self.client, name)
			list_obj.active = active
			list_obj.hidden = hidden
			list_obj.is_mailing = is_mailing
			list_obj.is_afsgroup = is_afsgroup
			result.append(list_obj)
		
		return frozenset(result)
		

class MoiraList(MoiraListMember):
	def __init__(self, client, listname):
		# FIXME: name validation should go here
		
		super(MoiraList, self).__init__( client, MoiraListMember.List, listname )
	
	def getMembersViaQuery(self, query_name):
		"""Returns all the members of the list which are included into it explicitly,
		that is, not by other lists."""
		
		response = self.client.query( query_name, (self.name,), version = 14 )
		result = []
		for member in response:
			result.append( MoiraListMember.fromTuple(self.client, member) )
		
		return frozenset(result)

	def getExplicitMembers(self, tags = False):
		query_name = "get_tagged_members_of_list" if tags else "get_members_of_list"
		return self.getMembersViaQuery(query_name)

	def getAllMembers(self, server_side = False, include_lists = False, tags = False):
		"""Performs a recursive expansion of the given list. This may be done both on the side of the client
		and on the side of the server. In the latter case, the server does not communicate the list of the nested
		lists to which user does not have access, so only the resulting list of members is returned. In case of the client-side
		expansion however, it causes the method to return the (members, inaccessible_lists, lists) tuple instead of just the member list.
		The inaccessible_lists is a set of lists to which the access was denied, and the lists is the dictionary with the memers of all
		lists encountered during the expansion process."""
		
		if server_side:
			if tags:
				raise MoiraUserError("Server-side expansion does not support member tag retrieval")
			
			members = self.getMembersViaQuery("get_end_members_of_list")
			if include_lists:
				return members
			else:
				return frozenset( filter(lambda m: type(m) != MoiraList, members) )

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
					raise MoiraUserError("List expansion depth limit exceeded")
				
				to_expand = {member.name for member in members if type(member) == MoiraList} - set(known)
				for sublist_name in to_expand:
					try:
						new_members = MoiraList(self.client, sublist_name).getExplicitMembers()
					except MoiraError as err:
						if err.code == moira_constants.MR_PERM:
							denied.add(sublist_name)
							known[sublist_name] = None
							continue
						else:
							raise err
							
					known[sublist_name] = new_members
					members |= new_members
			
			if not include_lists:
				members = filter( lambda m: type(m) != MoiraList, members )
			
			return (members, denied, known)
	
	def loadInfo(self):
		"""Loads the information about the list from the server into the object."""
		
		query_description = (
			('name', str),
			('active', bool),
			('public', bool),
			('hidden', bool),
			('is_mailing', bool),
			('is_afsgroup', bool),
			('gid', int),
			('is_nfsserver', bool),
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
		
		response, = self.client.query( 'get_list_info', (self.name, ), version = 14 )
		result = utils.responseToDict(query_description, response)
		self.__dict__.update(result)
	
	def countMembers(self):
		"""Returns the amount of explicit members of the list."""
		
		return int( self.client.query( 'count_members_of_list', (self.name, ), version = 14 )[0][0] )
	
	def addMember(self, member, tag = None):
		"""Adds a member into the list."""
		
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

class MoiraListTracer(object):
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
		for listname, members in self.lists.iteritems():
			if not members:
				continue

			for member in members:
				if member not in result:
					result[member] = []
				result[member].append(listname)
		
		self.inverse = result
		self.inverseLists = { member.name : contents for member, contents in self.inverse.iteritems() if type(member) == MoiraList }
	
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
				raise MoiraUserError("Maximum number (%s) of possible inclusion pathways reached" % self.max_pathways)
			output.append( newway[::-1] )
			return
		
		for listname in self.inverseLists[curlist]:
			# Protect ourselves from recursions
			if listname in newway:
				continue
			
			self.recursiveTrace(member, listname, newway, output)
