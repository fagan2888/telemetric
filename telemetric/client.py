from __future__ import print_function, absolute_import
import json
import zlib
import struct
import socket
import logging
from Exscript.util.ipv4 import is_ip as is_ipv4
from Exscript.util.ipv6 import is_ip as is_ipv6
from .util import print_json
from .gpb import GPBDecoder

logger = logging.getLogger()
TCP_FLAG_ZLIB_COMPRESSION = 0x1

# Should use enum.Enum but not available in python2.7.1 on EnXR
class TCPMsgType(object):
    RESET_COMPRESSOR = 1
    JSON = 2
    GPB_COMPACT = 3
    GPB_KEY_VALUE = 4

    @classmethod
    def to_string(self, value):
        if value == TCPMsgType.RESET_COMPRESSOR:
            return "RESET_COMPRESSOR (1)"
        elif value == TCPMsgType.JSON:
            return "JSON (2)"
        elif value == TCPMsgType.GPB_COMPACT:
            return "GPB_COMPACT (3)"
        elif value == TCPMsgType.GPB_KEY_VALUE:
            return "GPB_KEY_VALUE (4)"
        else:
            raise ValueError("{} is not a valid TCP message type".format(value))

def unpack_int(raw_data):
    return struct.unpack_from(">I", raw_data, 0)[0]

def open_sockets(ip_address, port):
    # Figure out if the supplied address is ipv4 or ipv6 and set the socet type
    # appropriately
    if is_ipv4(ip_address):
        socket_type = socket.AF_INET
    elif is_ipv6(ip_address):
        socket_type = socket.AF_INET6
    else:
        raise AttributeError("Invalid ip address ", ip_address)

    # Bind to two sockets to handle either UDP or TCP data
    udp_sock = socket.socket(socket_type, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_sock.bind((ip_address, port))

    tcp_sock = socket.socket(socket_type)
    tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    tcp_sock.bind((ip_address, port))
    tcp_sock.listen(1)

    return tcp_sock, udp_sock

class JSONv1Handler(object):
    """
    JSON v1 (Pre IOS XR 6.1.0)
    """

    def __init__(self):
        self.deco = None

    def unpack_message(self, data):
        while len(data) > 0:
            _type = unpack_int(data)
            data = data[4:]

            if _type == 1:
                data = data[4:]
                yield 1, None
            elif _type == 2:
                msg_length = unpack_int(data)
                data = data[4:]
                msg = data[:msg_length]
                data = data[msg_length:]
                yield 2, msg

    def get_message(self, length, conn, json_dump=False, print_all=True):
        logger.info("  Message Type: JSONv1 (COMPRESSED)")
        data = b""
        while len(data) < length:
            data += conn.recv(length - len(data))

        tlvs = []
        for x in self.unpack_message(data):
            tlvs.append(x)

        #find the data
        for x in tlvs:
            if x[0] == 1:
                logger.info("  Reset Compressor TLV")
                self.deco = zlib.decompressobj()
            if x[0] == 2:
                logger.info("  Message TLV")
                c_msg = x[1]
                j_msg_b = self.deco.decompress(c_msg)
                if json_dump:
                    # Print the message as-is
                    print(j_msg_b)
                else:
                    # Decode and pretty-print the message
                    print_json(j_msg_b)

class JSONv2Handler(object):
    """
    JSON v2 (>= IOS XR 6.1.0)
    """

    def __init__(self):
        self.deco = zlib.decompressobj()

    def tcp_flags_to_string(self, flags):
        strings = []
        if flags & TCP_FLAG_ZLIB_COMPRESSION != 0:
            strings.append("ZLIB compression")
        if len(strings) == 0:
            return "None"
        else:
            return "|".join(strings)

    def get_message(self, msg_type, conn, json_dump=False, print_all=True):
        try:
            msg_type_str = TCPMsgType.to_string(msg_type)
            logger.info("  Message Type: {})".format(msg_type_str))
        except Exception as err:
            logger.error("  Invalid Message type: {}".format(msg_type))

        t = conn.recv(4)
        flags = unpack_int(t)
        logger.info("  Flags: {}".format(self.tcp_flags_to_string(flags)))
        t = conn.recv(4)
        length = unpack_int(t)
        logger.info("  Length: {}".format(length))

        # Read all the bytes of the message according to the length in the header
        data = b""
        while len(data) < length:
            data += conn.recv(length - len(data))

        # Decompress the message if necessary. Otherwise use as-is
        if flags & TCP_FLAG_ZLIB_COMPRESSION != 0:
            try:
                logger.info("Decompressing message")
                msg = self.deco.decompress(data)
            except Exception as err:
                logger.error("failed to decompress message: {}".format(err))
                msg = None
        else:
            msg = data

        # Decode the data according to the message type in the header
        logger.info("Decoding message")
        try:
            if msg_type == TCPMsgType.GPB_COMPACT:
                gpbdecoder.decode_compact(msg, json_dump=json_dump,
                                          print_all=print_all)
            elif msg_type == TCPMsgType.GPB_KEY_VALUE:
                gpbdecoder.decode_kv(msg, json_dump=json_dump,
                                     print_all=print_all)
            elif msg_type == TCPMsgType.JSON:
                if json_dump:
                    # Print the message as-is
                    print(msg)
                else:
                    # Decode and pretty-print the message
                    print_json(msg)
            elif msg_type == TCPMsgType.RESET_COMPRESSOR:
                self.deco = zlib.decompressobj()
        except Exception as err:
            logger.error("failed to decode TCP message: {}".format(err))

class TMClient(object):
    def __init__(self, ipaddress, port, protos=None, json_dump=False,
                 print_all=False):
        """
        @type ipaddress: str
        @param ipaddress: An IPv4 or IPv6 address.
        @type port: int
        @param port: The port number
        @type protos: list(str)
        @param protos: A list of protobuf filenames to load schemas from.
        @type json_dump: boolean
        @param json_dump: Whether to dump all json output to stdout.
        @type print_all: str
        @param print_all: Whether to print all messages to stdout.
        """
        self.gpbdecoder = GPBDecoder(protos or [])
        self.v1handler = JSONv1Handler()
        self.v2handler = JSONv2Handler()
        self.ipaddress = ipaddress
        self.port = port
        self.json_dump = json_dump
        self.print_all = print_all

    def get_message(self, conn):
        """
        Handle a received TCP message.

        @type conn: socket
        @param conn: The TCP connection
        """
        logger.info("Getting TCP message")

        # v1 message header (from XR6.0) consists of just a 4-byte length
        # v2 message header (from XR6.1 onwards) consists of 3 4-byte fields:
        #     Type,Flags,Length
        # If the first 4 bytes read is <=4 then it is too small to be a
        # valid length. Assume it is v2 instead
        t = conn.recv(4)
        msg_type = unpack_int(t)
        if msg_type > 4: # V1 message - compressed JSON
            handler = v1handler
        else:
            handler = v2handler

        # V2 message
        return handler.get_message(msg_type, conn,
                                   json_dump=self.json_dump,
                                   print_all=self.print_all)

    def _tcp_loop(self, tcp_sock):
        """
        Event Loop. Wait for TCP messages and pretty-print them
        """
        while True:
            logger.info("Waiting for TCP connection")
            conn, addr = tcp_sock.accept()
            logger.info("Got TCP connection")
            try:
                while True:
                     self.get_message(conn)
            except Exception as e:
                logger.error("Failed to get TCP message. Attempting to reopen connection: {}".format(e))

    def _udp_loop(self, udp_sock):
        """
        Event loop. Wait for messages and then pretty-print them
        """
        while True:
            logger.info("Waiting for UDP message")
            raw_message, address = udp_sock.recvfrom(2**16)
            # All UDP packets contain compact GPB messages
            gpbdecoder.decode_compact(raw_message,
                                      json_dump=self.json_dump,
                                      print_all=self.print_all)

    def run(self):
        tcp_sock, udp_sock = open_sockets(self.ipaddress, self.port)
        tcp_thread = threading.Thread(target=self._tcp_loop, args=(tcp_sock,))
        tcp_thread.daemon = True
        tcp_thread.start()

        udp_thread = threading.Thread(target=self._udp_loop, args=(udp_sock,))
        udp_thread.daemon = True
        udp_thread.start()

        while True:
            try:
                time.sleep(60)
            except KeyboardInterrupt:
                return
