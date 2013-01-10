#
## PyMoira client library
##
## This file contains the Moira client and most generic operations (authentication,
## server location, etc).
#

import socket

from protocol import *
from protocol import _read_u32

from moira_constants import *

def locate_server():
	"""Locates the Moira server through Hesiod."""
	# FIXTHEM: some fine day Moira should start using real SRV records instead

	import random, hesiod
	
	lookup = hesiod.Lookup("moira", "sloc")
	if not lookup or not lookup.results:
		raise MoiraConnectionError("Unable to locate Moira server through Hesiod")
	return random.choice(lookup.results)

def _get_krb5_ap_req(service, server):
	"""Returns the AP_REQ Kerberos 5 ticket for a given service."""

	import kerberos, base64
	status_code, context = kerberos.authGSSClientInit( 'moira@%s' % server )
	kerberos.authGSSClientStep(context, "")
	token_gssapi = base64.b64decode( kerberos.authGSSClientResponse(context) )

	# The following code "parses" GSSAPI token as described in RFC 2743 and RFC 4121.
	# "Parsing" in this context means throwing out the GSSAPI header correctly
	# while doing some very basic validation of its contents.
	# 
	# This code is here because Python's interface provides only GSSAPI interface,
	# and Moira does not use GSSAPI.
	# (FIXTHEM: it should)
	# 
	# FIXME: this probably should either parse tokens properly or use another
	# Kerberos bindings for Python.
	
	body_start = token_gssapi.find( chr(0x01) + chr(0x00) )	# 01 00 indicates that this is AP_REQ
	if token_gssapi[0] != chr(0x60) or \
	   not (token_gssapi[2] == chr(0x06) or token_gssapi[4] == chr(0x06)) or \
	   body_start == -1 or body_start < 8 or body_start > 64:
		   raise MoiraConnectionError("Invalid GSSAPI token provided by Python's Kerberos API")

	body = token_gssapi[body_start + 2:]	
	return body

class MoiraClient(object):
	"""The connection class for Moira. Allows querying, authentication and other
	protocol-supported operations. Provides the foundation for building higher-level
	abstractions."""
	
	def __init__(self, server = None, timeout = None, default_version = None):
		if not server:
			server = locate_server()
		if not default_version:
			default_version = MOIRA_QUERY_VERSION
		
		self.server = socket.getfqdn(server)
		self.socket = socket.create_connection( (server, MOIRA_PORT), timeout )
		self.challenge()
		self.checkMOTD()
		
		self.version = None
		self.setVersion(default_version)
	
	def challenge(self):
		"""Performs an initial challenge-response exchange at the beginning of the connection."""
		
		self.socket.send(MOIRA_PROTOCOL_CHALLENGE)
		response = self.socket.recv( len(MOIRA_PROTOCOL_RESPONSE) )
		if response != MOIRA_PROTOCOL_RESPONSE:
			raise MoiraConnectionError("Moira server failed to return the correct response to connection initiation request")
	
	def send(self, data):
		"""A blocking method to send data to Moira using appropriate connection interface."""
		
		self.socket.send(data)
	
	def recv(self, buffer_size, exact = True):
		"""A blocking method to send data to Moira using appropriate connection interface. If exact
		flag is specified, the client waits until exactly buffer_size bytes are received and raises
		an error if connection is aborted before."""
		
		if exact:
			data = ""
			while len(data) < buffer_size:
				new_data = self.socket.recv(buffer_size - len(data))
				if len(new_data) == 0:
					raise MoiraConnectionError("Connection was closed while more data was expected")
				data += new_data
			return data
		else:
			return self.socket.recv(buffer_size)
	
	def sendPacket(self, opcode, data):
		"""Sends a Moira packet to the server. This is a blocking operation."""
		
		packet = MoiraPacket()
		packet.opcode = opcode
		packet.data = data
		self.send(packet.build())
	
	def recvPacket(self):
		"""Receives the most recent Moira packet from the server. This is a blocking operation."""
		length_data = self.recv(4)
		length = _read_u32(length_data)
		if length < 4:
			raise MoiraConnectionError("Invalid packet length specified")
		remainder = self.recv(length - 4)
		packet = MoiraPacket()
		packet.parse(length_data + remainder)
		return packet
	
	def checkMOTD(self):
		"""Checks whethet the server has an outage notice and raises an error if it does."""
		
		self.sendPacket(MR_MOTD, ())
		result = self.recvPacket()
		
		# Presence of MOTD means that server is unavailable,
		# or at least client/lib/utils.c treats it so
		if result.opcode == MR_SUCCESS:
			return
		if result.opcode != MR_MORE_DATA:
			raise MoiraError(result.opcode)

		motd = ""
		while result.opcode == MR_MORE_DATA:
			motd += result.data[0]
			result = self.recvPacket()

		if result.opcode != MR_SUCCESS:
			raise MoiraError(result.opcode)
		
		raise MoiraUnavailableError("Moira server is currently unavaliable: %s" % motd)
	
	def setVersion(self, version):
		"""Sets the query version for the connection and notifies the server about
		this change if the specified version has not already been set."""
		
		if self.version == version:
			return
		
		self.sendPacket( MR_SETVERSION, (str(version),) )
		result = self.recvPacket()
		if result.opcode != MR_SUCCESS and result.opcode != MR_VERSION_LOW:
			raise MoiraError(result.opcode)
	
	def authenticate(self, client = None):
		"""Authenticates to the server using Kerberos."""
		
		if not client:
			client = MOIRA_CLIENT_IDSTRING
		
		ap_req = _get_krb5_ap_req(MOIRA_KERBEROS_SERVICE_NAME, self.server)
		self.sendPacket( MR_KRB5_AUTH, (ap_req, client) )
		result = self.recvPacket()
		if result.opcode != MR_SUCCESS:
			raise MoiraError(result.opcode)
	
	def query(self, name, params, version = None):
		"""Sends a query to the Moira server and returns the result."""
		
		if version:
			self.setVersion(version)
		
		result = []
		
		query = (name,) + params
		self.sendPacket(MR_QUERY, query)
		response = self.recvPacket()

		while response.opcode == MR_MORE_DATA:
			result.append( response.data )
			response = self.recvPacket()
		
		if response.opcode != MR_SUCCESS:
			raise MoiraError(response.opcode)
		
		return tuple(result)
	
	def close(self):
		"""Closes the connection to the Moira server."""
		
		self.socket.close()
