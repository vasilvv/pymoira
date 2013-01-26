#
## PyMoira client library
##
## This file contains the Moira-related errors.
#

import constants

class BaseError(Exception):
    """Any exception thrown by the library is inhereted from this"""

    pass

class ConnectionError(BaseError):
    """An error which prevents the client from having or continuing a meaningful
    dialogue with a server (parsing failure, connection failure, etc)"""
    
    pass

class MoiraError(BaseError):
    """An error returned from Moira server itself which has a Moira error code."""
    
    def __init__(self, code):
        self.code = code
        
        if code in constants.errors:
            BaseError.__init__(self, "Moira error: %s" % constants.errors[code])
        else:
            BaseError.__init__(self, "Unknown Moira error (code %i)" % code)

class MoiraUnavailableError(BaseError):
    """An error raised in case when Moira MOTD is not empty."""
    
    pass

class UserError(BaseError):
    """An error related to Moira but not returned from the server."""
    
    pass
