#
## PyMoira client library
##
## This file contains the utility functions common for multiple modules.
#

import datetime
from errors import UserError

def convertMoiraBool(val):
    if val == '1':
        return True
    if val == '0':
        return False
    raise UserError("Invalid boolean value received from Moira server")

def convertMoiraInt(val):
    try:
        return int(val)
    except ValueError:
        return None

def convertMoiraDateTime(val):
    return datetime.datetime.strptime(val, '%d-%b-%Y %H:%M:%S')

def convertToMoiraValue(val):
    """Converts data from Python to Moira protocol representation."""

    if type(val) == bool:
        return '1' if val else '0'
    else:
        return str(val)

def responseToDict(description, response):
    """Transforms the query response to a dictionary using a description
    of format ( (field name, type) ), where types are bool, int, string and
    date time."""
    
    if len(description) != len(response):
        raise UserError("Error returned the response with invalid number of entries")
    
    result = {}
    for value, field in ( (response[i], description[i]) for i in range( 0, len(response) ) ):
        name, datatype = field
        if datatype == bool:
            result[name] = convertMoiraBool(value)
        elif datatype == int:
            result[name] = convertMoiraInt(value)
        elif datatype == datetime.datetime:
            result[name] = convertMoiraDateTime(value)
        elif datatype == str:
            result[name] = value
        else:
            raise UserError("Unsupported Moira data type specified: %s" % datatype)
    
    return result
