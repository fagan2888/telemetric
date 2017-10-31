import time
import json

INDENT = "  "

def print_indent(indent, string, *args):
    """
    Print a string indented by the specified level
    """
    print("{}{}".format(INDENT*indent, string.format(*args)))

def print_json(message):
    """
    Pretty-print a JSON message
    """
    try:
        json_msg = json.loads(message.decode('ascii'))
    except Exception as e:
        print("ERROR: Failed to convert message to JSON: {}".format(e))
        return

    # Pretty-print the message
    print(json.dumps(json_msg, indent=4))

def bytes_to_string(thebytes):
    """
    Convert a byte array into a string aa:bb:cc
    """
    return ":".join(["{:02x}".format(int(ord(c))) for c in thebytes])

def timestamp_to_string(timestamp):
    """
    Convert a timestamp to a string
    """
    try:
        string = "{} ({}ms)".format(time.ctime(timestamp / 1000), 
                                    timestamp % 1000)
    except Exception as e:
        print("ERROR: Failed to decode timestamp {}: {}".format(timestamp, e))
        string = "{}".format(timestamp)
    return string
