#
## PyMoira client library
##
## This file contains the protocol details not specific to any certain side of the connection.
#

import struct

from errors import *

#
# Protocol-related constants
#
MOIRA_PORT = 775
MOIRA_PROTOCOL_VERSION = 2
MOIRA_PROTOCOL_CHALLENGE = "\0\0\0\066\0\0\0\004\001\001\001\001server_id\0parms\0host\0user\0\0\0\0\001\0\0\0\0\001\0\0\0\0\001\0\0\0\0\001\0" # You don't want to know why those two strings looks the way they look
MOIRA_PROTOCOL_RESPONSE = "\0\0\0\061\0\0\0\003\0\001\001disposition\0server_id\0parms\0\0\0\0\001\0\0\0\001\0\0\0\0\001\0"                     # You really don't. Not convinced? See mr_connect.c
MOIRA_CLIENT_IDSTRING = "PyMoira"
MOIRA_KERBEROS_SERVICE_NAME = "moira"

MOIRA_QUERY_VERSION = 14
MOIRA_MAX_LIST_DEPTH = 3072    # server/qsupport.pc, line 206

#
# Utility functions
#

def _fmt_u32(n):
    return struct.pack("!I", n)

def _read_u32(s):
    r, = struct.unpack("!I", s[0:4])
    return r

#
# The following object represents a packet in Moira dialogue.
# 
# Moira packet looks in the following way:
#   0) All numbers are in the network byte order
#   1) Packet header (16 bytes)
#     - Message length, including header (4 bytes)
#     - Version (4 bytes), have to be equal MOIRA_PROTOCOL_VERSION
#     - Opcode (client) / status (server) (4 bytes)
#         In general, will be one of the constants. However, it may also
#         be a negative Kerberos error code or something else.
#     - Amount of fields (4 bytes)
#   2) Fields, each has the following form:
#     - Length, *without* padding (4 bytes)
#     - Value, padded with zeroes to four-byte boundary. It is supposed to be
#         zero-terminated string, and I hope it is so.
#
class Packet(object):
    """Represents a basic Moira packet, send either way (from client to server or from
    server to client)."""
    
    opcode = None
    data = ()
    
    # Either built or received
    raw = None
    
    def build(self):
        """Constructs a binary packet which may be sent to Moira server."""
        
        # First construct the body
        body = ""
        for item in self.data:
            item += "\0"
            lenstr = _fmt_u32( len(item) )
            while len(item) % 4 != 0: item += "\0"
            body += lenstr
            body += item
        
        # Now that we know the length of the body, construct header
        header = struct.pack("!IIiI",
            16 + len(body),           # Total length
            MOIRA_PROTOCOL_VERSION,      # Protocol version
            self.opcode,              # Operation
            len(self.data)            # Field count
        )
        
        self.raw = header + body
        return self.raw
    
    def parse(self, orig):
        """Parses the packet from the network."""
        
        # Seperate header and body
        length, version, status, argc = struct.unpack("!IIiI", orig[:16])
        body = orig[16:]
        
        # Sanity checks for the header
        if length % 4 != 0:
            raise ConnectionError("Malformed Moira package: the length is not a multiple of four")
        if version != 2:
            raise ConnectionError("Moira protocol version mismatch")
        # argc is parsed as unsigned, hence argc is always >= 0

        # Read fields and truncate the body as we read
        fields = []
        for i in range(0, argc):
            if len(body) < 4:
                raise ConnectionError("Moira protocol version mismatch")

            field_len = _read_u32(body)
            if field_len + 4 > len(body):
                raise ConnectionError("")

            body = body[4:]

            if field_len % 4 == 0:
                actual_len = field_len
            else:
                actual_len = field_len + (4 - field_len % 4)

            field = body[:actual_len].rstrip("\0")
            body = body[actual_len:]

            fields.append(field)

        if len(body) > 0:
            raise ConnectionError("Moira has sent package with out-of-field information")

        self.raw_len = length
        self.opcode = status
        self.data = tuple(fields)
        self.raw = orig
