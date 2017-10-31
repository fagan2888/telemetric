from __future__ import print_function
import os
import json
import re
from google.protobuf.message import Message
from google.protobuf.descriptor import FieldDescriptor
from protoutil import compile_proto_file, field_type_to_fn, proto_to_dict
from util import print_indent, timestamp_to_string, bytes_to_string

def _parse_schema_from_proto(input_file):
    """
    Find the schema path and corresponding message definition in a .proto file
    """
    message_re = re.compile(r'^message (\S+)')
    schema_path_re = re.compile(r'.*schema_path = "(\S+)"')
    message_name = None
    schema_path = None

    with open(input_file) as f:
        for line in f.readlines():
            # Look for the first instance of the string "message <message_name>"
            if message_name is None:
                match = message_re.match(line)
                if match:
                    message_name = match.group(1)
                continue

            # Look for "...schema_path = <schema_path>"
            match = schema_path_re.search(line)
            if match:
                schema_path = match.group(1)
                break

    return schema_path, message_name

def _load_modules(filenames):
    modules = {}
    for filename in filenames:
        module_name, ext = os.path.splitext(filename)
        module = imp.load_source(module_name, filename)
        modules[module_name] = module
    return modules

def print_compact_hdr(header):
    """
    Print the compact GPB message header
    """
    print("Encoding:    {:#x}".format(header.encoding))
    print("Policy Name: {}".format(header.policy_name))
    print("Version:     {}".format(header.version))
    print("Identifier:  {}".format(header.identifier))
    print("Start Time:  {}".format(timestamp_to_string(header.start_time)))
    print("End Time:    {}".format(timestamp_to_string(header.end_time)))
    print("# Tables:    {}""".format(len(header.tables)))

def print_compact_msg(field, indent, print_all=True):
    """
    Recursively iterate over a compactGPB obejct, displaying all fields at an 
    appropriate indent.

    @type :field: Field
    @param :field: The field to print.
    @type :indent: int
    @param :indent: The indent level to start printing at.
    @type :print_all: boolean
    @param :print_all: Whether to print all child messages, or just the first.
    """
    for descriptor in field.DESCRIPTOR.fields:
        value = getattr(field, descriptor.name)
        if descriptor.type == descriptor.TYPE_MESSAGE:
            # If the value is a sub-message then recursively call this function
            # to decode it. If the message is repeated then iterate over each
            # item.
            if descriptor.label == descriptor.LABEL_REPEATED:
                print_indent(indent, "{} ({} items) [", descriptor.name, len(value))
                for i, item in enumerate(value):
                    print_indent(indent, "{} {} {{", descriptor.name, i)
                    self.print_compact_msg(item, indent+1, print_all=print_all)
                    print_indent(indent, "}")
                    if not print_all:
                        # Stop after the first item unless all have been
                        # requested
                        break
                print_indent(indent, "]")
            else:
                print_indent(indent, "{} {{", descriptor.name)
                print_compact_msg(value, indent+1, print_all=print_all)
                print_at_indent(indent, "}")
        elif descriptor.type == descriptor.TYPE_ENUM:
            # For enum types print the enum name
            enum_name = descriptor.enum_type.values[value].name
            print_indent(indent, "{}: {}", descriptor.name, enum_name)
        elif descriptor.type == descriptor.TYPE_BYTES:
            print_indent(indent, "{}: {}", descriptor.name, bytes_to_string(value))
        else:
            # For everything else just print the value
            print_indent(indent, "{}: {}", descriptor.name, value)

def print_kv_hdr(header):
    """
    Print the key-value GPB message header
    """
    print("Collection ID:   {}".format(header.collection_id))
    print("Base Path:       {}".format(header.base_path))
    print("Subscription ID: {}".format(header.subscription_identifier))
    print("Model Version:   {}".format(header.model_version))

    # Start and end time are not always present
    if header.collection_start_time > 0:
        print("Start Time:      {}".format(timestamp_to_string(header.collection_start_time)))
    print("Msg Timestamp:   {}".format(timestamp_to_string(header.msg_timestamp)))
    if header.collection_end_time > 0:
        print("End Time:      {}".format(timestamp_to_string(header.collection_end_time)))
    print("Fields: {}".format(len(header.fields))) 

def print_kv_field_data(name, data, datatype, time, indent):
    """
    Print a single row for a TelemetryField message
    """
    name = name or "<no name>"
    print_indent(indent, "{}: {} ({}) {}", name, data, datatype, time)

def print_kv_field(field, indent):
    """
    Pretty-print a TelemtryField message
    """
    time = 0 if field.timestamp == 0 else timestamp_to_string(field.timestamp)
    
    # Find the datatype and print it
    datatypes = ["bytes_value",
                 "string_value",
                 "bool_value",
                 "uint32_value",
                 "uint64_value",
                 "sint32_value",
                 "sint64_value",
                 "double_value",
                 "float_value"]
    for d in datatypes:
        datatype = d[:-6]
        if field.HasField(d):
            if datatype == "bytes":
                value = bytes_to_string(field.bytes_value)
            else:
                value = getattr(field, d)
            print_kv_field_data(field.name, value, datatype, time, indent)

    # If 'fields' is used then recursively call this function to decode
    if field.fields:
        print_kv_field_data(field.name, 
                            "fields",
                            "items {}".format(len(field.fields)),
                            "{} {{".format(time), indent)

        for child in field.fields:
            print_kv_field(child, indent+1)
        print_indent(indent, "}")

class GPBDecoder(object):
    def __init__(self, protos):
        """
        Compile the telemetry proto files if they don't already exist and
        create a mapping between policy paths and proto files specified on the 
        command line.
        """
        # Build any proto files not already available
        proto_files = ["descriptor.proto",
                       "cisco.proto",
                       "telemetry.proto",
                       "telemetry_kv.proto"]
        compiled_files = _compile_proto_file(proto_files + protos)
        self.modules = _load_modules(compiled_files)

        # Load the decode methods from those modules.
        self.decoders = {}
        for proto in protos:
            schema_path, message_name = _parse_schema_from_proto(proto)
            self.decoders[schema_path] = getattr(module, message_name)

    def decode_compact(self, message, json_dump=False, print_all=True):
        """
        Decode and print a GPB compact message
        """
        telemetry_pb2 = self.modules['telemetry_pb2']
        header = telemetry_pb2.TelemetryHeader()
        header.ParseFromString(message)

        # Check the encoding value.
        ENCODING = 0x87654321
        if header.encoding != ENCODING:
            raise ValueError("Invalid 'encoding' value {:#x} (expected {:#x})".format(
                      header.encoding, ENCODING))

        # Print the message header
        json_dict = {}
        if json_dump:
            # Convert the protobuf into a dictionary in preparation for dumping
            # it as JSON.
            json_dict = proto_to_dict(header)
        else:
            print_compact_hdr(header)

        # Loop over the tables within the message to print them.
        for table_name, entry in enumerate(header.tables):
            schema_path = entry.policy_path
            if not json_dump:
                print_indent(1, "Schema Path:{}", schema_path)
                warning = "" if print_all else " (Only first row displayed)"
                print_indent(1, "# Rows:{}{}", len(entry.row), warning)

            # Find a decoder.
            decoder = self.decoders.get(schema_path)
            if not decoder:
                print_indent(1, "No decoder available")
                if json_dump:
                    json_dict["tables"][table_name]["row"][0] = "<No decoder available>"
                continue

            for i, row in enumerate(entry.row):
                row_msg = decoder()
                row_msg.ParseFromString(row)
                if json_dump:
                    # Replace the bytes in the 'row' field with a decoded dict
                    table = json_dict["tables"][table_name]
                    table["row"][i] = proto_to_dict(row_msg)
                else:
                    print_indent(2, "Row {}:", i)
                    print_compact_msg(row_msg, 2, args)
                    print("")

                if not print_all and not json_dump:
                    break

        if json_dump:
            print(json.dumps(json_dict))

    def decode_kv(self, message, json_dump=False, print_all=True):
        """
        Decode and print a GPB key-value message
        """
        telemetry_kv_pb2 = self.modules['telemetry_kv_pb2']
        header = telemetry_kv_pb2.Telemetry()
        header.ParseFromString(message)

        if json_dump:
            print(json.dumps(proto_to_dict(header)))
            return

        # Print the message header
        print_kv_hdr(header)

        # Loop over the tables within the message, printing either just the first 
        # row or all rows depending on the args specified
        if print_all:
            for entry in header.fields:
                print_kv_field(entry, 2)
        elif len(header.fields) > 0 and not args.brief:
            print("  Displaying first entry only")
            print_gpb_kv_field(header.fields[0], 1)
