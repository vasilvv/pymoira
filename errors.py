#
## PyMoira client library
##
## This file contains the Moira-related errors.
#

import moira_constants

class MoiraBaseError(Exception):
	"""Any exception thrown by the library is inhereted from this"""

	pass

class MoiraConnectionError(MoiraBaseError):
	"""An error which prevents the client from having or continuing a meaningful
	dialogue with a server (parsing failure, connection failure, etc)"""
	
	pass

class MoiraError(MoiraBaseError):
	"""An error returned from Moira server itself which has a Moira error code."""
	
	def __init__(self, code):
		if code in moira_constants.errors:
			MoiraBaseError.__init__(self, "Moira error: %s" % moira_constants.errors[code])
		else:
			MoiraBaseError.__init__(self, "Unknown Moira error (code %i)" % code)

class MoiraUnavailableError(MoiraBaseError):
	"""An error raised in case when Moira MOTD is not empty."""
	
	pass

class MoiraUserError(MoiraBaseError):
	"""An error related to Moira but not returned from the server."""
	
	pass
