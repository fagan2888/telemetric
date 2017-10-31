from __future__ import absolute_import
import os
import imp
from subprocess import check_call
from google.protobuf.descriptor import FieldDescriptor

data_dir = os.path.join(os.path.dirname(__file__), 'data')

def compile_proto_file(input_files, output_path, include_path):
    """
    Compile a .proto file using protoc. Returns the list of compiled filenames.
    """
    need_compile = []
    compiled_names = []
    for filename in input_files:
        filename = os.path.join(data_dir, filename)

        # Check if the file exists.
        if not os.path.isfile(filename):
            raise ValueError("file {} does not exist".format(filename))

        # Assemble compiled filename to return to caller.
        basename, ext = os.path.splitext(filename)
        compiled_name = basename + "_pb2.py"
        compiled_names.append(compiled_name)

        # Check if the file was already compiled.
        if os.path.isfile(compiled_name):
            if os.path.getmtime(compiled_name) >= os.path.getmtime(filename):
                continue

        # Check if the compiled file is out of date.
        need_compile.append(filename)

    command = ["protoc", "--python_out", output_path, "-I", include_path] + need_compile
    check_call(command)
    return compiled_names

###############################################################################
# Protobuf to dict conversion
###############################################################################
DECODE_FN_MAP = {
    FieldDescriptor.TYPE_DOUBLE: float,
    FieldDescriptor.TYPE_FLOAT: float,
    FieldDescriptor.TYPE_INT32: int,
    FieldDescriptor.TYPE_INT64: long,
    FieldDescriptor.TYPE_UINT32: int,
    FieldDescriptor.TYPE_UINT64: long,
    FieldDescriptor.TYPE_SINT32: int,
    FieldDescriptor.TYPE_SINT64: long,
    FieldDescriptor.TYPE_FIXED32: int,
    FieldDescriptor.TYPE_FIXED64: long,
    FieldDescriptor.TYPE_SFIXED32: int,
    FieldDescriptor.TYPE_SFIXED64: long,
    FieldDescriptor.TYPE_BOOL: bool,
    FieldDescriptor.TYPE_STRING: unicode,
    FieldDescriptor.TYPE_BYTES: lambda b: bytes_to_string(b),
    FieldDescriptor.TYPE_ENUM: int,
}


def field_type_to_fn(msg, field):
    if field.type == FieldDescriptor.TYPE_MESSAGE:
        # For embedded messages recursively call this function. If it is
        # a repeated field return a list
        result = lambda msg: proto_to_dict(msg)
    elif field.type in DECODE_FN_MAP:
        result = DECODE_FN_MAP[field.type]
    else:
        raise TypeError("Field %s.%s has unrecognised type id %d" % (
                         msg.__class__.__name__, field.name, field.type))
    return result

def proto_to_dict(msg):
    result_dict = {}
    extensions = {}
    for field, value in msg.ListFields():
        conversion_fn = field_type_to_fn(msg, field)
        
        # Skip extensions
        if not field.is_extension:
            # Repeated fields result in an array, otherwise just call the 
            # conversion function to store the value
            if field.label == FieldDescriptor.LABEL_REPEATED:
                result_dict[field.name] = [conversion_fn(v) for v in value]
            else:
                result_dict[field.name] = conversion_fn(value)
    return result_dict
