class TMMessage(object):
    def __init__(self, msg_type, header, content):
        if msg_type not in (TCPMsgType.JSON,
                            TCPMsgType.GPB_COMPACT,
                            TCPMsgType.GPB_KEY_VALUE):
            raise ValueError('invalid message type: {}'.format(msg_type))
        msg_type = msg_type
        header = header
        content = content
