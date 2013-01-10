#
## PyMoira client library
##
## This file contains the more abstract methods which allow user to work with
## lists and list members.
#

import protocol
import moira_constants
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
		"""Constructs the relevant Moira list member object out of a type-name tuple"""
		
		if len(member) != 2:
			raise MoiraUserError("Moira list member tuple must has a type-name format")
		
		mtype, name = member
		if mtype == MoiraListMember.List:
			return MoiraList(client, name)
		
		return MoiraListMember(client, mtype, name)
	
	def toTuple(self):
		return (self.mtype, self.name)
	
	def __repr__(self):
		return "%s:%s" % self.toTuple()
	
	def __hash__(self):
		return self.__repr__().__hash__()
	
	def __eq__(self, other):
		return self.mtype == other.mtype and self.name == other.name

class MoiraList(MoiraListMember):
	def __init__(self, client, listname):
		# FIXME: name validation should go here
		
		super(MoiraList, self).__init__( client, MoiraListMember.List, listname )
	
	def getExplicitMembers(self, query_name = "get_members_of_list"):
		"""Returns all the members of the list which are included into it explicitly,
		that is, not by other lists."""
		
		response = self.client.query( query_name, (self.name,), version = 14 )
		result = []
		for member in response:
			result.append( MoiraListMember.fromTuple(self.client, member) )
		
		return frozenset(result)

	def getAllMembers(self, server_side = False, include_lists = False):
		"""Performs a recursive expansion of the given list. This may be done both on the side of the client
		and on the side of the server. In the latter case, the server does not communicate the list of the nested
		lists to which user does not have access, so only the resulting list of members is returned. In case of the client-side
		expansion however, it causes the method to return the (members, inaccessible_lists, lists) tuple instead of just the member list.
		The inaccessible_lists is a set of lists to which the access was denied, and ."""
		
		if server_side:
			members = self.getExplicitMembers(query_name = "get_end_members_of_list")
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
			members = self.getExplicitMembers()
			
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
