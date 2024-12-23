#!/usr/bin/env python
################################################################
#  Non-adaptive AUTOSAR SOME/IP Communication Module Converter #
################################################################

import argparse, os, sys
from collections import OrderedDict
import io
import re

from pyfranca import Processor, LexerException, ParserException, \
    ProcessorException, ast

def capitalize_first_letter(input_string):
    return input_string[0].upper() + input_string[1:]

def lower_first_letter(input_string):
    return input_string[0].lower() + input_string[1:]

############################### AIDL Generation ###############################
def get_type_name(item):
    if(issubclass(type(item), ast.Array)):
        return item.type.name + '[]'
    else:
        return item.name

# dump_ 가 붙은 건 Abstract Syntax Tree 출력용임    
def dump_enum(item, prefix):
    for value in item.enumerators.values():
        print (prefix + value.name)

def dump_struct(item, prefix):
    for value in item.fields.values():
        print (prefix + get_type_name(value.type) + ' ' + value.name)

def dump_map(item, prefix):
    print(prefix + 'key type: ' + get_type_name(item.key_type))
    print(prefix + 'value type: ' + get_type_name(item.value_type))

def dump_comments(item, prefix):
    for key, value in item.comments.items():
        print (prefix + key + ": " + value)

def dump_namespace(namespace):
    if namespace.typedefs:
        print("\t\tTypedefs:")
        for item in namespace.typedefs.values():
            print("\t\t- {} is {}".format(item.name, item.type.name))
            dump_comments(item, "\t\t\t")
    if namespace.enumerations:
        print("\t\tEnumerations:")
        for item in namespace.enumerations.values():
            if(item.extends):
                print("\t\t- {} extends {}".format(item.name, item.extends))
            else:
                print("\t\t- {}".format(item.name))
            dump_enum(item, "\t\t\t- ")
            dump_comments(item, "\t\t\t")
    if namespace.structs:
        print("\t\tStructs:")
        for item in namespace.structs.values():
            if(item.extends):
                print("\t\t- {} extends {}".format(item.name, item.extends))
            else:
                print("\t\t- {}".format(item.name))
            dump_struct(item, "\t\t\t- ")
            dump_comments(item, "\t\t\t")
    if namespace.arrays:
        print("\t\tArrays:")
        for item in namespace.arrays.values():
            print("\t\t- {}[] {}".format(item.type.name, item.name))
            dump_comments(item, "\t\t\t")
    if namespace.maps:
        print("\t\tMaps:")
        for item in namespace.maps.values():
            print("\t\t- {}".format(item.name))
            dump_map(item, "\t\t\t- ")
            dump_comments(item, "\t\t\t")
    if namespace.constants:
        print("\t\tConstants:")
        for item in namespace.constants.values():
            print("\t\t- {}".format(item.name))
            dump_comments(item, "\t\t\t")

def dump_method(item, prefix):
    for _, value in item.in_args.items():
        print(prefix + 'in: ' + get_type_name(value.type) + ' ' + value.name)
    for _, value in item.out_args.items():
        print(prefix + 'out: ' + get_type_name(value.type) + ' ' + value.name)

def dump_broadcast(item, prefix):
    for _, value in item.out_args.items():
        print(prefix + 'out: ' + get_type_name(value.type) + ' ' + value.name)

def dump_interface(interface):
    if interface.attributes:
        print("\t\tAttributes:")
        for item in interface.attributes.values():
            print("\t\t- {} {}".format(item.type.name, item.name))
            dump_comments(item, "\t\t\t")
    if interface.methods:
        print("\t\tMethods:")
        for item in interface.methods.values():
            print("\t\t- {}()".format(item.name))
            dump_method(item, "\t\t\t- ")
            dump_comments(item, "\t\t\t")
    if interface.broadcasts:
        print("\t\tBroadcasts:")
        for item in interface.broadcasts.values():
            print("\t\t- {}".format(item.name))
            dump_broadcast(item, "\t\t\t- ")
            dump_comments(item, "\t\t\t")
    dump_namespace(interface)

def dump_package(package):
    print("- {}".format(package.name))
    dump_comments(package, "\t")
    if package.interfaces:
        print("\tInterfaces:")
        for interface in package.interfaces.values():
            if interface.version:
                version_str = " (v{})".format(interface.version)
            else:
                version_str = ""
            print("\t- {}{}".format(interface.name, version_str))
            dump_comments(interface, "\t\t")
            dump_interface(interface)
    if package.typecollections:
        print("\tType collections:")
        for typecollection in package.typecollections.values():
            if typecollection.version:
                version_str = " (v{})".format(typecollection.version)
            else:
                version_str = ""
            print("\t- {}{}".format(typecollection.name, version_str))
            dump_comments(typecollection, "\t\t")
            dump_namespace(typecollection)

def dump_packages(packages):
    print("Packages:")
    for package in packages.values():
        dump_package(package)

def convert_aidl_type(typename):
    if(typename == 'Int8' or typename == 'UInt8'):
        return 'byte'
    if(typename == 'Int16'):
        return 'int'
    if(typename == 'Int32' or typename == 'UInt16'):
        return 'int'
    if(typename == 'Int64' or typename == 'UInt32' or typename == 'UInt64'):
        return 'long'
    if(typename == 'Float'):
        return 'float'
    if(typename == 'Double'):
        return 'double'
    if(typename == 'Boolean'):
        return 'boolean'
    if(typename == 'String'):
        return 'String'
    if(typename == 'ByteBuffer'):
        return 'byte[]'
    
    return typename
    
def get_aidl_type_name(item):
    typename = ''
    if(issubclass(type(item), ast.Array)):
        typename = convert_aidl_type(item.type.name)
        return typename + '[]'
    elif(isinstance(item, ast.Reference)):
        if(isinstance(item.reference, ast.Map)):
            typename = convert_aidl_type(item.reference.name)
            return typename + '[]'
        else:
            typename = convert_aidl_type(item.name)
            return typename
    else:
        typename = convert_aidl_type(item.name)
        return typename

########################## Broadcast #########################################
def generate_aidl_broadcast(broadcast, interface_name):
    aidl_str = ""
    aidl_str += "\tvoid subscribe{}({}{}Callback callback);\n".format(capitalize_first_letter(broadcast.name), interface_name,capitalize_first_letter(broadcast.name))
    aidl_str += "\tvoid unsubscribe{}({}{}Callback callback);\n".format(capitalize_first_letter(broadcast.name), interface_name, capitalize_first_letter(broadcast.name))
    
    return aidl_str

def generate_aidl_method_parcelable(method, package_name):
    aidl_str = ""
    list_references = set()
    import_str = ""
    
    aidl_str += "parcelable {}ReturnType {{\n".format(capitalize_first_letter(method.name))
    for arg in method.out_args.values():
        aidl_str += "\t{} {};\n".format(get_aidl_type_name(arg.type).split('.')[-1], arg.name)
        if(isinstance(arg.type, ast.Reference)):
            list_references.add(arg.type.reference)
        if(isinstance(arg.type, ast.Reference)):
            list_references.add(arg.type.reference)
        if(isinstance(arg.type, ast.Array)):
            if(arg.type.name == None and isinstance(arg.type.type, ast.Reference)):
                list_references.add(arg.type.type.reference)
            elif(arg.type.name != None and isinstance(arg.type.reference.type, ast.Reference)):
                list_references.add(arg.type.reference.type.reference)
    aidl_str += "}\n"

    for reference in list_references:
        import_str += "import {}.{};\n".format(package_name, reference.name)
    import_str += "\n"
    
    return aidl_str, import_str

def generate_aidl_method(method):
    aidl_str = ""
    return_type = ""
    if(len(method.out_args.values()) == 1):
        arg = next(iter(method.out_args.values()))
        return_type = get_aidl_type_name(arg.type)
        return_type = return_type.split('.')[-1]
        
    elif(len(method.out_args.values()) == 0):
        return_type = "void"
    else:
        # AIDL 12 이상부터 nested parcelable 지원으로 주석처리
        # aidl_str += "\tparcelable {}ReturnType {{\n".format(capitalize_first_letter(method.name))
        # for arg in method.out_args.values():
        #     aidl_str += "\t\t{} {};\n".format(get_aidl_type_name(arg.type).split('.')[-1], arg.name)
        # aidl_str += "\t}\n"
        return_type = "{}ReturnType".format(capitalize_first_letter(method.name))
    if("fireAndForget" in method.flags):
        aidl_str += "\toneway {} {}(".format(return_type, method.name)    
    else:
        aidl_str += "\t{} {}(".format(return_type, method.name)
    index = 0
    for arg in method.in_args.values():
        aidl_str += "in {} {}".format(get_aidl_type_name(arg.type).split('.')[-1], arg.name)
        index += 1
        if(index != len(method.in_args)):
            aidl_str += ", "
    aidl_str += ");\n"
    return aidl_str

def generate_aidl_enumerate(enum):
    aidl_str = ""
    aidl_str += "\tenum {} {{".format(enum.name)
    # if(enum.extends):
    index = 0
    for elem in enum.enumerators.values():
        index += 1
        aidl_str += "{}".format(elem.name)
        if(index != len(enum.enumerators.values())):
            aidl_str += ", "
    aidl_str += "}\n"
    return aidl_str

def generate_aidl_const(const):
    aidl_str = ""
    typename = get_aidl_type_name(const.type)
    value = const.value.value if typename != "String" else "\"{}\"".format(const.value.value)
    aidl_str += "\tconst {} {} = {};\n".format(typename, const.name, value)
    return aidl_str


def generate_aidl_parcelabele(struct):
    aidl_str = ""
    # AIDL 12 이상부터 nested parcelable 지원으로 주석처리
    # aidl_str += "parcelable {}.{} {{\n".format(struct.namespace.name,struct.name)
    aidl_str += "parcelable {} {{\n".format(struct.name)
    for field in struct.fields.values():
        aidl_str += "\t{} {};\n".format(get_aidl_type_name(field.type).split('.')[-1], field.name)
    aidl_str += "}\n"
    return aidl_str

def generate_aidl_map(map):
    aidl_str = ""
    aidl_str += "\tparcelable {} {{\n".format(map.name)
    aidl_str += "\t\t{} key;\n".format(get_aidl_type_name(map.key_type))
    aidl_str += "\t\t{} value;\n".format(get_aidl_type_name(map.value_type))
    aidl_str += "\t}\n"
    return aidl_str

def generate_aidl_attribute(attribute, interface):
    aidl_str = ""
    handler_str = ""
    aidl_attribute = get_aidl_type_name(attribute.type)
    
    # map_str = ""
    # if(check_type_ver2(attribute, interface) == 11):
    #     map_str = "[]"
    
    if(len(aidl_attribute.split('.')) > 1):
        aidl_attribute = aidl_attribute.split('.')[-1]
    else:
        aidl_attribute = aidl_attribute
    aidl_str += "\tvoid subscribeAttribute{}({}{}Handler handler);\n".format(capitalize_first_letter(attribute.name),interface,capitalize_first_letter(attribute.name))
    if('readonly' not in attribute.flags):
        aidl_str += "\tvoid setAttribute{}Value(in {} value);\n".format(capitalize_first_letter(attribute.name), aidl_attribute)
    aidl_str += "\t{} getAttribute{}Value();\n".format(aidl_attribute, capitalize_first_letter(attribute.name))
    aidl_str += "\tvoid unsubscribeAttribute{}({}{}Handler handler);\n".format(capitalize_first_letter(attribute.name),interface,capitalize_first_letter(attribute.name))
    return aidl_str, handler_str

def generate_aidl_array(array):
    aidl_str = ""   
    # AIDL 12 이상부터 nested parcelable 지원으로 주석처리
    # aidl_str += "parcelable {}.{} {{\n".format(array.namespace.name,array.name)
    aidl_str += "parcelable {} {{\n".format(array.name)
    aidl_str += "\t{}[] data;\n".format(get_aidl_type_name(array.type))
    aidl_str += "}\n"
    return aidl_str

def generate_aidl_handler_interface_from_fidl_attribute(attribute, package_name):
    import_str = ""
    interface_str = ""
    list_references = set()

    interface_str += "\tvoid run{}Handler(".format(capitalize_first_letter(attribute.name))
    interface_str += "in {} value".format(get_aidl_type_name(attribute.type).split('.')[-1])
    interface_str += ");"
    interface_str += "\n"
    if(isinstance(attribute.type, ast.Reference)):
        list_references.add(attribute.type.reference)
    if(isinstance(attribute.type, ast.Array)):
            if(attribute.type.name == None and isinstance(attribute.type.type, ast.Reference)):
                list_references.add(attribute.type.type.reference)
            elif(attribute.type.name != None and isinstance(attribute.type.reference.type, ast.Reference)):
                list_references.add(attribute.type.reference.type.reference)
    for reference in list_references:
        import_str += "import {}.{};\n".format(package_name, reference.name)
    return interface_str, import_str

def generate_aidl_callback_interface_from_fidl_broadcast(broadcast, package_name):
    import_str = ""
    interface_str = ""
    list_references = set()

    interface_str += "\tvoid on{}Received(".format(capitalize_first_letter(broadcast.name))
    index = 1
    for arg in broadcast.out_args.values():
        if(isinstance(arg.type, ast.Reference)):
            list_references.add(arg.type.reference)
        if(isinstance(arg.type, ast.Array)):
            if(arg.type.name == None and isinstance(arg.type.type, ast.Reference)):
                list_references.add(arg.type.type.reference)
            elif(arg.type.name != None and isinstance(arg.type.reference.type, ast.Reference)):
                list_references.add(arg.type.reference.type.reference)
        interface_str += "in {} value{}".format(get_aidl_type_name(arg.type).split('.')[-1], index)
        index += 1
        if(index != len( broadcast.out_args)+1):
            interface_str += ", "
    interface_str += ");"
    interface_str += "\n"
    for reference in list_references:
        import_str += "import {}.{};\n".format(package_name, reference.name)
    return interface_str, import_str

def generate_aidl_interface_from_fidl_interface(interface, package_name):
    import_str = ""
    interface_str = ""
    interface_str_temp = ""
    list_references = set()
    handler_str = ""
    handler_str_temp = ""
    

    if(interface.attributes):
        for attribute in interface.attributes.values():
            if(isinstance(attribute.type, ast.Reference)):
                list_references.add(attribute.type.reference)
            interface_str_temp, handler_str_temp = generate_aidl_attribute(attribute, interface.name)
            interface_str += interface_str_temp
            handler_str += handler_str_temp
    if(interface.methods):
        for method in interface.methods.values():
            for arg in method.in_args.values():
                if(isinstance(arg.type, ast.Reference)):
                    list_references.add(arg.type.reference)
            for arg in method.out_args.values():
                if(isinstance(arg.type, ast.Reference)):
                    list_references.add(arg.type.reference)
            interface_str += generate_aidl_method(method)
    if(interface.broadcasts):
        for broadcast in interface.broadcasts.values():
            for arg in broadcast.out_args.values():
                if(isinstance(arg.type, ast.Reference)):
                    list_references.add(arg.type.reference)
            interface_str += generate_aidl_broadcast(broadcast, interface.name)
    # AIDL 12 이상부터 nested parcelable 지원으로 주석처리
    # if(interface.enumerations):
    #     for enum in interface.enumerations.values():
    #         interface_str += generate_aidl_enumerate(enum)
    if(interface.constants):
        for constant in interface.constants.values():
            if((isinstance(constant.type, ast.String) or isinstance(constant.type, ast.Int16) or isinstance(constant.type, ast.Int32) or isinstance(constant.type, ast.UInt16) or isinstance(constant.type, ast.UInt32)) == False):
                continue
            if(isinstance(constant.type, ast.Reference)):
                list_references.add(constant.type.reference)
            interface_str += generate_aidl_const(constant)
    # AIDL 12 이상부터 nested parcelable 지원으로 주석처리
    # if(interface.structs):
    #     for struct in interface.structs.values():
    #         for field in struct.fields.values():
    #             if(isinstance(field.type, ast.Reference)):
    #                 list_references.add(field.type.reference)
    #         interface_str += generate_aidl_parcelabele(struct)
    # if(interface.maps):
    #     for map in interface.maps.values():
    #         interface_str += generate_aidl_map(map)
    ## Android 12
    # if(interface.arrays):
    #     for array in interface.arrays.values():
    #         if(isinstance(array.type, ast.Reference)):
    #             list_references.add(array.type.reference)
    #         interface_str += generate_aidl_array(array)
    for reference in list_references:
        if(reference.namespace.name == interface.name):
            continue
        # AIDL 12 이상부터 nested parcelable 지원으로 주석처리
        #import_str += "import {}.{}.{};\n".format(package_name, reference.namespace.name, reference.name)
        import_str += "import {}.{};\n".format(package_name, reference.name)
    import_str += "\n"
    #handler_str += "\n"
    interface_str += handler_str
    return interface_str, import_str

def generate_aidl_parcelable_from_fidl_struct(struct, package_name):
    import_str = ""
    interface_str = ""
    list_references = set()

    for field in struct.fields.values():
        if(isinstance(field.type, ast.Reference)):
            list_references.add(field.type.reference)
        if(isinstance(field.type, ast.Array)):
            if(field.type.name == None and isinstance(field.type.type, ast.Reference)):
                list_references.add(field.type.type.reference)
            elif(field.type.name != None and isinstance(field.type.reference.type, ast.Reference)):
                list_references.add(field.type.reference.type.reference)
    interface_str += generate_aidl_parcelabele(struct)

    for reference in list_references:
        import_str += "import {}.{};\n".format(package_name, reference.name)
    import_str += "\n"
    
    return interface_str, import_str

def generate_aidl_parcelable_from_fidl_array(array, package_name):
    import_str = ""
    interface_str = ""
    list_references = set()

    if(isinstance(array.type, ast.Reference)):
        list_references.add(array.type.reference)
    interface_str += generate_aidl_array(array)
    for reference in list_references:
        # if(reference.namespace.name == array.type.reference.namespace.name):
        #     continue
        import_str += "import {}.{};\n".format(package_name, reference.name)
    import_str += "\n"
    
    return interface_str, import_str

def generate_aidl_parcelable_from_fidl_enum(enum, package_name):
    import_str = ""
    interface_str = ""
    list_references = set()

    interface_str += generate_aidl_enumerate(enum)
    for reference in list_references:
        # if(reference.namespace.name == array.type.reference.namespace.name):
        #     continue
        import_str += "import {}.{};\n".format(package_name, reference.name)
    import_str += "\n"

    return interface_str, import_str

def generate_aidl_parcelable_from_fidl_map(map, package_name):
    import_str = ""
    interface_str = ""
    list_references = set()

    interface_str += generate_aidl_map(map)
    if(isinstance(map.key_type, ast.Reference)):
        list_references.add(map.key_type.reference)
    if(isinstance(map.value_type, ast.Reference)):
        list_references.add(map.value_type.reference)
    for reference in list_references:
        # if(reference.namespace.name == map.type.reference.namespace.name):
        #    continue
        import_str += "import {}.{};\n".format(package_name, reference.name)
    import_str += "\n"

    return interface_str, import_str

def generate_aidl_interface_from_fidl_typecollection(interface, package_name):
    
    import_str = ""
    interface_str = ""
    list_references = set()
    # AIDL 12 이상부터 nested parcelable 지원으로 주석처리
    # if(interface.enumerations):
    #     for enum in interface.enumerations.values():
    #         interface_str += generate_aidl_enumerate(enum)
    if(interface.constants):
        for constant in interface.constants.values():
            if((isinstance(constant.type, ast.String) or isinstance(constant.type, ast.Int16) or isinstance(constant.type, ast.Int32) or isinstance(constant.type, ast.UInt16) or isinstance(constant.type, ast.UInt32)) == False):
                continue
            if(isinstance(constant.type, ast.Reference)):
                list_references.add(constant.type.reference)
            interface_str += generate_aidl_const(constant)
    # AIDL 12 이상부터 nested parcelable 지원으로 주석처리
    # if(interface.structs):
    #     for struct in interface.structs.values():
    #         for field in struct.fields.values():
    #             if(isinstance(field.type, ast.Reference)):
    #                 if(field.type.reference.namespace.name != interface.name):
    #                     list_references.add(field.type.reference)
    #         interface_str += generate_aidl_parcelabele(struct)
    
    
    # if(interface.maps):
    #     for map in interface.maps.values():
    #         interface_str += generate_aidl_map(map)
    
    # if(interface.arrays):
    #     for array in interface.arrays.values():
    #         if(isinstance(array.type, ast.Reference)):
    #             list_references.add(array.type.reference)
    #         interface_str += generate_aidl_array(array)
    for reference in list_references:
        # AIDL 12 이상부터 nested parcelable 지원으로 주석처리
        #import_str += "import {}.{}.{};\n".format(package_name, reference.namespace.name, reference.name)
        import_str += "import {}.{};\n".format(package_name, reference.name)
    import_str += "\n"
    return interface_str, import_str

def convert_to_aidl(packages, package_name, output_dir):
    interfaces = OrderedDict()
    imports = OrderedDict()
    extends = OrderedDict()
    parcel = OrderedDict()
    parcel_imports = OrderedDict()
    
    
    os.makedirs(output_dir + '/aidl', exist_ok=True)

    for package in packages.values():
        try:
            if(package.interfaces):
                for interface in package.interfaces.values():
                    interface_str, import_str = generate_aidl_interface_from_fidl_interface(interface, package_name)
                    interfaces[interface.name] = interface_str
                    imports[interface.name] = import_str
                    extends[interface.name] = interface.extends if interface.extends else None
                    # Unsupported data types filtering
                    # if(interface.maps):
                    #     raise Exception("Interface {}, Maps are not supported".format(interface.name))
                    
                    if(interface.attributes):
                        for attribute in interface.attributes.values():
                            hanlder_interface_str, handler_import_str = generate_aidl_handler_interface_from_fidl_attribute(attribute, package_name=package_name)
                            #interfaces[interface.name] += "\n\tinterface {} {{\n \t{} \t}}\n".format((capitalize_first_letter(broadcast.name)+"Callback"),callback_interface_str)
                            interfaces["{}{}Handler".format(interface.name, capitalize_first_letter(attribute.name))] = hanlder_interface_str
                            imports["{}{}Handler".format(interface.name, capitalize_first_letter(attribute.name))] = handler_import_str
                            imports[interface.name] += "import {}.{}{}Handler;\n".format(package_name, interface.name, capitalize_first_letter(attribute.name))
                    if(interface.broadcasts):
                        for broadcast in interface.broadcasts.values(): 
                            callback_interface_str, callback_import_str = generate_aidl_callback_interface_from_fidl_broadcast(broadcast, package_name)
                            #interfaces[interface.name] += "\n\tinterface {} {{\n \t{} \t}}\n".format((capitalize_first_letter(broadcast.name)+"Callback"),callback_interface_str)
                            interfaces["{}{}Callback".format(interface.name, capitalize_first_letter(broadcast.name))] = callback_interface_str
                            imports["{}{}Callback".format(interface.name, capitalize_first_letter(broadcast.name))] = callback_import_str
                            imports[interface.name] += "import {}.{}{}Callback;\n".format(package_name, interface.name, capitalize_first_letter(broadcast.name))
                    if(interface.structs):
                        for struct in interface.structs.values():
                            struct_interface_str, struct_import_str = generate_aidl_parcelable_from_fidl_struct(struct, package_name)
                            ## Android 12
                            # parcel["{}.{}".format(interface.name, struct.name)] = struct_interface_str
                            # parcel_imports["{}.{}".format(interface.name, struct.name)] = struct_import_str
                            # imports[interface.name] += "import {}.{}.{};\n".format(package_name, interface.name, struct.name)
                            parcel["{}".format(struct.name)] = struct_interface_str
                            parcel_imports["{}".format(struct.name)] = struct_import_str
                            imports[interface.name] += "import {}.{};\n".format(package_name, struct.name)
                    if(interface.arrays):
                        for array in interface.arrays.values():
                            array_interface_str, array_import_str = generate_aidl_parcelable_from_fidl_array(array, package_name)
                            ## Android 12 does not allow nested parcelables
                            # parcel["{}.{}".format(interface.name, array.name)] = array_interface_str
                            # parcel_imports["{}.{}".format(interface.name, array.name)] = array_import_str
                            # imports[interface.name] += "import {}.{}.{};\n".format(package_name, interface.name, array.name)
                            parcel["{}".format(array.name)] = array_interface_str
                            parcel_imports["{}".format(array.name)] = array_import_str
                            imports[interface.name] += "import {}.{};\n".format(package_name, array.name)
                    if(interface.enumerations):
                        for enum in interface.enumerations.values():
                            enum_interface_str, enum_import_str = generate_aidl_parcelable_from_fidl_enum(enum, package_name)
                            parcel["{}".format(enum.name)] = enum_interface_str
                            parcel_imports["{}".format(enum.name)] = enum_import_str
                            imports[interface.name] += "import {}.{};\n".format(package_name, enum.name)
                    if(interface.maps):
                        for map in interface.maps.values():
                            map_interface_str, map_import_str = generate_aidl_parcelable_from_fidl_map(map, package_name)
                            parcel["{}".format(map.name)] = map_interface_str
                            parcel_imports["{}".format(map.name)] = map_import_str
                            imports[interface.name] += "import {}.{};\n".format(package_name, map.name)
                            # print(imports[interface.name])
                            
                    if(interface.methods):
                        for method in interface.methods.values():
                            if(len(method.out_args.values()) > 1):
                                method_interface_str, method_import_str = generate_aidl_method_parcelable(method, package_name)
                                # parcel["{}.{}ReturnType".format(interface.name, method.name)] = method_interface_str
                                # parcel_imports["{}.{}ReturnType".format(interface.name, method.name)] = method_import_str
                                # imports[interface.name] += "import {}.{}.{}ReturnType;\n".format(package_name, interface.name, capitalize_first_letter(method.name))
                                parcel["{}ReturnType".format(method.name)] = method_interface_str
                                parcel_imports["{}ReturnType".format(method.name)] = method_import_str
                                imports[interface.name] += "import {}.{}ReturnType;\n".format(package_name, capitalize_first_letter(method.name))
            if(package.typecollections):
                for typecollection in package.typecollections.values():
                    interface_str, import_str = generate_aidl_interface_from_fidl_typecollection(typecollection, package_name)
                    interfaces[typecollection.name] = interface_str
                    imports[typecollection.name] = import_str
                    if(typecollection.structs):
                        for struct in typecollection.structs.values():
                            struct_interface_str, struct_import_str = generate_aidl_parcelable_from_fidl_struct(struct, package_name)
                            # parcel["{}.{}".format(typecollection.name, struct.name)] = struct_interface_str
                            # parcel_imports["{}.{}".format(typecollection.name, struct.name)] = struct_import_str
                            # imports[interface.name] += "import {}.{}.{};\n".format(package_name, typecollection.name, struct.name)
                            parcel["{}".format(struct.name)] = struct_interface_str
                            parcel_imports["{}".format(struct.name)] = struct_import_str
                            imports[interface.name] += "import {}.{};\n".format(package_name, struct.name)
                    if(typecollection.arrays):
                        for array in typecollection.arrays.values():
                            array_interface_str, array_import_str = generate_aidl_parcelable_from_fidl_array(array, package_name)
                            # parcel["{}.{}".format(typecollection.name,array.name)] = array_interface_str
                            # parcel_imports["{}.{}".format(typecollection.name,array.name)] = array_import_str
                            # imports[interface.name] += "import {}.{}.{};\n".format(package_name, typecollection.name, array.name)
                            parcel["{}".format(array.name)] = array_interface_str
                            parcel_imports["{}".format(array.name)] = array_import_str
                            imports[interface.name] += "import {}.{};\n".format(package_name, array.name)
                    if(typecollection.enumerations):
                        for enum in typecollection.enumerations.values():
                            enum_interface_str, enum_import_str = generate_aidl_parcelable_from_fidl_enum(enum, package_name)
                            parcel["{}".format(enum.name)] = enum_interface_str
                            parcel_imports["{}".format(enum.name)] = enum_import_str
                            imports[interface.name] += "import {}.{};\n".format(package_name, enum.name)
        except (Exception) as e:
            print("ERROR during AIDL generation: {}".format(e))
            continue
        
    for interface, interface_str in interfaces.items():
        aidl_str = ""
        aidl_str += "// Auto-generated by FIDL-AIDL Converter\n"
        aidl_str += "// Filename: {}.aidl\n\n".format(interface)
        aidl_str += "package {};\n\n".format(package_name)
        imports_set = set()
        if(extends.get(interface)):
            for _import in imports.get(extends.get(interface)).split('\n'):
                if(_import):
                    imports_set.add(_import)        
        for _import in imports.get(interface).split('\n'):
            if(_import):
                imports_set.add(_import)
        imports_set = list(imports_set)
        for _import in imports_set:
            aidl_str += _import + "\n"
        aidl_str += "\ninterface {} {{ \n".format(interface)
        if(extends.get(interface)):
            aidl_str += interfaces.get(extends.get(interface))
        aidl_str += interface_str
        aidl_str += "}\n"
        f = open("{}/aidl/{}.aidl".format(output_dir,interface), "w")
        f.write(aidl_str)
        f.close()
        
    for interface, interface_str in parcel.items():
        tcollection = interface.split('.')[0]
        aidl_str = ""
        aidl_str += "// Auto-generated by FIDL-AIDL Converter\n"
        aidl_str += "// Filename: {}.aidl\n\n".format(interface)
        aidl_str += "package {};\n\n".format(package_name)
        imports_set = set()
        if(extends.get(interface)):
            for _import in parcel_imports.get(extends.get(interface)).split('\n'):
                if(_import):
                    imports_set.add(_import)
        for _import in parcel_imports.get(interface).split('\n'):
            if(_import):
                imports_set.add(_import)
        imports_set = list(imports_set)
        for _import in imports_set:
            aidl_str += _import + "\n"
        #aidl_str += "\ninterface {} {{ \n".format(interface)
        aidl_str += "\n"
        if(extends.get(interface)):
            aidl_str += interfaces.get(extends.get(interface))
        aidl_str += interface_str
        #aidl_str += "}\n"
        f = open("{}/aidl/{}.aidl".format(output_dir,interface), "w")
        f.write(aidl_str)
        f.close()
################################################################################### AIDL End

# CPP code에서 사용되는 data type으로 변환
def convert_cpp_type(typename):
    if(typename == 'Int8'):
        return 'int8_t'
    if(typename == 'Int16'):
        return 'int16_t'
    if(typename == 'Int32'):
        return 'int32_t'
    if(typename == 'Int64'):
        return 'int64_t'
    if(typename == 'UInt8'):
        return 'uint8_t'
    if(typename == 'UInt16'):
        return 'uint16_t'
    if(typename == 'UInt32'):
        return 'uint32_t'
    if(typename == 'UInt64'):
        return 'uint64_t'
    if(typename == 'Float'):
        return 'float'
    if(typename == 'Double'):
        return 'double'
    if(typename == 'Boolean'):
        return 'bool'
    if(typename == 'String'):
        return 'std::string'
    return typename

# CPP에서 JNI 호출할 때 사용하는 data type으로 변환
def convert_jni_type(typename):
    if(typename == 'Int8'):
        return 'B'
    if(typename == 'Int16'):
        #return 'S'
        return 'I'
    if(typename == 'Int32'):
        return 'I'
    if(typename == 'Int64'):
        return 'J'
    if(typename == 'UInt8'):
        #return 'S'
        return 'B'
    if(typename == 'UInt16'):
        return 'I'
    if(typename == 'UInt32'):
        return 'J'
    if(typename == 'UInt64'):
        return 'J'
    if(typename == 'Float'):
        return 'F'
    if(typename == 'Double'):
        return 'D'
    if(typename == 'Boolean'):
        return 'Z'
    if(typename == 'String'):
        return 'Ljava/lang/String;'
    return typename

# CPP에서 사용하는 java data type
def convert_java_type(typename):
    if(typename == 'Int8'):
        return 'jbyte'
    if(typename == 'Int16'):
        #return 'jshort'
        return 'jint'
    if(typename == 'Int32'):
        return 'jint'
    if(typename == 'Int64'):
        return 'jlong'
    if(typename == 'UInt8'):
        #return 'jshort'
        return 'jbyte'
    if(typename == 'UInt16'):
        return 'jint'
    if(typename == 'UInt32'):
        return 'jlong'
    if(typename == 'UInt64'):
        return 'jlong'
    if(typename == 'Float'):
        return 'jfloat'
    if(typename == 'Double'):
        return 'jdouble'
    if(typename == 'Boolean'):
        return 'jboolean'
    if(typename == 'String'):
        return 'jstring'
    return typename

# Java code에서 사용하는 data type
def convert_java_code_type(typename):
    if(typename == 'Int8'):
        return 'byte'
    if(typename == 'Int16'):
        #return 'short'
        return 'int'
    if(typename == 'Int32'):
        return 'int'
    if(typename == 'Int64'):
        return 'long'
    if(typename == 'UInt8'):
        #return 'short'
        return 'byte'
    if(typename == 'UInt16'):
        return 'int'
    if(typename == 'UInt32'):
        return 'long'
    if(typename == 'UInt64'):
        return 'long'
    if(typename == 'Float'):
        return 'float'
    if(typename == 'Double'):
        return 'double'
    if(typename == 'Boolean'):
        return 'boolean'
    if(typename == 'String'):
        return 'String'
    return typename

# Function for checking the data type of an element
def check_type_ver2(arg, interface):
    type_list = ['Int8', 'UInt8', 'Int16', 'UInt16', 'Int32', 'UInt32', 'Int64', 'UInt64', 'Double', 'Float', 'Boolean']
    if(arg.type.name in type_list):
        return 1
    elif(arg.type.name == 'String'):
        return 2
    elif(isinstance(arg.type, ast.Reference)):
        if(isinstance(arg.type.reference, ast.Array)):
            if(isinstance(arg.type.reference.type, ast.Reference)):
                if(isinstance(arg.type.reference.type.reference, ast.Struct)):
                    return 9 # Explicit array of struct
                else:
                    raise Exception(f"Unsupported data type: {arg.name}")
            else:
                if(arg.type.reference.name in interface.arrays and len(arg.type.name.split('.')) == 1):
                    return 3 # explicit array in interface
                else:
                    return 6 # explicit array in typeCollection
        elif(isinstance(arg.type.reference, ast.Struct)):
            if(arg.type.reference.name in interface.structs and len(arg.type.name.split('.')) == 1):
                return 4
            else:
                return 7
        elif(isinstance(arg.type.reference, ast.Enumeration)):
            return 8
        # Map = implict struct array with only two elements, key and value
        elif(isinstance(arg.type.reference, ast.Map)):
            #print(arg.name)
            return 11
    elif(arg.type.name is None):
        if(isinstance(arg.type.type, ast.Reference)):
            if(isinstance(arg.type.type.reference, ast.Struct)):
                #print("I10 " + arg.name)
                return 10 # Implict array of struct
            else:
                raise Exception(f"Unsupported data type: {arg.name}")
        else:
            return 5 # implicit array
    
    elif(isinstance(arg.type, ast.Constant)):
        return 15
    elif(arg.type.name == 'ByteBuffer'):
        #print("H")
        #print(dir(arg.type.namespace), arg.type, arg.type.name, arg.type.namespace)
        arg.type = ast.Array(name=None, element_type=ast.Array(name="UInt8", element_type=ast.UInt8()))
        arg.type.namespace = "CommonAPI"
        return 5
    else:
        return -1

# Not in use
def check_type(typename, interface):
    type_list = ['Int8', 'UInt8', 'Int16', 'UInt16', 'Int32', 'UInt32', 'Int64', 'UInt64', 'Double', 'Float', 'Boolean']
    
    if(typename in type_list):
        return 1
    elif(typename == 'String'):
        return 2
    # Explicit arrays that are defined in the interface
    elif(typename in interface.arrays):
        return 3
    # Structs that are defined in the interface
    elif(typename in interface.structs):
        return 4
    # Implicit arrays
    elif(typename is None):
        return 5
    # Types that are defined somewhere else in typeCollection
    else:
        return 6 #than the value is defined at typecollection or some where inside another interface

# Unsigned array 여부 확인용
def isUnsigned(typename):
    type_list = ['UInt8', 'UInt16', 'UInt32', 'UInt64']
    if(typename in type_list):
        return 1
    
# Unsigned array casting 위해서 data type 한 단계 높은 것으로 변환
def upcast_cpp_int(typename):
    if(typename == 'UInt8'):
        return 'int8_t' # aidl does not support short
    elif(typename == 'UInt16' or typename == 'Int16' or typename == 'Int32'):
        return 'int32_t'
    elif(typename == 'UInt32' or typename == 'Int64'):
        return 'int64_t'
    elif(typename == 'UInt64'):
        return 'int64_t'
    elif(typename == 'Int8'):
        return 'int8_t'
    
# struct elements into JNI types
def struct_fields(struct, java_class):
    fields_str = ""
    #fields_construct_str = ""
    for field in struct.values():        
        if(field.type.name is None):
            if(isinstance(field.type.type, ast.Reference)):
                depth_check = field.type
                array_depth = ""
                while(isinstance(depth_check.type, ast.Reference)):
                    array_depth += "["
                    if(isinstance(depth_check.type.reference, ast.Array)):
                        depth_check = depth_check.type.reference
                    else:
                        break
                if(isinstance(field.type.type.reference, ast.Struct)):
                    fields_str += "{}L{}{}JNI${};".format(array_depth, java_class,field.type.type.reference.namespace.name,field.type.type.reference.name)
                elif(isinstance(field.type.reference.type.reference, ast.Array)):
                    fields_str += "{}[{}".format(convert_jni_type(array_depth,field.type.type.reference.name))
            else:
                fields_str += "[{}".format(convert_jni_type(field.type.type.name))
        else:
            if(isinstance(field.type, ast.Reference)):
                if(isinstance(field.type.reference, ast.Array)):
                    if(isinstance(field.type.reference.type, ast.Reference)):
                        depth_check = field.type.reference
                        array_depth = ""
                        while(isinstance(depth_check.type, ast.Reference)):
                            array_depth += "["
                            if(isinstance(depth_check.type.reference, ast.Array)):
                                depth_check = depth_check.type.reference
                            else:
                                break
                        if(isinstance(field.type.reference.type.reference, ast.Struct)):
                            fields_str += "{}L{}{}JNI${};".format(array_depth, java_class,depth_check.type.reference.namespace.name,depth_check.type.reference.name)
                        elif(isinstance(field.type.reference.type.reference, ast.Array)):
                            fields_str += "{}[{}".format(convert_jni_type(array_depth,field.type.reference.type.name))
                    else:
                        if(len(field.type.name.split('.')) > 1 ):
                            fields_str += "[{}".format(convert_jni_type(field.type.reference.type.name))
                        else:
                            fields_str += "[{}".format(convert_jni_type(field.type.reference.type.name))
                elif(isinstance(field.type.reference, ast.Struct)):
                    if(len(field.type.name.split('.')) > 1 ):
                        ### Interface와 TypeCollection에 동일한 이름을 가진 데이터구조가 존재할 경우 interface의 것으로 override 되는 문제점 존재
                        #### ARXML에서 TypeCollection을 지원하지 않음에 따라 더 이상 typeCollection에 대한 코드 업데이트는 하지 않음.
                        fields_str += "L{}{}JNI${};".format(java_class,field.type.name.split('.')[0],field.type.reference.name)
                    else:
                        fields_str += "L{}{}JNI${};".format(java_class,field.type.reference.namespace.name,field.type.reference.name)
                elif(isinstance(field.type.reference, ast.Enumeration)):
                    fields_str += "B"
            else:
                fields_str += convert_jni_type(field.type.name)
    
    # print(fields_str)
    
    return fields_str

# Struct 내에 1차원 배열이 존재할 때 사용, array of String 일 때는 별도로 처리
def array_in_struct_gen(array,attribute_low, field, packages, interface, is_sub = True):
    arr_str = ""
    array_name = array.name
    field_name = capitalize_first_letter(field.name)
    if check_type_ver2(array,interface) == 1:
        type_array = capitalize_first_letter(convert_aidl_type(array.type.name))
    else:
        type_array = "Object"

    type_jni_array = convert_jni_type(array.type.name)
    type_java_array = convert_java_type(array.type.name)
    type_cpp_array = convert_cpp_type(array.type.name)
    type_cpp_array_upcast = upcast_cpp_int(array.type.name)
    env = ""
    indentation = ""
    if(is_sub):
        env = "env"
        indentation = "\t"
    else:
        env = "env"
        indentation = ""
    # cpp_package = packages
    if(isinstance(field.type, ast.Reference)):
    #### parcelable array를 java - C++ 간 연동하는데 어려움이 있어 array의 경우 type을 확인해서 typedef로 지정된 array가 아닌 native 하게 만들어진 것 사용
    ##### AIDL로 자동 생성되는 parcelable에는 constructor 등 CPP에서 필요로 하는 function들이 없음. 만약 있다면 Java 간 casting이 불필요 해지기 때문에 코드가 상당히 간결해질 것임.
        if(len(field.type.name.split('.'))>1):
            arr_str += f"""\n\t\t{indentation}{field.type.name.split('.')[0]}::{array_name} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
        else:
            arr_str += f"""\n\t\t{indentation}{field.type.reference.namespace.name}::{array_name} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
    else:
        arr_str += f"""\n\t\t{indentation}std::vector<{type_cpp_array}> _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
    if(isUnsigned(array.type.name) or array.type.name == "Int16"):
        arr_str += f"""
        {indentation}std::vector<{type_cpp_array_upcast}> _{attribute_low}{field_name}Signed;
        {indentation}_{attribute_low}{field_name}Signed.assign(_{attribute_low}{field_name}.begin(), _{attribute_low}{field_name}.end());
        {indentation}{type_java_array}* {attribute_low}{field_name}Data = static_cast<{type_java_array}*>(_{attribute_low}{field_name}Signed.data());"""
    
    ######
    elif(array.type.name == "String"):
        arr_str += f"""
        {indentation}jsize {attribute_low}{field_name}Length = static_cast<jsize>(_{attribute_low}{field_name}.size());
        {indentation}jstring {attribute_low}{field_name}Str = {env}->NewStringUTF("");
        {indentation}jclass {attribute_low}{field_name}Clazz = {env}->GetObjectClass({attribute_low}{field_name}Str);
        {indentation}jobjectArray {attribute_low}{field_name} = {env}->NewObjectArray({attribute_low}{field_name}Length, {attribute_low}{field_name}Clazz, nullptr);
        {indentation}for(int ssss = 0; ssss < {attribute_low}{field_name}Length; ssss++){{
            {indentation}{attribute_low}{field_name}Str = {env}->NewStringUTF(_{attribute_low}{field_name}[ssss].c_str());
            {indentation}{env}->SetObjectArrayElement({attribute_low}{field_name}, ssss, {attribute_low}{field_name}Str);
        {indentation}}}
        {indentation}{env}->DeleteLocalRef({attribute_low}{field_name}Str);"""
    ######
    
    else:
        arr_str += f"""
    \t{indentation}{type_java_array}* {attribute_low}{field_name}Data = static_cast<{type_java_array}*>(_{attribute_low}{field_name}.data());"""
    
    
    if(array.type.name != "String"):
        arr_str += f"""
    \t{indentation}jsize {attribute_low}{field_name}Length = static_cast<jsize>(_{attribute_low}{field_name}.size());
    \t{indentation}{type_java_array}Array {attribute_low}{field_name} = {env}->New{type_array}Array({attribute_low}{field_name}Length);
    \t{indentation}{env}->Set{type_array}ArrayRegion({attribute_low}{field_name}, 0, {attribute_low}{field_name}Length, {attribute_low}{field_name}Data);"""
    
    return arr_str

## struct의 세부 field에 따라 코드 생성하는 함수
def struct_fields_sub_gen(attribute, interface, packages, java_class, field_name_extends="", is_sub = True, depth=0):
    fields_str = ""
    type_checked = 0
    field_type_java = ""
    field_name = ""
    env = ""
    indentation = ""
    if (is_sub):
        env = "env"
        indentation = "\t"
    else:
        env = "env"
        indentation = ""

    array = ""
    struct = attribute.type.reference
    #interface_cap = capitalize_first_letter(interface.name)
    interface_cap = interface.name
    type_fields_jni = struct_fields(struct=struct.fields,java_class=java_class)
    interface_extension = "JNI"
    
    defined = ""
    if(len(attribute.type.name.split('.')) > 1):
        defined = attribute.type.name.split('.')[0]
    else:
        defined = attribute.type.reference.namespace.name
        
    if(is_sub):
        fields_str += f"""
            jmethodID {defined}{attribute.type.name.split('.')[-1]}MID = {env}->GetMethodID({defined}Clazz, "{capitalize_first_letter(attribute.type.name.split('.')[-1])}ToCPP", "()L{java_class}{defined}{interface_extension}${attribute.type.name.split('.')[-1]};");
            jobject {defined}{attribute.type.name.split('.')[-1]}Instance = {env}->CallObjectMethod({defined}Instance, {defined}{attribute.type.name.split('.')[-1]}MID);
            jclass {defined}{attribute.type.name.split('.')[-1]}Clazz = {env}->GetObjectClass({defined}{attribute.type.name.split('.')[-1]}Instance);"""
    else:
        fields_str += f"""
        jclass {defined}{attribute.type.name.split('.')[-1]}Clazz = {env}->FindClass("{java_class}{attribute.type.reference.namespace.name}{interface_extension}${attribute.type.name.split('.')[-1]}");"""
        
    fields_str += f"""
        {indentation}jmethodID {defined}{attribute.type.name.split('.')[-1]}Constructor = {env}->GetMethodID({defined}{attribute.type.name.split('.')[-1]}Clazz, "<init>", "({type_fields_jni})V");"""
    

    if(field_name_extends == ""):
        attribute_low = field_name_extends + lower_first_letter(attribute.name)
    else:
        attribute_low = field_name_extends + capitalize_first_letter(attribute.name)

    for field in struct.fields.values():
        #type_checked = check_type(field.type.name, interface)
        type_checked = check_type_ver2(field, interface)
        field_name = capitalize_first_letter(field.name)
        ## Primitives without String
        if(type_checked == 1):
            field_type_java = convert_java_type(field.type.name)
            #field_name = capitalize_first_letter(field.name)
            fields_str += f"""
        {indentation}{field_type_java} {attribute_low}{field_name} = static_cast<{field_type_java}>(_{attribute_low}.get{field_name}());"""
        ## String
        elif(type_checked == 2):
            field_type_java = convert_java_type(field.type.name)
            #field_name = capitalize_first_letter(field.name)
            fields_str += f"""
        {indentation}{field_type_java} {attribute_low}{field_name} = {env}->NewStringUTF((_{attribute_low}.get{field_name}()).c_str());"""
        ## Interface Array
        elif(type_checked == 3):
            array = interface.arrays[field.type.name]
            #field_name = capitalize_first_letter(field.name)
            fields_str += array_in_struct_gen(array,attribute_low, field, packages, interface)
        ## Interface Struct
        elif(type_checked == 4):
            defined_field = ""
            if(len(field.type.name.split('.')) > 1):
                defined_field = field.type.name.split('.')[0]
            else:
                defined_field = field.type.reference.namespace.name
            #field_name = capitalize_first_letter(field.name)
            
            fields_str += f"""
        {indentation}{field.type.namespace.name}::{field.type.name} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
            fields_str += struct_fields_sub_gen(field, interface, packages, java_class, attribute_low, is_sub)
            fields_str += f"""
        {indentation}jobject {attribute_low}{field_name} = {env}->NewObject({defined_field}{field.type.name}Clazz, {defined_field}{field.type.name}Constructor"""
            for value in field.type.reference.fields.values():
                fields_str += ", {}{}{}".format(attribute_low,field_name,capitalize_first_letter(value.name))
            fields_str += ");"
        ## None type array
        elif(type_checked == 5):
            array = field.type
            fields_str += array_in_struct_gen(array,attribute_low, field, packages, java_class, is_sub)
        ## TypeColleciton Array
        elif(type_checked == 6):
            array = field.type.reference
            fields_str += array_in_struct_gen(array,attribute_low, field, packages, java_class, is_sub)
        ## TypeColleciton Struct
        elif(type_checked == 7):
            defined_field = ""
            reference_name = field.type.reference.namespace.name #field.type.name.split('.')[0]
            if(len(field.type.name.split('.')) > 1):
                defined_field = field.type.name.split('.')[0]
            else:
                defined_field = field.type.reference.namespace.name
            #field_name = capitalize_first_letter(field.name)
            fields_str += f"""
        {indentation}{reference_name}::{field.type.reference.name} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
            fields_str += struct_fields_sub_gen(field, interface, packages, java_class, attribute_low, is_sub)
            fields_str += f"""
        {indentation}jobject {attribute_low}{field_name} = {env}->NewObject({defined_field}{field.type.reference.name}Clazz, {defined_field}{field.type.reference.name}Constructor"""
            for value in field.type.reference.fields.values():
                fields_str += " ,{}{}{}".format(attribute_low,field_name,capitalize_first_letter(value.name))
            fields_str += ");"
        ## Enumeration
        elif(type_checked == 8):
            reference_name = field.type.reference.namespace.name
            reference_type = field.type.reference.name
            if(not is_sub):
                fields_str += f"""
        {indentation}//jmethodID {reference_name}{reference_type}IntToEnum = {env}->GetMethodID(_{lower_first_letter(interface_cap)}Client->{reference_name}Clazz, "IntTo{capitalize_first_letter(reference_type)}", "(B)L{java_class}{reference_name}{interface_extension}${reference_type};");
        {indentation}{reference_name}::{reference_type} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();
        {indentation}uint8_t _{attribute_low}{field_name}Int = static_cast<uint8_t>(_{attribute_low}{field_name});
        {indentation}jbyte {attribute_low}{field_name} = static_cast<jbyte>(_{attribute_low}{field_name});
        {indentation}//jbyte {attribute_low}{field_name}Int = static_cast<jbyte>(_{attribute_low}{field_name});
        {indentation}//jobject {attribute_low}{field_name} = {env}->CallObjectMethod({reference_name}Instance, {reference_name}{reference_type}IntToEnum, {attribute_low}{field_name}Int);"""
            else:
                fields_str += f"""
        {indentation}//jmethodID {reference_name}{reference_type}IntToEnum = {env}->GetMethodID({reference_name}Clazz, "IntTo{capitalize_first_letter(reference_type)}", "(B)L{java_class}{reference_name}{interface_extension}${reference_type};");
        {indentation}{reference_name}::{reference_type} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();
        {indentation}uint8_t _{attribute_low}{field_name}Int = static_cast<uint8_t>(_{attribute_low}{field_name});
        {indentation}jbyte {attribute_low}{field_name} = static_cast<jbyte>(_{attribute_low}{field_name});
        {indentation}//jbyte {attribute_low}{field_name}Int = static_cast<jbyte>(_{attribute_low}{field_name});
        {indentation}//jobject {attribute_low}{field_name} = {env}->CallObjectMethod({reference_name}Clazz, {reference_name}{reference_type}IntToEnum, {attribute_low}{field_name}Int);"""
        elif(type_checked == 9):
            if(not is_sub):
                fields_str += f"""
        {indentation}{field.type.namespace.name}::{field.type.name} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
                fields_str += complex_array(field, interface, packages, java_class, attribute_low, is_sub=1, is_implicit=False, depth=depth+1)
            else:
                fields_str += complex_array(field, interface, packages, java_class, attribute_low, is_sub=7, is_implicit=False, depth=depth+1)
        elif(type_checked == 10):
            if(not is_sub):
                fields_str += f"""
        {indentation}std::vector<{field.type.type.reference.namespace.name}::{field.type.type.reference.name}> _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
                fields_str += complex_array(field, interface, packages, java_class, attribute_low, is_sub=1, is_implicit=True, depth=depth+1)
            else:
                # print(field_name)
                fields_str += complex_array(field, interface, packages, java_class, attribute_low, is_sub=8, is_implicit=True, depth=depth+1)
        # Map
        elif(type_checked == 11):
            if(not is_sub):
                fields_str += f"""
        {indentation}std::vector<{field.type.type.reference.namespace.name}::{field.type.type.reference.name}> _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
                fields_str += complex_array(field, interface, packages, java_class, attribute_low, is_sub=1, is_implicit=True, depth=depth+1)
            else:
                # print(field_name)
                fields_str += complex_array(field, interface, packages, java_class, attribute_low, is_sub=8, is_implicit=True, depth=depth+1)
            
        else:
            fields_str += ""
        
            ### 중복 선언 제거
    duplicated_line = set()
    unique_lines = []
    lines = fields_str.split('\n')
    for line in lines:
        if line not in duplicated_line or '}' in line:
            unique_lines.append(line)
            duplicated_line.add(line)
        
    fields_str = '\n'.join(unique_lines)
    ###
    
    
    return fields_str

# Set 할 때 필요한 코드 생성 함수, set call 이전과 set call 이후 두 가지 str 반환
def struct_fields_set_gen(attribute, interface, packages, java_class, field_name_extends="", is_complex=False, is_implicit=False, depth=0):
    fields_str = ""
    fields_str_after = ""
    type_checked = 0
    field_type_java = ""
    field_type_jni = ""
    field_name = ""
    array = ""
    # struct = attribute.type.reference
    
    env = "env"
    defined = ""
    interface_extension = "JNI"
   # type_fields_jni = struct_fields(struct=struct.fields, java_class=java_class)
    
    if(not is_implicit):
        if(len(attribute.type.name.split('.')) > 1):
            defined = attribute.type.name.split('.')[0]
        else:
            defined = attribute.type.reference.namespace.name
    else:
        defined = attribute.type.type.reference.namespace.name
    if(field_name_extends == ""):
        attribute_low = field_name_extends + lower_first_letter(attribute.name)
    else:
        attribute_low = field_name_extends + capitalize_first_letter(attribute.name)
            
    if(is_complex and not is_implicit):
        attribute = attribute.type.reference    
    elif(is_implicit):
        attribute = attribute.type
    
    for field in attribute.type.reference.fields.values():
        field_name = capitalize_first_letter(field.name)
        field_name_low = field.name
        type_checked = check_type_ver2(field, interface)
        if(type_checked == 1):
            field_type_jni = convert_jni_type(field.type.name)
            field_type_java = convert_java_type(field.type.name)
            field_type_cpp = convert_cpp_type(field.type.name)
            #field_name = capitalize_first_letter(field.name)
            #field_name_low = lower_first_letter(field.name)
            fields_str += f"""\n\t\tjfieldID {attribute_low}{field_name}FID = {env}->GetFieldID({defined}{attribute.type.reference.name}Clazz, \"{field_name_low}\", \"{field_type_jni}\");"""
            fields_str += f"""\n\t\t{field_type_java} {attribute_low}{field_name} = {env}->Get{capitalize_first_letter(convert_aidl_type(field.type.name))}Field({attribute_low}, {attribute_low}{field_name}FID);"""
            fields_str += f"""
        _{attribute_low}.set{field_name}(static_cast<{field_type_cpp}>({attribute_low}{field_name}));"""
            fields_str_after += f"""\n\t\t{attribute_low}{field_name} = static_cast<{field_type_java}>(_{attribute_low}Response.get{field_name}());"""
        elif(type_checked == 2):
            field_type_jni = convert_jni_type(field.type.name)
            field_type_java = convert_java_type(field.type.name)
            #field_name = capitalize_first_letter(field.name)
            #field_name_low = lower_first_letter(field.name)
            fields_str += f"""\n\t\tjfieldID {attribute_low}{field_name}FID = {env}->GetFieldID({defined}{attribute.type.reference.name}Clazz, \"{field_name_low}\", \"{field_type_jni}\");"""
            # fields_str += f"""\n\t\tjstring {attribute_low}{field_name} = static_cast<jstring>(env->GetObjectField({attribute_low},{attribute_low}{field_name}FID);"""
            fields_str += f"""\n\t\tjstring {attribute_low}{field_name} = (jstring)({env}->GetObjectField({attribute_low},{attribute_low}{field_name}FID));"""
            fields_str += f"""\n\t\tconst char* _{attribute_low}{field_name}Temp = {env}->GetStringUTFChars({attribute_low}{field_name}, nullptr);"""
            fields_str += f"""\n\t\tstd::string _{attribute_low}{field_name}(_{attribute_low}{field_name}Temp);"""
            fields_str += f"""
        _{attribute_low}.set{field_name}(_{attribute_low}{field_name});"""
            fields_str_after += f"""\n\t\t{attribute_low}{field_name} = {env}->NewStringUTF((_{attribute_low}Response.get{field_name}()).c_str());"""
        elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
            if(type_checked == 3):
                array = interface.arrays[field.type.name]
            elif(type_checked == 5):
                array = field.type
            elif(type_checked == 6):
                array = field.type.reference
            type_jni_array = convert_jni_type(array.type.name)
            type_java_array = convert_java_type(array.type.name)
            type_cpp_array = convert_cpp_type(array.type.name)
            #field_name = capitalize_first_letter(field.name)
            #field_name_low = lower_first_letter(field.name)
            if(array.type.name != "String"):
                fields_str += f"""\n\t\tjfieldID {attribute_low}{field_name}FID = {env}->GetFieldID({defined}{attribute.type.reference.name}Clazz, \"{field_name_low}\", \"[{type_jni_array}\");
        {type_java_array}Array {attribute_low}{field_name} = reinterpret_cast<{type_java_array}Array>({env}->GetObjectField({attribute_low},{attribute_low}{field_name}FID));
        {type_java_array}* {attribute_low}{field_name}Data = {env}->Get{capitalize_first_letter(convert_aidl_type(array.type.name))}ArrayElements({attribute_low}{field_name}, nullptr);
        jsize {attribute_low}{field_name}Length = {env}->GetArrayLength({attribute_low}{field_name});"""
            ## String array, set
            else:
                string_array_gen = ""
                if(type_checked == 3):
                    string_array_gen = f"{field.type.namespace.name}::{field.type.name}"
                elif(type_checked == 5):
                    string_array_gen = f"std::vector<std::string>"
                fields_str += f"""\n\t\tjfieldID {attribute_low}{field_name}FID = {env}->GetFieldID({defined}{attribute.type.reference.name}Clazz, \"{field_name_low}\", \"[{type_jni_array}\");
        jobjectArray {attribute_low}{field_name} = reinterpret_cast<jobjectArray>({env}->GetObjectField({attribute_low}, {attribute_low}{field_name}FID));
        jsize {attribute_low}{field_name}Length = {env}->GetArrayLength({attribute_low}{field_name});
        jstring {attribute_low}{field_name}Str = {env}->NewStringUTF("");
        {string_array_gen} _{attribute_low}{field_name};
        for(int s = 0; s < {attribute_low}{field_name}Length; s++){{
            {attribute_low}{field_name}Str = (jstring){env}->GetObjectArrayElement({attribute_low}{field_name}, s);
            const char *{attribute_low}{field_name}Cstr = {env}->GetStringUTFChars({attribute_low}{field_name}Str, nullptr);
            _{attribute_low}{field_name}.push_back(std::string({attribute_low}{field_name}Cstr));
        }}"""
            ##
            if(type_checked == 3 and array.type.name != "String"):
                fields_str += f"""\n\t\t/*{packages}::*/{field.type.namespace.name}::{field.type.name} _{attribute_low}{field_name}({attribute_low}{field_name}Data, {attribute_low}{field_name}Data + {attribute_low}{field_name}Length);"""
            elif(type_checked == 5 and array.type.name != "String"):
                fields_str += f"""\n\t\tstd::vector<{type_cpp_array}> _{attribute_low}{field_name}({attribute_low}{field_name}Data, {attribute_low}{field_name}Data + {attribute_low}{field_name}Length);"""
            elif(type_checked == 6):
                fields_str += f"""\n\t\t/*{packages}::*/{field.type.reference.namespace.name}::{field.type.reference.name} _{attribute_low}{field_name}({attribute_low}{field_name}Data, {attribute_low}{field_name}Data + {attribute_low}{field_name}Length);"""
            fields_str += f"""\n\t\t_{attribute_low}.set{field_name}(_{attribute_low}{field_name});"""
            temp = ""
            temp_cast = ""
            if(isUnsigned(array.type.name) or array.type.name == "Int16"):
                temp += "Signed"
                temp_cast += f"""
        std::vector<{upcast_cpp_int(array.type.name)}> _{attribute_low}{field_name}Signed;
        _{attribute_low}{field_name}Signed.assign(_{attribute_low}{field_name}.begin(), _{attribute_low}{field_name}.end());"""
            if(array.type.name != "String"):
                fields_str_after += f"""\n\t\t_{attribute_low}{field_name} = _{attribute_low}Response.get{field_name}();{temp_cast}
        {attribute_low}{field_name}Data = static_cast<{type_java_array}*>(_{attribute_low}{field_name}{temp}.data());
        {attribute_low}{field_name}Length = static_cast<jsize>(_{attribute_low}{field_name}{temp}.size());
        {env}->Set{capitalize_first_letter(convert_aidl_type(array.type.name))}ArrayRegion({attribute_low}{field_name}, 0, {attribute_low}{field_name}Length, {attribute_low}{field_name}Data);"""
            ## String array, get
            else:
                fields_str_after += f"""
        jclass {attribute_low}{field_name}StrClazz = {env}->GetObjectClass({attribute_low}{field_name}Str);
        jobjectArray {attribute_low}{field_name} = {env}->NewObjectArray({attribute_low}{field_name}Length, {attribute_low}{field_name}StrClazz, nullptr);
        for(int s = 0; s < {attribute_low}{field_name}Length; s++){{
            {attribute_low}{field_name}Str = {env}->NewStringUTF(_{attribute_low}{field_name}[s].c_str());
            {env}->SetObjectArrayElement({attribute_low}{field_name}, s, {attribute_low}{field_name}Str);
        }}
        {env}->DeleteLocalRef({attribute_low}{field_name}Str);"""
            ##
        ## interface struct
        elif(type_checked == 4 or type_checked == 7):
            fields_str_temp = ""
            fields_str_after_temp = ""
            type_fields_jni = struct_fields(struct=field.type.reference.fields, java_class=java_class)
            defined_field = ""
            if(len(field.type.name.split('.')) > 1):
                defined_field = field.type.name.split('.')[0]
            else:
                defined_field = field.type.reference.namespace.name
            fields_str += f"""\n\t\tjfieldID {attribute_low}{field_name}FID = {env}->GetFieldID({defined}{attribute.type.reference.name}Clazz, \"{field_name_low}\", \"L{java_class}{defined_field}{interface_extension}${field.type.name.split('.')[-1]};\");
        jobject {attribute_low}{field_name} = {env}->GetObjectField({attribute_low}, {attribute_low}{field_name}FID);
        jclass {defined_field}{field.type.reference.name}Clazz = {env}->GetObjectClass({attribute_low}{field_name});
        /*{packages}::*/{field.type.reference.namespace.name}::{field.type.reference.name} _{attribute_low}{field_name};
        /*{packages}::*/{field.type.reference.namespace.name}::{field.type.reference.name} _{attribute_low}{field_name}Response;"""
            fields_str_after += f"""\n\t\t_{attribute_low}{field_name}Response = _{attribute_low}Response.get{field_name}();
        jmethodID {defined_field}{field.type.reference.name}Constructor = {env}->GetMethodID({defined_field}{field.type.reference.name}Clazz, "<init>", "({type_fields_jni})V");"""
            fields_str_temp, fields_str_after_temp = struct_fields_set_gen(field, interface, packages, java_class, field_name_extends=attribute_low)
            fields_str += fields_str_temp
            fields_str_after += fields_str_after_temp
            fields_str += f"""\n\t\t_{attribute_low}.set{field_name}(_{attribute_low}{field_name});"""
            fields_str_after += f"""\n\t\t{attribute_low}{field_name} = {env}->NewObject({defined_field}{field.type.reference.name}Clazz, {defined_field}{field.type.reference.name}Constructor"""
            for value in field.type.reference.fields.values():
                fields_str_after += ", {}{}{}".format(attribute_low,field_name,capitalize_first_letter(value.name))
            fields_str_after += ");"
        elif(type_checked == 8):
            reference_cap = (field.type.reference.namespace.name)
            reference_type = field.type.reference.name
            fields_str += f"""
        //jfieldID {attribute_low}{field_name}FID = {env}->GetFieldID({defined}{attribute.type.reference.name}Clazz, "{field_name_low}", "L{java_class}{reference_cap}{interface_extension}${field.type.name};");
        //jobject {attribute_low}{field_name} = {env}->GetObjectField({attribute_low}, {attribute_low}{field_name}FID);
        jfieldID {attribute_low}{field_name}FID = {env}->GetFieldID({defined}{attribute.type.reference.name}Clazz, "{field.name}", "B");
        jbyte {attribute_low}{field_name} = {env}->GetByteField({attribute_low}, {attribute_low}{field_name}FID);
        //jmethodID {reference_cap}{reference_type}IntToEnum = {env}->GetMethodID(_{lower_first_letter(interface.name)}Client->{reference_cap}Clazz, "IntTo{capitalize_first_letter(reference_type)}", "(B)L{java_class}{reference_cap}{interface_extension}${reference_type};");
        //jmethodID {reference_cap}{reference_type}EnumToInt = {env}->GetMethodID(_{lower_first_letter(interface.name)}Client->{reference_cap}Clazz, "{capitalize_first_letter(reference_type)}ToInt", "(L{java_class}{reference_cap}{interface_extension}${reference_type};)B");
        //jbyte {attribute_low}{field_name_low}Int = {env}->CallByteMethod({reference_cap}Instance, {reference_cap}{reference_type}EnumToInt, {attribute_low}{field_name});
        uint8_t _{attribute_low}{field_name}Int = static_cast<uint8_t>({attribute_low}{field_name});
        {reference_cap}::{reference_type} _{attribute_low}{field_name} = {reference_cap}::{reference_type}::Literal(_{attribute_low}{field_name}Int);
        _{attribute_low}.set{field_name}(_{attribute_low}{field_name});"""
            fields_str_after += f"""
        _{attribute_low}{field_name}Int = static_cast<uint8_t>(_{attribute_low}Response.get{field_name}());
        {attribute_low}{field_name} = static_cast<jbyte>(_{attribute_low}{field_name}Int);
        //{attribute_low}{field_name} = {env}->CallObjectMethod({reference_cap}Instance, {reference_cap}{reference_type}IntToEnum, {attribute_low}{field_name}Int);"""
        ### Complex array
        elif(type_checked == 9):
            defined_field = field.type.reference.type.reference.namespace.name
            defined = field.type.reference.type.reference.namespace.name
            fields_str += f"""\n\t\tjfieldID {attribute_low}{field_name}FID = {env}->GetFieldID({defined}{attribute.type.reference.name}Clazz, \"{field_name_low}\", \"[L{java_class}{defined_field}{interface_extension}${field.type.reference.type.reference.name};\");
        jobjectArray {attribute_low}{field_name} = (jobjectArray){env}->GetObjectField({attribute_low}, {attribute_low}{field_name}FID);"""
            fields_str += complex_array(field, interface, packages, java_class, field_name_extends=attribute_low, is_sub = 3, is_implicit=False, depth=depth+1)
            fields_str += f"""_{attribute_low}.set{field_name}(_{attribute_low}{field_name});"""
            fields_str_after += f"""\n\t\t{defined}::{field.type.reference.type.reference.name} _{attribute_low}{field_name}Response = _{attribute_low}Response.get{field_name}();
            """
            fields_str_after += complex_array(field, interface, packages, java_class, field_name_extends=attribute_low, is_sub = 2, is_implicit=False, depth=depth+1)
            
        elif(type_checked == 10):
            defined_field = field.type.type.reference.namespace.name
            defined = field.type.type.reference.namespace.name
            fields_str += f"""\n\t\tjfieldID {attribute_low}{field_name}FID = {env}->GetFieldID({defined}{attribute.type.reference.name}Clazz, \"{field_name_low}\", \"[L{java_class}{defined_field}{interface_extension}${field.type.type.reference.name};\");
        jobjectArray {attribute_low}{field_name} = (jobjectArray){env}->GetObjectField({attribute_low}, {attribute_low}{field_name}FID);"""
            fields_str += complex_array(field, interface, packages, java_class, field_name_extends=attribute_low, is_sub = 3, is_implicit=True, depth=depth+1)
            fields_str += f"""_{attribute_low}.set{field_name}(_{attribute_low}{field_name});"""
            fields_str_after += f"""\n\t\tstd::vector<{defined}::{field.type.type.reference.name}> _{attribute_low}{field_name}Response = _{attribute_low}Response.get{field_name}();
            """
            fields_str_after += complex_array(field, interface, packages, java_class, field_name_extends=attribute_low, is_sub = 2, is_implicit=True, depth=depth+1) 
        # Map
        elif(type_checked == 11):
            defined_field = field.type.type.reference.namespace.name
            defined = field.type.type.reference.namespace.name
            fields_str += f"""\n\t\tjfieldID {attribute_low}{field_name}FID = {env}->GetFieldID({defined}{attribute.type.reference.name}Clazz, \"{field_name_low}\", \"[L{java_class}{defined_field}{interface_extension}${field.type.type.reference.name};\");
        jobjectArray {attribute_low}{field_name} = (jobjectArray){env}->GetObjectField({attribute_low}, {attribute_low}{field_name}FID);"""
            fields_str += complex_array(field, interface, packages, java_class, field_name_extends=attribute_low, is_sub = 3, is_implicit=True, depth=depth+1)
            fields_str += f"""_{attribute_low}.set{field_name}(_{attribute_low}{field_name});"""
            fields_str_after += f"""\n\t\tstd::vector<{defined}::{field.type.type.reference.name}> _{attribute_low}{field_name}Response = _{attribute_low}Response.get{field_name}();
            """
            fields_str_after += complex_array(field, interface, packages, java_class, field_name_extends=attribute_low, is_sub = 2, is_implicit=True, depth=depth+1) 
        
    ### 중복 선언 제거 fields_str
    duplicated_line = set()
    unique_lines = []
    duplicated_words = []
    lines = fields_str.split('\n')
    for line in lines:
        if line not in duplicated_line or '}' in line:
            words = line.split()
            if(len(words) >= 2):
                if words[0] in ["jclass", "jmethodID"] and ("Clazz" or "Constructor" or "MID" in words[1]):
                    if(words[0],words[1]) not in duplicated_words:
                        duplicated_words.append((words[0], words[1]))
                        unique_lines.append(line)
                        duplicated_line.add(line)
                else:
                    duplicated_line.add(line)
                    unique_lines.append(line)
            else:
                duplicated_line.add(line)            
                unique_lines.append(line)

    fields_str = '\n'.join(unique_lines)
    ###
    ### fields_str_after
    duplicated_line = set()
    unique_lines = []
    duplicated_words = []
    lines = fields_str_after.split('\n')
    for line in lines:
        if line not in duplicated_line or '}' in line:
            words = line.split()
            if(len(words) >= 2):
                if words[0] in ["jclass", "jmethodID"] and ("Clazz" or "Constructor" or "MID" in words[1]):
                    if(words[0],words[1]) not in duplicated_words:
                        duplicated_words.append((words[0], words[1]))
                        unique_lines.append(line)
                        duplicated_line.add(line)
                else:
                    duplicated_line.add(line)
                    unique_lines.append(line)
            else:
                duplicated_line.add(line)            
                unique_lines.append(line)

    fields_str_after = '\n'.join(unique_lines)
    ###
       
    return fields_str, fields_str_after

##################  Complex Array Code Gen  ###################
def struct_fields_for_complex_array(attribute, interface, packages, java_class, field_name_extends="", is_sub = True, is_implicit=False, is_get=False, depth=0, is_method_out = False):
    fields_str = ""
    type_checked = 0
    field_type_java = ""
    field_name = ""
    env = ""
    indentation = ""
    if (is_sub):
        env = "env"
        indentation = "\t"
    else:
        env = "env"
        indentation = ""

    array = ""
    # struct = attribute.type.reference
    struct = attribute
    if(is_implicit):
        struct = attribute.type.type.reference
    else:
        struct = attribute.type.reference.type.reference
    #interface_cap = capitalize_first_letter(interface.name)
    interface_cap = interface.name
    type_fields_jni = struct_fields(struct=struct.fields,java_class=java_class)
    interface_extension = "JNI"
    

    if(field_name_extends == ""):
        attribute_low = field_name_extends + lower_first_letter(attribute.name)
    else:
        attribute_low = field_name_extends + capitalize_first_letter(attribute.name)

    for field in struct.fields.values():
        #type_checked = check_type(field.type.name, interface)
        type_checked = check_type_ver2(field, interface)
        field_name = capitalize_first_letter(field.name)
        ## Primitives without String
        if(type_checked == 1):
            field_type_java = convert_java_type(field.type.name)
            #field_name = capitalize_first_letter(field.name)
            fields_str += f"""
        {indentation}{field_type_java} {attribute_low}{field_name} = static_cast<{field_type_java}>(_{attribute_low}.get{field_name}());"""
        ## String
        elif(type_checked == 2):
            field_type_java = convert_java_type(field.type.name)
            #field_name = capitalize_first_letter(field.name)
            fields_str += f"""
        {indentation}{field_type_java} {attribute_low}{field_name} = {env}->NewStringUTF((_{attribute_low}.get{field_name}()).c_str());"""
        ## Interface Array
        elif(type_checked == 3):
            array = interface.arrays[field.type.name]
            #field_name = capitalize_first_letter(field.name)
            fields_str += array_in_struct_gen(array,attribute_low, field, packages, interface)
        ## Interface Struct
        elif(type_checked == 4):
            defined_field = ""
            if(len(field.type.name.split('.')) > 1):
                defined_field = field.type.name.split('.')[0]
            else:
                defined_field = field.type.reference.namespace.name
            #field_name = capitalize_first_letter(field.name)
            
            fields_str += f"""
        {indentation}{field.type.namespace.name}::{field.type.name} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
            ############ 기존 함수 call할 때 세부적으로 분류해서 진행
            if((is_sub and is_get) or is_method_out):
                fields_str += struct_fields_sub_gen(field, interface, packages, java_class, attribute_low, False)
            else:
                fields_str += struct_fields_sub_gen(field, interface, packages, java_class, attribute_low, is_sub)
            ############ 
            fields_str += f"""
        {indentation}jobject {attribute_low}{field_name} = {env}->NewObject({defined_field}{field.type.name}Clazz, {defined_field}{field.type.name}Constructor"""
            for value in field.type.reference.fields.values():
                fields_str += ", {}{}{}".format(attribute_low,field_name,capitalize_first_letter(value.name))
            fields_str += ");"
        ## None type array
        elif(type_checked == 5):
            array = field.type
            fields_str += array_in_struct_gen(array,attribute_low, field, packages, java_class, is_sub)
        ## TypeColleciton Array
        elif(type_checked == 6):
            array = field.type.reference
            fields_str += array_in_struct_gen(array,attribute_low, field, packages, java_class, is_sub)
        ## TypeColleciton Struct
        elif(type_checked == 7):
            defined_field = ""
            reference_name = field.type.reference.namespace.name #field.type.name.split('.')[0]
            if(len(field.type.name.split('.')) > 1):
                defined_field = field.type.name.split('.')[0]
            else:
                defined_field = field.type.reference.namespace.name
            #field_name = capitalize_first_letter(field.name)
            fields_str += f"""
        {indentation}{reference_name}::{field.type.reference.name} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
            if((is_sub and is_get) or is_method_out):
                fields_str += struct_fields_sub_gen(field, interface, packages, java_class, attribute_low, False)
            else:
                fields_str += struct_fields_sub_gen(field, interface, packages, java_class, attribute_low, is_sub)
            fields_str += f"""
        {indentation}jobject {attribute_low}{field_name} = {env}->NewObject({defined_field}{field.type.reference.name}Clazz, {defined_field}{field.type.reference.name}Constructor"""
            for value in field.type.reference.fields.values():
                fields_str += " ,{}{}{}".format(attribute_low,field_name,capitalize_first_letter(value.name))
            fields_str += ");"
        ## Enumeration
        elif(type_checked == 8):
            reference_name = field.type.reference.namespace.name
            reference_type = field.type.reference.name
            if(not is_sub):
                fields_str += f"""
        {indentation}{reference_name}::{reference_type} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();
        {indentation}uint8_t _{attribute_low}{field_name}Int = static_cast<uint8_t>(_{attribute_low}{field_name});
        {indentation}jbyte {attribute_low}{field_name} = static_cast<jbyte>(_{attribute_low}{field_name});"""
            else:
                fields_str += f"""
        {indentation}{reference_name}::{reference_type} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();
        {indentation}uint8_t _{attribute_low}{field_name}Int = static_cast<uint8_t>(_{attribute_low}{field_name});
        {indentation}jbyte {attribute_low}{field_name} = static_cast<jbyte>(_{attribute_low}{field_name});"""
        elif(type_checked == 9):
            if(not is_get):
                # fields_str += f"""
        # {indentation}{field.type.namespace.name}::{field.type.name} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
                fields_str += complex_array(field, interface, packages, java_class, attribute_low, 7, is_implicit=False, depth=depth+1)
            else:
                if(not is_method_out):
                    fields_str += f"""
        {indentation}{field.type.namespace.name}::{field.type.name} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
                    fields_str += complex_array(field, interface, packages, java_class, attribute_low, 1, is_implicit=False, depth=depth+1)
                else:
                    fields_str += f"""
        {indentation}{field.type.namespace.name}::{field.type.name} _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
                    fields_str += complex_array(field, interface, packages, java_class, attribute_low, 5, is_implicit=False, depth=depth+1)
        elif(type_checked == 10):
            if(not is_get):
        #         fields_str += f"""
        # {indentation}std::vector<{field.type.type.reference.namespace.name}::{field.type.type.reference.name}> _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
                fields_str += complex_array(field, interface, packages, java_class, attribute_low, 8, is_implicit=True, depth=depth+1)
            else:
                if(not is_method_out):
                    fields_str += f"""
        {indentation}std::vector<{field.type.type.reference.namespace.name}::{field.type.type.reference.name}> _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
                    fields_str += complex_array(field, interface, packages, java_class, attribute_low, 1, is_implicit=True, depth=depth+1)
                else:
                    fields_str += f"""
        {indentation}std::vector<{field.type.type.reference.namespace.name}::{field.type.type.reference.name}> _{attribute_low}{field_name} = _{attribute_low}.get{field_name}();"""
                    fields_str += complex_array(field, interface, packages, java_class, attribute_low, 5, is_implicit=True, depth=depth+1)
        else:
            fields_str += ""
            
        ### 중복 선언 제거
    duplicated_line = set()
    unique_lines = []
    lines = fields_str.split('\n')
    for line in lines:
        if line not in duplicated_line or '}' in line:
            unique_lines.append(line)
            duplicated_line.add(line)
        
    fields_str = '\n'.join(unique_lines)
    ###
    
    return fields_str


def complex_array(attribute, interface, packages, java_class, field_name_extends="", is_sub=0, is_implicit=False, depth=0):
    src_str = ""
    
    # Complex array 는 array of (implicit / explicit) array 또는 array of struct 또는 array of enum 4개 중 하나임. 
    # Map이 추가된다면 1개 더 생김
    ## Explicit array는 3, implicit array는 5, Structure는 4, Enum은 8
    ## TypeCollection에 해당하는 내용들은 제외, 사유: ARXML에서 미지원
    attribute_type = check_type_ver2(attribute, interface)
    array_type = 0
    if(attribute_type == 9):
        array_type = check_type_ver2(attribute.type.reference, interface)
    elif(attribute_type == 10):
        array_type = check_type_ver2(attribute.type, interface)
    ########## 여기서부터 Map -> 계획 변경, 미사용 ######################
    # elif(attribute_type == 11):
    #     ## Map 인 경우 attribute이 참조하는 type을 새롭게 새롭게 만들어야 함 
    #     print("MAP")
    #     # map_to_struct = ast.Struct(attribute.type.reference.name) 
    #     # field_key = ast.StructField("key", attribute.type.reference.key_type)
    #     # field_value = ast.StructField("value", attribute.type.reference.value_type)
    #     # map_to_struct.fields.update({field_key.name:field_key.type})
    #     # map_to_struct.fields.update({field_value.name:field_value.type})
    #     # map_array = ast.Array(attribute.name, None)
    #     # map_array.type = map_to_struct
    #     # attribute.type = map_array
    #     # 이대로 못 씀, 사유: commonapi 에서 지원하는 struct는 get set 함수로 원소들 값 읽고 쓰는데 map은 그게 지원이 안 됨 그래서 코드 재사용 못 함
    
    attribute_name = attribute.name
    attribute_cap = capitalize_first_letter(attribute.name)
    attribute_low = lower_first_letter(attribute.name)
    interface_cap = capitalize_first_letter(interface.name)
    interface_extension = "JNI"
    indentation = "\t"
    if(depth != 0):
        indentation = indentation * depth
    for_loop_depth = "i" * depth
    
    # is_sub 0: sub / 1: get / 2: after set call / 3: before set call / 4: broadcast / 5: method out_args / 6: method in_args / 
    # Iterative Sub 7: struct having an explict struct array / 8: struct having an implict struct array
    # Iterative Get 9 / 10
    # Iterative Set 11 /12 
    if(is_sub != 0 and is_sub != 4 and is_sub != 7 and is_sub != 8 and is_sub != 9 and is_sub != 10):
        indentation = ""

    env = "env"
    
    # For a struct has a complex array or a complex array of complex array
    if(field_name_extends == ""):
        attribute_low = field_name_extends + lower_first_letter(attribute.name)
    else:
        attribute_low = field_name_extends + capitalize_first_letter(attribute.name)
    
    out = ""
    if(is_sub == 5):
        out = "out"
    
    if(array_type == 4):
        struct = attribute
        if(is_implicit):
            struct = attribute.type.type.reference
        else:
            struct = attribute.type.reference.type.reference
        struct_name = struct.name
        struct_ref = struct.namespace.name
        struct_jni = f"[L{java_class}{struct_ref}{interface_extension}${struct_name};"
        struct_fields_jni = struct_fields(struct=struct.fields, java_class=java_class)
        struct_fields_arg = ""
        for field in struct.fields.values():
            struct_fields_arg += f", {attribute_low}{capitalize_first_letter(field.name)}"
        
        struct_for_loop = ""
        if(is_sub != 3 and is_sub != 6):
            if(is_sub == 0 or is_sub == 4 or is_sub == 7 or is_sub == 8):
                struct_for_loop = struct_fields_for_complex_array(attribute, interface, packages=packages, java_class=java_class, field_name_extends=field_name_extends, is_sub=True, is_implicit=is_implicit, is_get=False, depth=depth)
            elif(is_sub == 5):
                struct_for_loop = struct_fields_for_complex_array(attribute, interface, packages=packages, java_class=java_class, field_name_extends=field_name_extends, is_sub=True, is_implicit=is_implicit, is_get=True, depth=depth, is_method_out=True)
            else:
                struct_for_loop = struct_fields_for_complex_array(attribute, interface, packages=packages, java_class=java_class, field_name_extends=field_name_extends, is_sub=True, is_implicit=is_implicit, is_get=True, depth=depth)
            if(is_sub == 2):
                struct_for_loop = struct_for_loop.replace(f"_{attribute_low}.get", f"_{attribute_low}Response[i{for_loop_depth}].get")
            else:
                struct_for_loop = struct_for_loop.replace(f"_{attribute_low}.get", f"_{attribute_low}[i{for_loop_depth}].get")
            struct_for_loop_lines = struct_for_loop.split('\n')
            if(is_sub == 0):
                struct_for_loop_lines = ['\t' + indentation[:-1] + line for line in struct_for_loop_lines]
            struct_for_loop = '\n'.join(struct_for_loop_lines)
        
        struct_set_for_loop = ""
        struct_set_after = ""
        if(is_sub == 3 or is_sub == 6):
            struct_set_for_loop, struct_set_after = struct_fields_set_gen(attribute, interface, packages, java_class, field_name_extends=field_name_extends, is_complex=True, is_implicit=is_implicit, depth=depth)
            struct_set_for_loop = struct_set_for_loop.replace(f"_{attribute_low}.set", f"_{attribute_low}[i{for_loop_depth}].set")
            struct_set_for_loop = struct_set_for_loop.replace(f"{attribute_low},", f"{attribute_low}Obj,")
            struct_for_loop_lines = struct_set_for_loop.split('\n')
            struct_for_loop_lines = ['\t' + indentation[:-1] + line for line in struct_for_loop_lines]
            struct_set_for_loop = '\n'.join(struct_for_loop_lines)

        if(is_sub == 0):
            src_str += f"""
            
        {indentation}jmethodID {attribute_cap}MID = {env}->GetMethodID({interface_cap}Clazz, "subAttribute{attribute_cap}Handler", "({struct_jni})V");
        {indentation}jmethodID {struct_ref}{struct_name}MID = {env}->GetMethodID({interface_cap}Clazz, "{capitalize_first_letter(struct_name)}ToCPP", "()L{java_class}{struct_ref}JNI${struct_name};");
        {indentation}jobject {struct_ref}{struct_name}Instance = {env}->CallObjectMethod({interface_cap}Instance, {struct_ref}{struct_name}MID);
        {indentation}jclass {struct_ref}{struct_name}Clazz = {env}->GetObjectClass({struct_ref}{struct_name}Instance);
        {indentation}jmethodID {struct_ref}{struct_name}Constructor = {env}->GetMethodID({struct_ref}{struct_name}Clazz, "<init>", "({struct_fields_jni})V");
        {indentation}"""
        elif(is_sub == 4):
            src_str += f"""
            
        {indentation}jmethodID {struct_ref}{struct_name}MID = {env}->GetMethodID({interface_cap}Clazz, "{capitalize_first_letter(struct_name)}ToCPP", "()L{java_class}{struct_ref}JNI${struct_name};");
        {indentation}jobject {struct_ref}{struct_name}Instance = {env}->CallObjectMethod({interface_cap}Instance, {struct_ref}{struct_name}MID);
        {indentation}jclass {struct_ref}{struct_name}Clazz = {env}->GetObjectClass({struct_ref}{struct_name}Instance);
        {indentation}jmethodID {struct_ref}{struct_name}Constructor = {env}->GetMethodID({struct_ref}{struct_name}Clazz, "<init>", "({struct_fields_jni})V");
        {indentation}"""
        
        elif(is_sub == 1):
            src_str += f"""
            
        {indentation}jclass {struct_ref}{struct_name}Clazz = {env}->FindClass("{java_class}{struct_ref}JNI${struct_name}");
        {indentation}jmethodID {struct_ref}{struct_name}Constructor = {env}->GetMethodID({struct_ref}{struct_name}Clazz, "<init>", "({struct_fields_jni})V");"""
        
        #### method 에서 in out이 같을 때 문제가 생기니 유의
        elif(is_sub == 5):
            src_str += f"""
        
        {indentation}jclass {out}{struct_ref}{struct_name}Clazz = {env}->FindClass("{java_class}{struct_ref}JNI${struct_name}");
        {indentation}jmethodID {out}{struct_ref}{struct_name}Constructor = {env}->GetMethodID({out}{struct_ref}{struct_name}Clazz, "<init>", "({struct_fields_jni})V");"""
        
        elif(is_sub == 7 or is_sub == 8):
            src_str += f"""
        
        {indentation}jmethodID {struct_ref}{struct_name}MID = {env}->GetMethodID({interface_cap}Clazz, "{capitalize_first_letter(struct_name)}ToCPP", "()L{java_class}{struct_ref}JNI${struct_name};");
        {indentation}jobject {struct_ref}{struct_name}Instance = {env}->CallObjectMethod({interface_cap}Instance, {struct_ref}{struct_name}MID);
        {indentation}jclass {struct_ref}{struct_name}Clazz = {env}->GetObjectClass({struct_ref}{struct_name}Instance);
        {indentation}jmethodID {struct_ref}{struct_name}Constructor = {env}->GetMethodID({struct_ref}{struct_name}Clazz, "<init>", "({struct_fields_jni})V");"""
            if(is_sub == 7): #### Get에 [i] 있었는데 안 맞아서 지움. 혹시라도 문제 생기면 확인할 것
                src_str += f"""
        {indentation}{struct_ref}::{struct_name} _{attribute_low} = _{field_name_extends}.get{capitalize_first_letter(attribute.name)}();"""
            if(is_sub == 8): #### Get에 [i] 있었는데 안 맞아서 지움. 혹시라도 문제 생기면 확인할 것
                src_str += f"""
        {indentation}std::vector<{struct_ref}::{struct_name}> _{attribute_low} = _{field_name_extends}.get{capitalize_first_letter(attribute.name)}();"""
            src_str += f"""
        {indentation}jsize {attribute_low}Length = static_cast<jsize>(_{attribute_low}.size());
        {indentation}jobjectArray {attribute_low} = {env}->NewObjectArray({attribute_low}Length, {struct_ref}{struct_name}Clazz, nullptr);
        {indentation}"""
        
        if(is_sub < 2 or is_sub == 4 or is_sub == 5):
            src_str += f"""
        {indentation}jsize {attribute_low}Length = static_cast<jsize>(_{attribute_low}.size());
        {indentation}jobjectArray {attribute_low} = {env}->NewObjectArray({attribute_low}Length, {out}{struct_ref}{struct_name}Clazz, nullptr);
        {indentation}"""
        elif(is_sub == 2):
            src_str += f"""
        {indentation}jobjectArray {attribute_low}Response = {env}->NewObjectArray({attribute_low}Length, {struct_ref}{struct_name}Clazz, nullptr);
        {indentation}jmethodID {struct_ref}{struct_name}Constructor = {env}->GetMethodID({struct_ref}{struct_name}Clazz, "<init>", "({struct_fields_jni})V");
        {indentation}"""
        elif(is_sub == 3):
            src_str += f"""
        {indentation}jobject {attribute_low}Obj = {env}->GetObjectArrayElement({attribute_low}, 0);
        {indentation}jsize {attribute_low}Length = {env}->GetArrayLength({attribute_low});"""
            if(field_name_extends == ""):
                if(not is_implicit):
                    src_str += f"""
        {indentation}jclass {struct_ref}{struct_name}Clazz = {env}->GetObjectClass({attribute_low}Obj);
        {indentation}{attribute.type.reference.namespace.name}::{attribute.type.reference.name} _{attribute_low}({attribute_low}Length);
        {indentation}{attribute.type.reference.namespace.name}::{attribute.type.reference.name} _{attribute_low}Response;
        """
                else:
                    src_str += f"""
        {indentation}jclass {struct_ref}{struct_name}Clazz = {env}->GetObjectClass({attribute_low}Obj);
        {indentation}std::vector<{attribute.type.type.reference.namespace.name}::{attribute.type.type.reference.name}> _{attribute_low}({attribute_low}Length);
        {indentation}std::vector<{attribute.type.type.reference.namespace.name}::{attribute.type.type.reference.name}> _{attribute_low}Response;
        """
            else:
                if(not is_implicit):
                    src_str += f"""
        {indentation}jclass {struct_ref}{struct_name}Clazz = {env}->GetObjectClass({attribute_low}Obj);
        {indentation}{attribute.type.reference.namespace.name}::{attribute.type.reference.name} _{attribute_low}({attribute_low}Length);
        //{indentation}{attribute.type.reference.namespace.name}::{attribute.type.reference.name} _{attribute_low}Response;
        """
                else:
                    src_str += f"""
        {indentation}jclass {struct_ref}{struct_name}Clazz = {env}->GetObjectClass({attribute_low}Obj);
        {indentation}std::vector<{attribute.type.type.reference.namespace.name}::{attribute.type.type.reference.name}> _{attribute_low}({attribute_low}Length);
        //{indentation}std::vector<{attribute.type.type.reference.namespace.name}::{attribute.type.type.reference.name}> _{attribute_low}Response;
        """
        elif(is_sub == 6):
            src_str += f"""
        {indentation}jobject {attribute_low}Obj = {env}->GetObjectArrayElement({attribute_low}, 0);
        {indentation}jclass {struct_ref}{struct_name}Clazz = {env}->GetObjectClass({attribute_low}Obj);
        {indentation}jsize {attribute_low}Length = {env}->GetArrayLength({attribute_low});"""
            if(not is_implicit):
                src_str += f"""
        {indentation}{attribute.type.reference.namespace.name}::{attribute_name} _{attribute_low}({attribute_low}Length);
        """
            else:
                src_str += f"""
        {indentation}std::vector<{attribute.type.type.reference.namespace.name}::{attribute.type.type.reference.name}> _{attribute_low}({attribute_low}Length);
        """
        
        # For loops
        ## Sub, Get, Bcast, Method out_args
        if(is_sub < 2 or is_sub == 4 or is_sub == 5 or is_sub == 7 or is_sub == 8):
            src_str += f"""
        {indentation}for(int i{for_loop_depth} = 0; i{for_loop_depth} < {attribute_low}Length; i{for_loop_depth}++){{{struct_for_loop}
            {indentation}jobject {attribute_low}Obj = {env}->NewObject({out}{struct_ref}{struct_name}Clazz, {out}{struct_ref}{struct_name}Constructor{struct_fields_arg});
            {indentation}{env}->SetObjectArrayElement({attribute_low}, i{for_loop_depth}, {attribute_low}Obj);
            {indentation}{env}->DeleteLocalRef({attribute_low}Obj);
        {indentation}}}
        
        {indentation}"""
        
        ## Set
        elif(is_sub == 2):
            src_str += f"""
        {indentation}for(int i{for_loop_depth} = 0; i{for_loop_depth} < {attribute_low}Length; i{for_loop_depth}++){{{struct_for_loop}
            {indentation}{attribute_low}Obj = {env}->NewObject({struct_ref}{struct_name}Clazz, {struct_ref}{struct_name}Constructor{struct_fields_arg});
            {indentation}{env}->SetObjectArrayElement({attribute_low}Response, i{for_loop_depth}, {attribute_low}Obj);
        {indentation}}}
        {indentation}{env}->DeleteLocalRef({attribute_low}Obj);

        {indentation}"""
        
        else:
            src_str += f""" 
        {indentation}for(int i{for_loop_depth} = 0; i{for_loop_depth} < {attribute_low}Length; i{for_loop_depth}++){{
            {indentation}{attribute_low}Obj = {env}->GetObjectArrayElement({attribute_low}, i{for_loop_depth});
            {struct_set_for_loop}
        }}
        """
        ## Method in_args
        if(is_sub == 6):
            src_str += f"""{indentation}{env}->DeleteLocalRef({attribute_low}Obj);
        """
        
        # {indentation}{env}->CallVoidMethod({interface_cap}Instance, {attribute_cap}MID, {attribute_low});
        # {indentation}{env}->DeleteLocalRef({attribute_low});
        # {indentation}jvm->DetachCurrentThread();
    
    return src_str
########################### Map C++ Generation ########################### 07.01
def check_type_map(arg, interface):
    type_list = ['Int8', 'UInt8', 'Int16', 'UInt16', 'Int32', 'UInt32', 'Int64', 'UInt64', 'Double', 'Float', 'Boolean']
    if(arg.name in type_list):
        return 1
    elif(arg.name == 'String'):
        return 2
    elif(isinstance(arg, ast.Reference)):
        if(isinstance(arg.reference, ast.Array)):
            if(isinstance(arg.reference.type, ast.Reference)):
                if(isinstance(arg.reference.type.reference, ast.Struct)):
                    return 9 # Explicit array of struct
                else:
                    raise Exception(f"Unsupported data type: {arg.name}")
            else:
                if(arg.reference.name in interface.arrays and len(arg.name.split('.')) == 1):
                    return 3 # explicit array in interface
                else:
                    return 6 # explicit array in typeCollection
        elif(isinstance(arg.reference, ast.Struct)):
            if(arg.reference.name in interface.structs and len(arg.name.split('.')) == 1):
                return 4
            else:
                return 7
        elif(isinstance(arg.reference, ast.Enumeration)):
            return 8
        # Map = implict struct array with only two elements, key and value
        elif(isinstance(arg.reference, ast.Map)):
            # print(arg.name)
            return 11
    elif(arg.name is None):
        if(isinstance(arg.type, ast.Reference)):
            if(isinstance(arg.type.reference, ast.Struct)):
                #print("I10 " + arg.name)
                return 10 # Implict array of struct
            else:
                raise Exception(f"Unsupported data type: {arg.name}")
        else:
            return 5 # implicit array
    elif(arg.name == 'ByteBuffer'):
        return 5
    
    elif(isinstance(arg, ast.Constant)):
        return 15
    else:
        return -1

def map_struct_cast(value, interface, java_class, map_name, upper="", indentation=0, is_key = False, is_set = False, is_sub=True):
    cast_str = ""
    pair = ".second"
    k_or_v = "Value"
    if(is_key):
        pair = ".first"
        k_or_v = "Key"
    field_const = ""
    upper = map_name + upper
    type = value
    if(not is_set):
        for field in value.reference.fields.values():
            type_checked = check_type_ver2(field, interface)
            field_const += ", {}".format(upper + k_or_v + capitalize_first_letter(field.name))
            if(type_checked == 1):
                cast_str += f"""{convert_java_type(field.type.name)} {upper}{k_or_v}{capitalize_first_letter(field.name)} = static_cast<{convert_java_type(field.type.name)}>(pair{pair}.get{capitalize_first_letter(field.name)}());
                """
            elif(type_checked == 2):
                cast_str += f"""{convert_java_type(field.type.name)} {upper}{k_or_v}{capitalize_first_letter(field.name)} = env->NewStringUTF((pair{pair}.get{capitalize_first_letter(field.name)}()).c_str());
                """
            elif(type_checked == 4):
                if(is_sub):
                    cast_str += f"""jmethodID {field.reference.namespace.name}{field.reference.name}MID = env->GetMethodID({field.reference.namespace.name}Clazz, "{capitalize_first_letter(field.reference.name)}ToCPP", "()L{java_class}{field.reference.namespace.name}JNI${field.reference.name};");
                jobject {field.reference.namespace.name}{field.reference.name}Instance = env->CallObjectMethod({field.reference.namespace.name}Instance, {field.reference.namespace.name}{field.reference.name}MID);
                jclass {field.reference.namespace.name}{field.reference.name}Clazz = env->GetObjectClass({field.reference.namespace.name}{field.reference.name}Instance);
                jmethodID {field.reference.namespace.name}{field.reference.name}Constructor = env->GetMethodID({field.reference.namespace.name}{field.reference.name}Clazz, "<init>", "({struct_fields(field,java_class)}V)");
                """
                    cast_str += map_struct_cast(field,interface,java_class,upper,upper=field.name, indentation=indentation+1, is_key=is_key, is_set=is_set, is_sub=is_sub)
                if(not is_sub):
                    print(map_name)
                    cast_str += f"""jclass {field.reference.namespace.name}{field.reference.name}Clazz = env->FindClass("{java_class}{field.reference.namespace.name}JNI${field.reference.name}");
                jmethodID {field.reference.namespace.name}{field.reference.name}Constructor = env->GetMethodID({field.reference.namespace.name}{field.reference.name}Clazz, "<init>", "({struct_fields(field,java_class)}V)");
                """
                    cast_str += map_struct_cast(field,interface,java_class,upper,upper=field.name, indentation=indentation+1, is_key=is_key, is_set=is_set, is_sub=False)
        
        cast_str += f"""jobject {upper}{k_or_v} = env->NewObject({type.reference.namespace.name}{type.reference.name}Clazz, {type.reference.namespace.name}{type.reference.name}Constructor{field_const});"""
    else:
        for field in value.reference.fields.values():
            type_checked = check_type_ver2(field, interface)
            field_const += ", {}".format(upper + k_or_v + capitalize_first_letter(field.name))
            if(type_checked == 1):
                cast_str += f"""jfieldID {upper}{k_or_v}{capitalize_first_letter(field.name)}FID = env->GetFieldID({type.reference.namespace.name}{type.reference.name}Clazz, "{field.name}", "{convert_jni_type(field.type.name)}");
            {convert_java_type(field.type.name)} {upper}{k_or_v}{capitalize_first_letter(field.name)} = env->GetObjectField({upper}{k_or_v}, {upper}{k_or_v}{capitalize_first_letter(field.name)}FID);
            {convert_cpp_type(field.type.name)} _{upper}{k_or_v}{capitalize_first_letter(field.name)} = static_cast<{convert_cpp_type(field.type.name)}>({upper}{k_or_v}{capitalize_first_letter(field.name)});
            _{upper}{k_or_v}.set{capitalize_first_letter(field.name)}(_{upper}{k_or_v}{capitalize_first_letter(field.name)});
            """
            elif(type_checked == 2):
                cast_str += f"""jfieldID {upper}{k_or_v}{capitalize_first_letter(field.name)}FID = env->GetFieldID({type.reference.namespace.name}{type.reference.name}Clazz, "{field.name}", "{convert_jni_type(field.type.name)}");
            {convert_java_type(field.type.name)} {upper}{k_or_v}{capitalize_first_letter(field.name)} = (jstring)env->GetObjectField({upper}{k_or_v}, {upper}{k_or_v}{capitalize_first_letter(field.name)}FID);
            const char* _{upper}{k_or_v}{capitalize_first_letter(field.name)}Temp = env->GetStringUTFChars({upper}{k_or_v}{capitalize_first_letter(field.name)}, nullptr);
            {convert_cpp_type(field.type.name)} _{upper}{k_or_v}{capitalize_first_letter(field.name)}(_{upper}{k_or_v}{capitalize_first_letter(field.name)}Temp);
            _{upper}{k_or_v}.set{capitalize_first_letter(field.name)}(_{upper}{k_or_v}{capitalize_first_letter(field.name)});
            """
            elif(type_checked == 4):
                cast_str += f"""jfieldID {upper}{k_or_v}{capitalize_first_letter(field.name)}FID = env->GetFieldID({type.reference.namespace.name}{type.reference.name}Clazz, "{field.name}", "L{java_class}{field.reference.namespace.name}JNI${field.reference.name};");
                jobject {upper}{k_or_v}{capitalize_first_letter(field.name)} = env->GetObjectField({upper}{k_or_v}, {upper}{k_or_v}{capitalize_first_letter(field.name)}FID);
                jclass {field.reference.namespace.name}{field.reference.name}Clazz = env->GetObjectClass({upper}{k_or_v});
                {field.reference.namespace.name}::{field.reference.name} _{upper}{k_or_v};
                """
                cast_str += map_struct_cast(field,interface,java_class,upper,upper=field.name, indentation=indentation+1, is_key=is_key, is_set=is_set)
                cast_str += f"""_{upper}{k_or_v}.set{capitalize_first_letter(field.name)}(_{upper}{k_or_v}{capitalize_first_letter(field.name)});
                """
        
        # cast_str += f"""{upper}{k_or_v} = env->NewObject({type.reference.namespace.name}Clazz, {type.reference.namespace.name}{type.reference.name}Constructor{field_const});"""
            
    return cast_str

def map_key_value_cast(map, interface, java_class, is_key = True, is_set = False, is_sub=True):
    cast_str = ""
    key_type = map.type.reference.key_type
    value_type = map.type.reference.value_type
    type = key_type
    type_checked = 0
    k_or_v = ""
    pair = ".first"
    if(is_key):
        type_checked = check_type_map(key_type, interface)
        k_or_v = "Key"
    else:
        type_checked = check_type_map(value_type, interface)
        k_or_v = "Value"
        pair = ".second"
        type = value_type
    map_low = lower_first_letter(map.name)
    
    # sub or get
    if(not is_set):
        if(type_checked == 1):
            cast_str += f"""{convert_java_type(type.name)} {map_low}{k_or_v} = static_cast<{convert_java_type(type)}>(pair{pair});"""
        elif(type_checked == 2):
            cast_str += f"""{convert_java_type(type.name)} {map_low}{k_or_v} = env->NewStringUTF((pair{pair}).c_str());"""
        elif(type_checked == 4):
            if(is_sub):
                cast_str += f"""jmethodID {type.reference.namespace.name}{type.reference.name}MID = env->GetMethodID({type.reference.namespace.name}Clazz, "{capitalize_first_letter(type.reference.name)}ToCPP", "()L{java_class}{type.reference.namespace.name}JNI${type.reference.name};");
                jobject {type.reference.namespace.name}{type.reference.name}Instance = env->CallObjectMethod({type.reference.namespace.name}Instance, {type.reference.namespace.name}{type.reference.name}MID);
                jclass {type.reference.namespace.name}{type.reference.name}Clazz = env->GetObjectClass({type.reference.namespace.name}{type.reference.name}Instance);
                jmethodID {type.reference.namespace.name}{type.reference.name}Constructor = env->GetMethodID({type.reference.namespace.name}{type.reference.name}Clazz, "<init>", "({struct_fields(type.reference.fields,java_class)})V");
                """
                cast_str += map_struct_cast(type,interface,java_class,map_low,upper="", indentation=0, is_key=is_key, is_set=False, is_sub=is_sub)
            # get 일 때
            else:
                cast_str += f"""jclass {type.reference.namespace.name}{type.reference.name}Clazz = env->FindClass("{java_class}{type.reference.namespace.name}JNI${type.reference.name}");
                jmethodID {type.reference.namespace.name}{type.reference.name}Constructor = env->GetMethodID({type.reference.namespace.name}{type.reference.name}Clazz, "<init>", "({struct_fields(type.reference.fields,java_class)})V");
                """
                cast_str += map_struct_cast(type,interface,java_class,map_low,upper="", indentation=0, is_key=is_key, is_set=False, is_sub=False)
        #### ByteBuffer with Map
        elif(type_checked == 3 or type_checked == 5):
            type_java_array = ""
            type_array = ""
            if(type_checked == 5):
                type_java_array = convert_java_type(type.type.name)
                type_array = capitalize_first_letter(convert_java_code_type(type.type.name))
                cast_str += f"""std::vector<{upcast_cpp_int(type.type.name)}> _{map_low}{k_or_v}Signed;
                """
            else:
                type_java_array = convert_java_type(type.reference.type.name)
                type_array = capitalize_first_letter(convert_java_code_type(type.reference.type.name))
                if(isUnsigned(type.reference.name)):
                    cast_str += f"""{type.reference.namespace.name}::{type.reference.name} _{map_low}{k_or_v}Signed;
                """
                else:
                   cast_str += f"""std::vector<{upcast_cpp_int(type.reference.type.name)}> _{map_low}{k_or_v}Signed;
                """ 
            cast_str += f"""_{map_low}{k_or_v}Signed.assign((pair{pair}).begin(), (pair{pair}).end());
                {type_java_array}* {map_low}{k_or_v}Data = static_cast<{type_java_array}*>((_{map_low}{k_or_v}Signed).data());
                jsize {map_low}{k_or_v}Length = static_cast<jsize>((_{map_low}{k_or_v}Signed).size());
                {type_java_array}Array {map_low}{k_or_v} = env->New{type_array}Array({map_low}{k_or_v}Length);
                env->Set{type_array}ArrayRegion({map_low}{k_or_v}, 0, {map_low}{k_or_v}Length, {map_low}{k_or_v}Data);"""
            #print("cast", cast_str)
                
    else:
        if(type_checked == 1):
            cast_str += f"""jfieldID {map_low}{k_or_v}FID = env->GetFieldID({map.type.reference.namespace.name}{map.type.reference.name}Clazz, "{lower_first_letter(k_or_v)}", "{convert_jni_type(type.name)}");
            {convert_java_type(type.name)} {map_low}{k_or_v} = env->GetObjectField({map_low}Obj, {map_low}{k_or_v}FID);
            {convert_cpp_type(type.name)} _{map_low}{k_or_v} = static_cast<{convert_cpp_type(type)}>({map_low}{k_or_v});"""
        elif(type_checked == 2):
            cast_str += f"""jfieldID {map_low}{k_or_v}FID = env->GetFieldID({map.type.reference.namespace.name}{map.type.reference.name}Clazz, "{lower_first_letter(k_or_v)}", "{convert_jni_type(type.name)}");
            {convert_java_type(type.name)} {map_low}{k_or_v} = (jstring)env->GetObjectField({map_low}Obj, {map_low}{k_or_v}FID);
            const char* _{map_low}{k_or_v}Temp = env->GetStringUTFChars({map_low}{k_or_v}, nullptr);
            {convert_cpp_type(type.name)} _{map_low}{k_or_v}(_{map_low}{k_or_v}Temp);"""
        elif(type_checked == 4):
            cast_str += f"""jfieldID {map_low}{k_or_v}FID = env->GetFieldID({map.type.reference.namespace.name}{map.type.reference.name}Clazz, "{lower_first_letter(k_or_v)}", "L{java_class}{type.reference.namespace.name}JNI${type.reference.name};");
            jobject {map_low}{k_or_v} = env->GetObjectField({map_low}Obj, {map_low}{k_or_v}FID);
            jclass {type.reference.namespace.name}{type.reference.name}Clazz = env->GetObjectClass({map_low}{k_or_v});
            {type.reference.namespace.name}::{type.reference.name} _{map_low}{k_or_v};
            """
            cast_str += map_struct_cast(type, interface, java_class, map_low, upper="", indentation=0, is_key=is_key, is_set=True)
        elif(type_checked == 3 or type_checked == 5):
            type_java_array = ""
            type_cpp = ""
            type_array = ""
            if(type_checked == 3):
                type_java_array = convert_java_type(type.reference.type.name)
                type_cpp = convert_cpp_type(type.reference.type.name)
                type_array = capitalize_first_letter(convert_java_code_type(type.reference.type.name))
                cast_str += f"""jfieldID {map_low}{k_or_v}FID = env->GetFieldID({map.type.reference.namespace.name}{map.type.reference.name}Clazz, "{lower_first_letter(k_or_v)}", "[{convert_jni_type(type.reference.type.name)}");
            """
            elif(type_checked == 5):
                type_java_array = convert_java_type(type.type.name)
                type_cpp = convert_cpp_type(type.type.name)
                type_array = capitalize_first_letter(convert_java_code_type(type.type.name))
                cast_str += f"""jfieldID {map_low}{k_or_v}FID = env->GetFieldID({map.type.reference.namespace.name}{map.type.reference.name}Clazz, "{lower_first_letter(k_or_v)}", "[{convert_jni_type(type.type.name)}");
            """
            cast_str += f"""{type_java_array}Array {map_low}{k_or_v} = reinterpret_cast<{type_java_array}Array>(env->GetObjectField({map_low}Obj, {map_low}{k_or_v}FID));
            {type_java_array}* {map_low}{k_or_v}Data = env->Get{type_array}ArrayElements({map_low}{k_or_v}, nullptr);
            jsize {map_low}{k_or_v}Length = env->GetArrayLength({map_low}{k_or_v});
            std::vector<{type_cpp}> _{map_low}{k_or_v}({map_low}{k_or_v}Data, {map_low}{k_or_v}Data + {map_low}{k_or_v}Length);"""
        
    return cast_str

def generate_src_map(map, package_name, interface, java_package_name, upper="", indentation=0, type=0):
    # type 0: sub or bcast / 1: get / 2: before set / 3: after set / 4: method out
    map_str = ""
    key_cast = ""
    value_cast = ""
    map_low = lower_first_letter(map.name)
    map_cap = capitalize_first_letter(map.name)
    env = "env"
    out = ""
    if(type == 4):
        out = "out"
    if(upper != ""):
        upper = upper + "."
        
    # ByteBuffer check
    check_type_map(map.type.reference.key_type, interface)
    check_type_map(map.type.reference.value_type, interface)
    if(map.type.reference.value_type.name == 'ByteBuffer'):
        map.type.reference.value_type = ast.Array(name=None, element_type=ast.Array(name="UInt8", element_type=ast.UInt8()))
        #print("FFFF", dir(map.type.reference.value_type), map.type.reference.value_type.name)
    #
    
    indent = "s"*indentation
    key_constructor = ""
    value_constructor = ""
    if(isinstance(map.type.reference.key_type, ast.Reference)):
        key_constructor = "L"+java_package_name+map.type.reference.namespace.name+"JNI${}".format(map.type.reference.key_type.name) +";"
    else:
        key_constructor = convert_jni_type(map.type.reference.key_type.name)
    if(isinstance(map.type.reference.value_type, ast.Reference)):
        if(isinstance(map.type.reference.value_type.reference, ast.Struct)):
            value_constructor = "L"+java_package_name+map.type.reference.namespace.name+"JNI${}".format(map.type.reference.value_type.name) +";"
        elif(isinstance(map.type.reference.value_type.reference, ast.Array)):
            value_constructor = "["+ convert_jni_type(map.type.reference.value_type.reference.type.name)
    elif(isinstance(map.type.reference.value_type, ast.Array)):
        #print(convert_jni_type(map.type.reference.value_type.type.name))
        value_constructor = "["+ convert_jni_type(map.type.reference.value_type.type.name)
    else:
        value_constructor = convert_jni_type(map.type.reference.value_type.name)
    
    
    # init
    if(type == 0):
        map_str += f"""
            jmethodID {map_cap}MID = {env}->GetMethodID({interface.name}Clazz, "subAttribute{map_cap}Handler", "([L{java_package_name}{map.type.reference.namespace.name}JNI${map.type.reference.name};)V");
            jmethodID {interface.name}{capitalize_first_letter(map.type.reference.name)}MID = {env}->GetMethodID({interface.name}Clazz, "{capitalize_first_letter(map.type.reference.name)}ToCPP", "()L{java_package_name}{map.type.reference.namespace.name}JNI${map.type.reference.name};");
            jobject {interface.name}{capitalize_first_letter(map.type.reference.name)}Instance = {env}->CallObjectMethod({interface.name}Instance, {interface.name}{capitalize_first_letter(map.type.reference.name)}MID);
            jclass {interface.name}{capitalize_first_letter(map.type.reference.name)}Clazz = {env}->GetObjectClass({interface.name}{capitalize_first_letter(map.type.reference.name)}Instance);
            jmethodID {interface.name}{capitalize_first_letter(map.type.reference.name)}Constructor = {env}->GetMethodID({interface.name}{capitalize_first_letter(map.type.reference.name)}Clazz, "<init>", "({key_constructor}{value_constructor})V");
            jsize {map_low}Length = static_cast<jsize>(_{map_low}.size());
            jobjectArray {map_low} = {env}->NewObjectArray({map_low}Length, {interface.name}{capitalize_first_letter(map.type.reference.name)}Clazz, nullptr);
            """
        
        key_cast = map_key_value_cast(map, interface, java_package_name, True)
        value_cast = map_key_value_cast(map, interface, java_package_name, False)
            
        cast_str = f"""int m{indent} = 0;
            for(const auto& pair: _{map_low}){{
                {key_cast}
                {value_cast}
                jobject {map_low}Obj = {env}->NewObject({interface.name}{capitalize_first_letter(map.type.reference.name)}Clazz, {interface.name}{capitalize_first_letter(map.type.reference.name)}Constructor, {map_low}Key, {map_low}Value);
                {env}->SetObjectArrayElement({map_low}, m{indent}++, {map_low}Obj);
                {env}->DeleteLocalRef({map_low}Obj);
            }}
            """
        map_str += cast_str
    elif(type == 1 or type ==4):
        map_str += f"""
        jclass {out}{interface.name}{capitalize_first_letter(map.type.reference.name)}Clazz = {env}->FindClass("{java_package_name}{map.type.reference.namespace.name}JNI${map.type.reference.name}");
        jmethodID {out}{interface.name}{capitalize_first_letter(map.type.reference.name)}Constructor = {env}->GetMethodID({out}{interface.name}{capitalize_first_letter(map.type.reference.name)}Clazz, "<init>", "({key_constructor}{value_constructor})V");
        jsize {map_low}Length = static_cast<jsize>(_{map_low}.size());
        jobjectArray {map_low} = {env}->NewObjectArray({map_low}Length, {out}{interface.name}{capitalize_first_letter(map.type.reference.name)}Clazz, nullptr);
        """
        
        key_cast = map_key_value_cast(map, interface, java_package_name, True, False, False)
        value_cast = map_key_value_cast(map, interface, java_package_name, False, False, False)
            
        cast_str = f"""int m{indent} = 0;
        for(const auto& pair: _{map_low}){{
            {key_cast}
            {value_cast}
            jobject {map_low}Obj = {env}->NewObject({out}{interface.name}{capitalize_first_letter(map.type.reference.name)}Clazz, {out}{interface.name}{capitalize_first_letter(map.type.reference.name)}Constructor, {map_low}Key, {map_low}Value);
            {env}->SetObjectArrayElement({map_low}, m{indent}++, {map_low}Obj);
            {env}->DeleteLocalRef({map_low}Obj);
        }}
        """
        map_str += cast_str
        
    elif(type == 2):
        map_str += f"""
        jobject {map_low}Obj = {env}->GetObjectArrayElement({map_low}, 0);
        jsize {map_low}Length = {env}->GetArrayLength({map_low});
        jclass {map.type.reference.namespace.name}{map.type.reference.name}Clazz = {env}->GetObjectClass({map_low}Obj);
        {map.type.reference.namespace.name}::{map.type.reference.name} _{map_low}({map_low}Length);
        {map.type.reference.namespace.name}::{map.type.reference.name} _{map_low}Response;
        """
        
        key_cast = map_key_value_cast(map, interface, java_package_name, True, True)
        value_cast = map_key_value_cast(map, interface, java_package_name, False, True)
        
        cast_str = f"""
        for(int m{indent}; m{indent} < {map_low}Length; m{indent}++){{
            {map_low}Obj = {env}->GetObjectArrayElement({map_low}, m{indent});
            {key_cast}
            {value_cast}
            _{map_low}[_{map_low}Key] = _{map_low}Value;
        }}
        """
        map_str += cast_str
    
    elif(type == 3):
        map_str += f"""
        
        jobjectArray {map_low}Response = {env}->NewObjectArray({map_low}Length, {map.type.reference.namespace.name}{map.type.reference.name}Clazz, nullptr);
        jmethodID {map.type.reference.namespace.name}{map.type.reference.name}Constructor = {env}->GetMethodID({map.type.reference.namespace.name}{map.type.reference.name}Clazz, "<init>", "({key_constructor}{value_constructor})V");
        """
        
        key_cast = map_key_value_cast(map, interface, java_package_name, True, False, False)
        value_cast = map_key_value_cast(map, interface, java_package_name, False, False, False)
            
        cast_str = f"""int m{indent} = 0;
        for(const auto& pair: _{map_low}Response){{
            {key_cast}
            {value_cast}
            {map_low}Obj = {env}->NewObject({interface.name}{capitalize_first_letter(map.type.reference.name)}Clazz, {interface.name}{capitalize_first_letter(map.type.reference.name)}Constructor, {map_low}Key, {map_low}Value);
            {env}->SetObjectArrayElement({map_low}Response, m{indent}++, {map_low}Obj);
        }}
        {env}->DeleteLocalRef({map_low}Obj);
        """
        map_str += cast_str
        
    # struct_fields_sub_gen and struct_fields_set_gen
    
    
    return map_str

################################### Attribute ############################

def generate_src_attribute(attribute, package_name, interface, java_package_name):
    env = "env"
    package_names = package_name.split('.')
    src_str = ""
    attr_type = attribute.type.name
    java_package = ""
    java_class = ""
    version = interface.version.major
    for name in java_package_name:
        java_package += "{}_".format(name)
        java_class += "{}/".format(name)
    # interface_cap = capitalize_first_letter(interface.name)
    interface_cap = interface.name
    interface_low = lower_first_letter(interface.name)
    attribute_cap = capitalize_first_letter(attribute.name)
    attribute_low = lower_first_letter(attribute.name)
    reference_cap = ""
    reference_type = ""
    interface_extension = "JNI"
    if(isinstance(attribute.type, ast.Reference)):
        reference_cap = capitalize_first_letter(attribute.type.reference.namespace.name)
        reference_type = attribute.type.reference.name

    type_cpp = convert_cpp_type(attr_type)
    type_jni = convert_jni_type(attr_type)
    type_java = convert_java_type(attr_type)
    array_name = attribute.type.name
    struct_name = attribute.type.name
    cpp_package = "::v{}".format(version)
    for name in package_names:
        cpp_package += "::{}".format(name)
    
    ### type validation
    type_checked = check_type_ver2(attribute, interface)
    
    if(type_checked < 1 or type_checked > 11):
        return src_str
    ###
    
    array = ""
    type_array = ""
    type_jni_array = ""
    type_java_array = ""
    type_cpp_array = ""

    struct = ""
    type_jni_struct = ""
    type_fields_jni = ""
    defined = ""

    if(type_checked == 3):
        array = interface.arrays[attr_type]
        type_array = capitalize_first_letter(convert_aidl_type(array.type.name))
        type_jni_array = convert_jni_type(array.type.name)
        type_java_array = convert_java_type(array.type.name)
        if(array.type.name == "String"):
            type_java_array = "jobject"
        type_cpp_array = upcast_cpp_int(array.type.name)
        
    elif(type_checked == 4):
        struct = interface.structs[attr_type]
        type_jni_struct = "L{}{}JNI${};".format(java_class,interface_cap,attr_type)
        type_fields_jni = struct_fields(struct.fields, java_class)
    elif(type_checked == 5):
        array = attribute.type
        type_array = capitalize_first_letter(convert_aidl_type(attribute.type.type.name))
        type_cpp = convert_cpp_type(attribute.type.type.name)
        type_jni = convert_jni_type(attribute.type.type.name)
        type_java = convert_java_type(attribute.type.type.name)
        type_jni_array = convert_jni_type(attribute.type.type.name)
        type_java_array = convert_java_type(attribute.type.type.name)
        if(type_java_array == "jstring"):
            type_java_array = "jobject"
        type_cpp_array = upcast_cpp_int(attribute.type.type.name)
        if(type_cpp_array == None):
            type_cpp_array = "std::string"
        
    elif(type_checked == 6):
        array = attribute.type.reference
        array_name = attribute.type.reference.name
        type_array = capitalize_first_letter(convert_aidl_type(attribute.type.reference.type.name))
        type_cpp = convert_cpp_type(attribute.type.reference.type.name)
        type_jni = convert_jni_type(attribute.type.reference.type.name)
        type_java = convert_java_type(attribute.type.reference.type.name)
        type_jni_array = convert_jni_type(attribute.type.reference.type.name)
        type_java_array = convert_java_type(attribute.type.reference.type.name)
        if(type_java_array == "jstring"):
            type_java_array = "jobject"
        type_cpp_array = upcast_cpp_int(attribute.type.reference.type.name)
    elif(type_checked == 7):
        type_jni_struct = "L{}{}JNI${};".format(java_class,interface_cap,attribute.type.reference.name)
        struct = attribute.type.name
        type_fields_jni = struct_fields(attribute.type.reference.fields, java_class)
    elif(type_checked == 8):
        print("")
    elif(type_checked == 9 or type_checked == 10):
        print("")
        # print(attribute.type.name, attribute.type.reference.type.reference)
        
    elif(type_checked == 15):
        raise Exception("ERROR: Constants are not allowed for attributes")
    
    
    ##########################################################################################################################        
    #sub의 경우 1번 - 공통
    if(type_checked == 4):
        defined = attribute.type.reference.namespace.name

    elif(type_checked == 7):
        defined = attribute.type.reference.namespace.name
        struct_name = attribute.type.reference.name

    
    if((type_checked >= 1 and type_checked <= 11)):
        src_str += f"""
    JNIEXPORT void JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_subAttribute{attribute_cap}(JNIEnv *env, jobject instance, jlong proxyptr){{
        {interface_cap}Client* _{interface_cap}Client = reinterpret_cast<{interface_cap}Client*>(proxyptr);
        _{interface_cap}Client->{interface_cap}Instance = {env}->NewGlobalRef(instance);
    \t_{interface_cap}Client->myProxy->get{attribute_cap}Attribute().getChangedEvent().subscribe(
    """
    
    #sub 2번 - 개별 - primitive와 아닌 것이 차이가 남
    if(type_checked == 1 or type_checked == 2):
        src_str += f"""\t\t[_{interface_cap}Client]({type_cpp} _{attribute_low}){{"""
    ### 3, 4, 6 통합 가능함 왜냐면 3개다 reference를 가지는 형태라 reference가 interface나 typecollection으로 나뉘어도 동일한 방법으로 추출 가능
    elif(type_checked == 3):
        src_str += f"""\t\t[_{interface_cap}Client]({interface_cap}::{array_name} _{attribute_low}){{"""
    elif(type_checked == 4):
        src_str += f"""\t\t[_{interface_cap}Client]({interface_cap}::{struct_name} _{attribute_low}){{"""
    elif(type_checked == 5):
        src_str += f"""\t\t[_{interface_cap}Client](std::vector<{type_cpp}> _{attribute_low}){{"""
    elif(type_checked == 6 or type_checked == 7 or type_checked == 8):
        src_str += f"""\t\t[_{interface_cap}Client]({reference_cap}::{attribute.type.reference.name} _{attribute_low}){{"""    
    elif(type_checked == 9):
        src_str += f"""\t\t[_{interface_cap}Client]({reference_cap}::{attribute.type.reference.name} _{attribute_low}){{"""
    elif(type_checked == 10):
        src_str += f"""\t\t[_{interface_cap}Client](std::vector<{attribute.type.type.reference.namespace.name}::{attribute.type.type.reference.name}> _{attribute_low}){{"""
    elif(type_checked == 11):
        src_str += f"""\t\t[_{interface_cap}Client]({attribute.type.reference.namespace.name}::{attribute.type.reference.name} _{attribute_low}){{"""
    
    #sub 3번 공통
    if(type_checked >= 1 and type_checked <= 11):
        src_str += f"""\n\t\t\tJNIEnv* {env};
    \t\tif((jvm)->AttachCurrentThread(&{env},nullptr) != JNI_OK){{
    \t\t    LOGI("Attach Error!");    
    \t\t}};
    \t\tjobject {interface_cap}Instance = _{interface_cap}Client->{interface_cap}Instance;
    \t\tjclass {interface_cap}Clazz = {env}->GetObjectClass({interface_cap}Instance);"""
    
    #sub 4번 개별 - type jni가 달라져야함 공통으로 만들려면 별도로 type_jni 추출할 때 array가 가능하게 해야함 근데 안 될 듯
    if(type_checked == 1):
        src_str += f"""\n\t\t\tjmethodID {attribute_cap}MID = {env}->GetMethodID({interface_cap}Clazz, "subAttribute{attribute_cap}Handler", "({type_jni})V");
        \t{type_java} {attribute_low} = static_cast<{type_java}>(_{attribute_low});"""
    elif(type_checked == 2):
        src_str += f"""\n\t\t\tjmethodID {attribute_cap}MID = {env}->GetMethodID({interface_cap}Clazz, "subAttribute{attribute_cap}Handler", "({type_jni})V");
        \t{type_java} {attribute_low} = {env}->NewStringUTF(_{attribute_low}.c_str());"""
    elif(type_checked == 3 or type_checked == 5):
        src_str += f"""\n\t\t\tjmethodID {attribute_cap}MID = {env}->GetMethodID({interface_cap}Clazz, "subAttribute{attribute_cap}Handler", "([{type_jni_array})V");"""
        if(isUnsigned(array.type.name) or array.type.name == "Int16"):
            src_str += f"""
            std::vector<{type_cpp_array}> _{attribute_low}Signed;
            _{attribute_low}Signed.assign(_{attribute_low}.begin(), _{attribute_low}.end());
            {type_java_array}* {attribute_low}Data = static_cast<{type_java_array}*>(_{attribute_low}Signed.data());"""
        elif(array.type.name == "String"):
            src_str += f"""
            jsize {attribute_cap}Length = static_cast<jsize>(_{attribute_low}.size());
            jstring {attribute_cap}Str = {env}->NewStringUTF("");
            jclass {attribute_cap}Clazz = {env}->GetObjectClass({attribute_cap}Str);
            jobjectArray {attribute_low} = {env}->NewObjectArray({attribute_cap}Length, {attribute_cap}Clazz, nullptr);
            
            for(int s = 0; s < {attribute_cap}Length; s++){{
                {attribute_cap}Str = {env}->NewStringUTF(_{attribute_low}[s].c_str());
                {env}->SetObjectArrayElement({attribute_low}, s, {attribute_cap}Str);
            }}
            {env}->DeleteLocalRef({attribute_cap}Str);"""
        else:
            src_str += f"""
    \t\t{type_java_array}* {attribute_low}Data = static_cast<{type_java_array}*>(_{attribute_low}.data());"""
        if(array.type.name != "String"):
            src_str += f"""
    \t\tjsize {attribute_low}Length = static_cast<jsize>(_{attribute_low}.size());
    \t\t{type_java_array}Array {attribute_low} = {env}->New{type_array}Array({attribute_low}Length);
    \t\t{env}->Set{type_array}ArrayRegion({attribute_low}, 0, {attribute_low}Length, {attribute_low}Data);"""
    # Structs
    elif(type_checked == 4 or type_checked == 7):
        # 최초 interface1Clazz 등을 위함
        reference_list = [interface_cap]
        if(attribute.type.reference.namespace.name not in reference_list):
            reference_list.append(attribute.type.reference.namespace.name)
            src_str += f"""
    \t\tjobject {capitalize_first_letter(attribute.type.reference.namespace.name)}Instance = {env}->AllocObject(_{interface_cap}Client->{capitalize_first_letter(attribute.type.reference.namespace.name)}Clazz);
    \t\tjclass {capitalize_first_letter(attribute.type.reference.namespace.name)}Clazz = {env}->GetObjectClass({capitalize_first_letter(attribute.type.reference.namespace.name)}Instance);"""
        for field in attribute.type.reference.fields.values():
            if(isinstance(field.type, ast.Reference)):
                if(isinstance(field.type.reference, ast.Struct)):
                    if(field.type.reference.namespace.name not in reference_list):
                        reference_list.append(field.type.reference.namespace.name)
                        src_str += f"""
    \t\tjobject {capitalize_first_letter(field.type.reference.namespace.name)}Instance = {env}->AllocObject(_{interface_cap}Client->{capitalize_first_letter(field.type.reference.namespace.name)}Clazz);
    \t\tjclass {capitalize_first_letter(field.type.reference.namespace.name)}Clazz = {env}->GetObjectClass({capitalize_first_letter(field.type.reference.namespace.name)}Instance);"""
        
        src_str += f"""
        \tjmethodID {attribute_cap}MID = {env}->GetMethodID({interface_cap}Clazz, "subAttribute{attribute_cap}Handler", "({type_jni_struct})V");"""
        ###
        src_str += struct_fields_sub_gen(attribute,interface,cpp_package,java_class,"")
        src_str += f"""
        \tjobject {attribute_low} = {env}->NewObject({defined}{struct_name}Clazz, {defined}{struct_name}Constructor"""
        #for field in interface.structs[attr_type].fields.values():
        for field in attribute.type.reference.fields.values():
            src_str += ", {}{}".format(attribute_low, capitalize_first_letter(field.name))
        src_str += ");"
    elif(type_checked == 6):
        src_str += f"""\n\t\t\tjmethodID {attribute_cap}MID = {env}->GetMethodID({interface_cap}Clazz, "subAttribute{attribute_cap}Handler", "([{type_jni_array})V");"""
        if(isUnsigned(attribute.type.reference.type.name) or array.type.name == "Int16"):
            src_str += f"""
            std::vector<{type_cpp_array}> _{attribute_low}Signed;
            _{attribute_low}Signed.assign(_{attribute_low}.begin(), _{attribute_low}.end());
            {type_java_array}* {attribute_low}Data = static_cast<{type_java_array}*>(_{attribute_low}Signed.data());"""
        else:
            src_str += f"""
    \t\t{type_java_array}* {attribute_low}Data = static_cast<{type_java_array}*>(_{attribute_low}.data());"""
        src_str += f"""
    \t\tjsize {attribute_low}Length = static_cast<jsize>(_{attribute_low}.size());
    \t\t{type_java_array}Array {attribute_low} = {env}->New{type_array}Array({attribute_low}Length);
    \t\t{env}->Set{type_array}ArrayRegion({attribute_low}, 0, {attribute_low}Length, {attribute_low}Data);"""
    elif(type_checked == 8):
        if(reference_cap != interface_cap):
            src_str += f"""
    \t\tjobject {capitalize_first_letter(attribute.type.reference.namespace.name)}Instance = {env}->AllocObject(_{interface_cap}Client->{capitalize_first_letter(attribute.type.reference.namespace.name)}Clazz);
    \t\tjclass {capitalize_first_letter(attribute.type.reference.namespace.name)}Clazz = {env}->GetObjectClass({capitalize_first_letter(attribute.type.reference.namespace.name)}Instance);"""
        src_str += f"""
        \tjmethodID {attribute_cap}MID = {env}->GetMethodID({reference_cap}Clazz, "subAttribute{attribute_cap}Handler", "(B)V");
        \tuint8_t _{attribute_low}Int = static_cast<uint8_t>(_{attribute_low});
        \tjbyte {attribute_low} = static_cast<jbyte>(_{attribute_low}Int);"""
    elif(type_checked == 9):
        src_str += complex_array(attribute, interface, cpp_package, java_class)
        src_str += f"""{env}->CallVoidMethod({interface_cap}Instance, {attribute_cap}MID, {attribute_low});
            {env}->DeleteLocalRef({attribute_low});
            jvm->DetachCurrentThread();
            }}
        );
    }}\n
    """
    elif(type_checked == 10):
        src_str += complex_array(attribute, interface, cpp_package, java_class, field_name_extends="", is_sub=0, is_implicit=True)
        src_str += f"""{env}->CallVoidMethod({interface_cap}Instance, {attribute_cap}MID, {attribute_low});
            {env}->DeleteLocalRef({attribute_low});
            jvm->DetachCurrentThread();
            }}
        );
    }}\n
    """
    elif(type_checked == 11):
        # src_str += complex_array(attribute, interface, cpp_package, java_class, field_name_extends="", is_sub=0, is_implicit=True)
        src_str += generate_src_map(attribute, cpp_package, interface, java_class, upper="", indentation=0, type=0)
        src_str += f"""{env}->CallVoidMethod({interface_cap}Instance, {attribute_cap}MID, {attribute_low});
            {env}->DeleteLocalRef({attribute_low});
            jvm->DetachCurrentThread();
            }}
        );
    }}\n
    """
    #sub 5번 공통
    if(type_checked >= 1 and type_checked <= 8):
        src_str += f"""\n\t\t\t{env}->CallVoidMethod({interface_cap}Instance, {attribute_cap}MID, {attribute_low});"""
    
    #sub 6번 개별
    if(type_checked >= 3 and type_checked <= 7):
        src_str += f"""\n\t\t\t{env}->DeleteLocalRef({attribute_low});"""
    
    #sub 7번 공통
    if(type_checked >= 1 and type_checked <= 8):
        src_str += f"""\n\t\t\tjvm->DetachCurrentThread();
    \t\t}}
    \t);
    }}\n
    """
    ###################################################################################################################
    ##### get code
    #1번 개별, return type 때문
    if(type_checked == 1 or type_checked == 2):
        src_str += f"""JNIEXPORT {type_java} JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_getAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender){{"""
    elif(type_checked == 3 or type_checked == 5):
        src_str += f"""JNIEXPORT {type_java_array}Array JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_getAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender){{"""
    elif(type_checked == 4 or type_checked == 7): # or type_checked == 8):
        src_str += f"""JNIEXPORT jobject JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_getAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender){{"""
    elif(type_checked == 6):
        src_str += f"""JNIEXPORT {type_java_array}Array JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_getAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender){{""" 
    elif(type_checked == 8):
        src_str += f"""JNIEXPORT jbyte JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_getAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender){{"""
    elif(type_checked == 9 or type_checked == 10 or type_checked == 11):
        src_str += f"""JNIEXPORT jobjectArray JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_getAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender){{"""
    
    
    if(type_checked >= 1 and type_checked <= 11):
        src_str += f"""
    \t{interface_cap}Client* _{interface_cap}Client = reinterpret_cast<{interface_cap}Client*>(proxyptr);
    \t//_{interface_cap}Client->{interface_cap}Instance = {env}->NewGlobalRef(instance);
    \tCommonAPI::CallStatus callStatus;
    \tCommonAPI::CallInfo info(static_cast<int>(timeout));
    \tinfo.sender_ = static_cast<int>(sender);
    """
    
    #1-1번 2.28 추가, Enumeration의 경우 instance를 사용해야 하는데 이때 필요한 instance가 해당 interface의 것이 아닐 수도 있음.
    list_get = []
    # if(type_checked == 8 or type_checked == 4 or type_checked == 6 or type_checked == 7):
    if(isinstance(attribute.type, ast.Reference)):
        if(isinstance(attribute.type.reference, ast.Enumeration) and (attribute.type.reference.namespace.name not in list_get)):
            list_get.append(attribute.type.reference.namespace.name)
            src_str += f"""\tjobject {attribute.type.reference.namespace.name}Instance = {env}->AllocObject(_{interface_cap}Client->{attribute.type.reference.namespace.name}Clazz);
            """
        elif(isinstance(attribute.type.reference, ast.Struct)):
            for field in attribute.type.reference.fields.values():
                if(isinstance(field.type, ast.Reference)):
                    if(isinstance(field.type.reference, ast.Enumeration) and (field.type.reference.namespace.name not in list_get)):
                        list_get.append(field.type.reference.namespace.name)
                        src_str += f"""\tjobject {field.type.reference.namespace.name}Instance = {env}->AllocObject(_{interface_cap}Client->{field.type.reference.namespace.name}Clazz);
            """
            
    
    #2번 개별, 변수 getValue의 인자 선언
    # if primitive
    if(type_checked == 1 or type_checked == 2):
        src_str += f"""\t{type_cpp} _{attribute_low};"""
    elif(type_checked == 3):
        src_str += f"""
        /*{cpp_package}::*/{interface_cap}::{array_name} _{attribute_low};"""
    elif(type_checked == 4):
        src_str += f"""
        /*{cpp_package}::*/{interface_cap}::{struct_name} _{attribute_low};"""
    elif(type_checked == 5):
        src_str += f"""
        std::vector<{convert_cpp_type(attribute.type.type.name)}> _{attribute_low};"""
    elif(type_checked == 6 or type_checked == 7):
        src_str += f"""
        /*{cpp_package}::*/{reference_cap}::{attribute.type.reference.name} _{attribute_low};"""
    elif(type_checked == 8):
        src_str += f"""
        /*{cpp_package}::*/{reference_cap}::{attribute.type.reference.name} _{attribute_low};"""
    elif(type_checked == 9):
        src_str += f"""
        /*{cpp_package}::*/{reference_cap}::{attribute.type.reference.name} _{attribute_low};"""
    elif(type_checked == 10):
        src_str += f"""
        std::vector<{attribute.type.type.reference.namespace.name}::{attribute.type.type.reference.name}> _{attribute_low};"""
    elif(type_checked == 11):
        src_str += f"""
        {attribute.type.reference.namespace.name}::{attribute.type.reference.name} _{attribute_low};"""
        
    #3번 getvalue call
    if(type_checked >= 1 and type_checked <= 11):
        src_str += f"""
    \t_{interface_cap}Client->myProxy->get{attribute_cap}Attribute().getValue(callStatus, _{attribute_low}, &info);
    \tif(callStatus != CommonAPI::CallStatus::SUCCESS) {{
    \t\tLOGE("Get Value {attribute_low} failed!");
    \t}}"""
    
    #4번 개별 return
    if(type_checked == 1):
        src_str += f"""
        return static_cast<{type_java}>(_{attribute_low});
    }}\n
    """
    elif(type_checked == 2):
        src_str += f"""{type_java} {attribute_low} = env->NewStringUTF(_{attribute_low}.c_str());
    \n\treturn {attribute_low};
    }}\n
    """
    elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
        if(isUnsigned(array.type.name) or array.type.name == "Int16"):
            src_str += f"""
        std::vector<{type_cpp_array}> _{attribute_low}Signed;
        _{attribute_low}Signed.assign(_{attribute_low}.begin(), _{attribute_low}.end());
        {type_java_array}* {attribute_low}Data = static_cast<{type_java_array}*>(_{attribute_low}Signed.data());"""
        elif(array.type.name == "String"):
            src_str += f"""
        jsize {attribute_cap}Length = static_cast<jsize>(_{attribute_low}.size());
        jstring {attribute_cap}Str = {env}->NewStringUTF("");
        jclass {attribute_cap}Clazz = {env}->GetObjectClass({attribute_cap}Str);
        jobjectArray {attribute_low} = {env}->NewObjectArray({attribute_cap}Length, {attribute_cap}Clazz, nullptr);
        
        for(int ss = 0; ss < {attribute_cap}Length; ss++){{
            {attribute_cap}Str = {env}->NewStringUTF(_{attribute_low}[ss].c_str());
            {env}->SetObjectArrayElement({attribute_low}, ss, {attribute_cap}Str);
        }}
        
        {env}->DeleteLocalRef({attribute_cap}Str);
        
        return {attribute_low};
    }}\n
    """
        else:
            src_str += f"""
        {type_java_array}* {attribute_low}Data = static_cast<{type_java_array}*>(_{attribute_low}.data());"""
        
        if(array.type.name != "String"):
            src_str += f"""
        jsize {attribute_low}Length = static_cast<jsize>(_{attribute_low}.size());
        {type_java_array}Array {attribute_low} = env->New{type_array}Array({attribute_low}Length);
        env->Set{type_array}ArrayRegion({attribute_low}, 0, {attribute_low}Length, {attribute_low}Data);
        return {attribute_low};
    }}\n
    """
    elif(type_checked == 4 or type_checked == 7):
        ## struct_fields_sub_gen 으로 아래 부분 전체 대체 가능?
        src_str += struct_fields_sub_gen(attribute,interface,cpp_package,java_class,"",False)
        src_str += f"""
        jobject {attribute_low} = env->NewObject({defined}{struct_name}Clazz, {defined}{struct_name}Constructor"""
        for field in attribute.type.reference.fields.values():
            src_str += ", {}{}".format(attribute_low, capitalize_first_letter(field.name))
        src_str += ");"
        ##### 여기까지 대체
        #4-1 2.28 Enumeration 추가로 별도 instance 만들 시 해당 instance 삭제
        for ref in list_get:
            src_str += f"""
        {env}->DeleteLocalRef({ref}Instance);"""
        src_str += f"""
        return {attribute_low};
    }}\n\n"""
    elif(type_checked == 8):
        src_str += f"""
        uint8_t _{attribute_low}Int = static_cast<uint8_t>(_{attribute_low});
        jbyte {attribute_low}Int = static_cast<jbyte>(_{attribute_low}Int);
        {env}->DeleteLocalRef({reference_cap}Instance);
        return {attribute_low}Int;
    }}\n\n"""
    elif(type_checked == 9):
        src_str += complex_array(attribute, interface, cpp_package, java_class, field_name_extends="", is_sub=1)
        src_str += f"""return {attribute_low};
    }}\n
    """
    elif(type_checked == 10):
        src_str += complex_array(attribute, interface, cpp_package, java_class, field_name_extends="", is_sub=1, is_implicit=True)
        src_str += f"""return {attribute_low};
    }}\n
    """
    elif(type_checked == 11):
        ### type 1 만들어야함
        src_str += generate_src_map(attribute, cpp_package, interface, java_class, upper="", indentation=0, type=1)
        src_str += f"""return {attribute_low};
    }}\n
    """
    
    ################################################################################################################
    ### set code, if not readonly
    ####1번 개별, return type 때문
    if('readonly' not in attribute.flags):
        if(type_checked == 1 or type_checked == 2):
            src_str += f"""
    JNIEXPORT {type_java} JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_setAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender, {type_java} {attribute_low}){{"""
        elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
            src_str += f"""
    JNIEXPORT {type_java_array}Array JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_setAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender, {type_java_array}Array {attribute_low}){{"""
        elif(type_checked == 4 or type_checked == 7): #or type_checked == 8):
            src_str += f"""
    JNIEXPORT jobject JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_setAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender, jobject {attribute_low}){{"""    
        elif(type_checked == 8):
            src_str += f"""
    JNIEXPORT jbyte JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_setAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender, jbyte {attribute_low}){{"""    
        elif(type_checked == 9 or type_checked == 10 or type_checked == 11):
            src_str += f"""
    JNIEXPORT jobjectArray JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_setAttribute{attribute_cap}Value(JNIEnv *env, jobject instance, jlong proxyptr, jint timeout, jint sender, jobjectArray {attribute_low}){{"""    
    
        src_str += f"""
    \t{interface_cap}Client* _{interface_cap}Client = reinterpret_cast<{interface_cap}Client*>(proxyptr);
    \t//_{interface_cap}Client->{interface_cap}Instance = {env}->NewGlobalRef(instance);
    \tCommonAPI::CallStatus callStatus;
    \tCommonAPI::CallInfo info(static_cast<int>(timeout));
    \tinfo.sender_ = static_cast<int>(sender);"""
    
        ### 1-1 Enumeration 때문에 추가
        list_set = []
        # if(type_checked == 8 or type_checked == 4 or type_checked == 6 or type_checked == 7):
        if(isinstance(attribute.type, ast.Reference)):
            if(isinstance(attribute.type.reference, ast.Enumeration) and (attribute.type.reference.namespace.name not in list_set)):
                list_set.append(attribute.type.reference.namespace.name)
                #src_str += f"""\n\t\t//jobject {attribute.type.reference.namespace.name}Instance = {env}->AllocObject({interface_low}Client->{attribute.type.reference.namespace.name}Clazz);"""
            elif(isinstance(attribute.type.reference, ast.Struct)):
                for field in attribute.type.reference.fields.values():
                    if(isinstance(field.type, ast.Reference)):
                        if(isinstance(field.type.reference, ast.Enumeration) and (field.type.reference.namespace.name not in list_set)):
                            list_set.append(field.type.reference.namespace.name)
                            src_str += f"""\n\t\tjobject {field.type.reference.namespace.name}Instance = {env}->AllocObject(_{interface_cap}Client->{field.type.reference.namespace.name}Clazz);"""
        src_str_temp = ""
        src_str_struct = ""
        ####2번 개별, 변수 선언
        if(type_checked == 1):
            src_str += f"""
        {type_cpp} _{attribute_low} = static_cast<{type_cpp}>({attribute_low});
        {type_cpp} _{attribute_low}Response;"""
        elif(type_checked == 2):
            src_str += f"""
            const char* char_{attribute_low} = env->GetStringUTFChars({attribute_low},nullptr);
            {type_cpp} _{attribute_low}(char_{attribute_low});
            {type_cpp} _{attribute_low}Response;"""
        elif(type_checked == 3 or type_checked == 6):
            if(array.type.name != "String"):
                src_str += f"""
        {type_java_array}* {attribute_low}Data = env->Get{type_array}ArrayElements({attribute_low}, nullptr);
        jsize {attribute_low}Length = env->GetArrayLength({attribute_low});
        /*{cpp_package}::*/{reference_cap}::{array_name} _{attribute_low}({attribute_low}Data, {attribute_low}Data + {attribute_low}Length);
        /*{cpp_package}::*/{reference_cap}::{array_name} _{attribute_low}Response;"""
            else:
                src_str += f"""
        jsize {attribute_cap}Length = env->GetArrayLength({attribute_low});
        /*{cpp_package}::*/{reference_cap}::{array_name} _{attribute_low};
        /*{cpp_package}::*/{reference_cap}::{array_name} _{attribute_low}Response;
        jstring {attribute_cap}Str = {env}->NewStringUTF("");
        for(int sss = 0; sss < {attribute_cap}Length; sss++){{
            {attribute_cap}Str = (jstring){env}->GetObjectArrayElement({attribute_low}, sss);
            const char *{attribute_cap}Cstr = {env}->GetStringUTFChars({attribute_cap}Str, nullptr);
            _{attribute_low}.push_back(std::string({attribute_cap}Cstr));
        }}
        """
        elif(type_checked == 4 or type_checked == 7):
            src_str += f"""
        jclass {defined}{struct_name}Clazz = env->GetObjectClass({attribute_low});
        jmethodID {defined}{struct_name}Constructor = env->GetMethodID({defined}{struct_name}Clazz, "<init>", "({type_fields_jni})V");
        /*{cpp_package}::*/{reference_cap}::{struct_name} _{attribute_low};
        /*{cpp_package}::*/{reference_cap}::{struct_name} _{attribute_low}Response;"""
            src_str_temp, src_str_struct = struct_fields_set_gen(attribute,interface,cpp_package,java_class)
            src_str += src_str_temp
        elif(type_checked == 5):
            if(array.type.name != "String"):
                src_str += f"""
        {type_java_array}* {attribute_low}Data = env->Get{type_array}ArrayElements({attribute_low}, nullptr);
        jsize {attribute_low}Length = env->GetArrayLength({attribute_low});
        std::vector<{type_cpp}> _{attribute_low}({attribute_low}Data, {attribute_low}Data + {attribute_low}Length);
        std::vector<{type_cpp}> _{attribute_low}Response;"""
            else:
                src_str += f"""
        jsize {attribute_cap}Length = env->GetArrayLength({attribute_low});
        std::vector<{type_cpp}> _{attribute_low};
        std::vector<{type_cpp}> _{attribute_low}Response;
        jstring {attribute_cap}Str = {env}->NewStringUTF("");
        for(int sss = 0; sss < {attribute_cap}Length; sss++){{
            {attribute_cap}Str = (jstring){env}->GetObjectArrayElement({attribute_low}, sss);
            const char *{attribute_cap}Cstr = {env}->GetStringUTFChars({attribute_cap}Str, nullptr);
            _{attribute_low}.push_back(std::string({attribute_cap}Cstr));
        }}
        """
        elif(type_checked == 8):
            src_str += f"""
        jbyte {attribute_low}Int = {attribute_low};
        uint8_t _{attribute_low}Int = static_cast<uint8_t>({attribute_low}Int);
        {reference_cap}::{reference_type} _{attribute_low} = {reference_cap}::{reference_type}::Literal(_{attribute_low}Int);
        {reference_cap}::{reference_type} _{attribute_low}Response;"""
        elif(type_checked == 9):
            src_str += complex_array(attribute, interface, cpp_package, java_class, "", 3)
        elif(type_checked == 10):
            src_str += complex_array(attribute, interface, cpp_package, java_class, "", 3, is_implicit=True)
        elif(type_checked == 11):
            src_str += generate_src_map(attribute,cpp_package,interface,java_class,upper="",indentation=0,type=2)
            
        ####3번 setValue call
        src_str += f"""
        _{interface_cap}Client->myProxy->get{attribute_cap}Attribute().setValue(_{attribute_low}, callStatus, _{attribute_low}Response, &info);
        if(callStatus != CommonAPI::CallStatus::SUCCESS) {{
        \tLOGE("Set Value {attribute_low} failed!");
        }}"""
        
        ####4번 return
        if(type_checked == 1):
            src_str += f"""
        return static_cast<{type_java}>(_{attribute_low}Response);
        }}\n"""
        elif(type_checked == 2):
            src_str += f"""
        {type_java} {attribute_low}Response = env->NewStringUTF(_{attribute_low}Response.c_str());
        return {attribute_low}Response;
        }}\n"""
        elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
            if(isUnsigned(array.type.name) or array.type.name == "Int16"):
                src_str += f"""
        std::vector<{type_cpp_array}> _{attribute_low}ResponseSigned;
        _{attribute_low}ResponseSigned.assign(_{attribute_low}Response.begin(), _{attribute_low}Response.end());
        {attribute_low}Data = static_cast<{type_java_array}*>(_{attribute_low}ResponseSigned.data());"""
            elif(array.type.name == "String"):
                src_str += f"""
        jclass {attribute_cap}Clazz = {env}->GetObjectClass({attribute_cap}Str);
        {type_java_array}Array {attribute_low}Response = {env}->NewObjectArray({attribute_cap}Length, {attribute_cap}Clazz, nullptr);
        
        for(int sss = 0; sss < {attribute_cap}Length; sss++){{
            {attribute_cap}Str = {env}->NewStringUTF(_{attribute_low}Response[sss].c_str());
            {env}->SetObjectArrayElement({attribute_low}Response, sss, {attribute_cap}Str);
        }}
        {env}->DeleteLocalRef({attribute_cap}Str);
        
        return {attribute_low}Response;
    }}
    """
            else:
                src_str += f"""
        {attribute_low}Data = static_cast<{type_java_array}*>(_{attribute_low}Response.data());"""
            if(array.type.name != "String"):
                src_str += f"""
        {type_java_array}Array {attribute_low}Response = env->New{type_array}Array({attribute_low}Length);
        env->Set{type_array}ArrayRegion({attribute_low}Response, 0, {attribute_low}Length, {attribute_low}Data);
        return {attribute_low}Response;
        }}\n"""
        elif(type_checked == 4 or type_checked == 7):
            src_str += src_str_struct
            src_str += f"""
        jobject {attribute_low}Response = env->NewObject({defined}{attribute.type.reference.name}Clazz, {defined}{attribute.type.reference.name}Constructor"""
            for field in attribute.type.reference.fields.values():
                src_str += ", {}{}".format(attribute_low,capitalize_first_letter(field.name));
            src_str += ");"
            for ref in list_set:
                src_str += f"""
        {env}->DeleteLocalRef({ref}Instance);"""
            src_str += f"""
        return {attribute_low}Response;
    }}\n"""
        elif(type_checked == 8):
            src_str += f"""
        _{attribute_low}Int = static_cast<uint8_t>(_{attribute_low}Response);
        jbyte {attribute_low}Response = static_cast<jbyte>(_{attribute_low}Int);
        return {attribute_low}Response;
    }}\n"""
        elif(type_checked == 9):
            src_str += complex_array(attribute, interface, cpp_package, java_class, field_name_extends="", is_sub=2)
            src_str += f"""
        return {attribute_low}Response;
    }}\n"""
        elif(type_checked == 10):
            src_str += complex_array(attribute, interface, cpp_package, java_class, field_name_extends="", is_sub=2, is_implicit=True)
            src_str += f"""
        return {attribute_low}Response;
    }}\n"""
        elif(type_checked == 11):
            src_str += generate_src_map(attribute,cpp_package,interface,java_class,upper="",indentation=0,type=3)
            src_str += f"""
        return {attribute_low}Response;
    }}\n"""

    ###################################################################################################################
    ### unsub code, same for all
    src_str += f"""
    JNIEXPORT void JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_unsubAttribute{attribute_cap}(JNIEnv *env, jobject instance, jlong proxyptr, jint subscription){{
    \t{interface_cap}Client* _{interface_cap}Client = reinterpret_cast<{interface_cap}Client*>(proxyptr);
    \t//_{interface_cap}Client->{interface_cap}Instance = {env}->NewGlobalRef(instance);
    \tint _subscription = static_cast<int>(subscription);
    \t_{interface_cap}Client->myProxy->get{attribute_cap}Attribute().getChangedEvent().unsubscribe(_subscription);
    }}\n"""

    src_str += """\n////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////\n"""

    return(src_str)

##################################### METHOD ################################################################################
def struct_fields_method_in_gen(arg, interface, packages, java_class, field_name_extends=""):
    fields_str = ""
    
    field_type_java = ""
    field_type_jni = ""
    field_name = ""
    array = ""
    type_checked = 0
    struct = arg.type.reference
    env = "env"
    defined = ""
    interface_extension = "JNI"
    if(len(arg.type.name.split('.')) > 1):
        defined = arg.type.name.split('.')[0]
    else:
        defined = arg.type.reference.namespace.name
        
    if(field_name_extends == ""):
        arg_low = field_name_extends + lower_first_letter(arg.name)
    else:
        arg_low = field_name_extends + capitalize_first_letter(arg.name)
        
    for field in arg.type.reference.fields.values():
        field_name = capitalize_first_letter(field.name)
        field_name_low = field.name
        type_checked = check_type_ver2(field, interface)
        if(type_checked == 1):
            field_type_jni = convert_jni_type(field.type.name)
            field_type_java = convert_java_type(field.type.name)
            field_type_cpp = convert_cpp_type(field.type.name)
            #field_name = capitalize_first_letter(field.name)
            #field_name_low = lower_first_letter(field.name)
            fields_str += f"""\n\t\tjfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, \"{field_name_low}\", \"{field_type_jni}\");"""
            fields_str += f"""\n\t\t{field_type_java} {arg_low}{field_name} = {env}->Get{capitalize_first_letter(convert_aidl_type(field.type.name))}Field({arg_low}, {arg_low}{field_name}FID);"""
            fields_str += f"""
        _{arg_low}.set{field_name}(static_cast<{field_type_cpp}>({arg_low}{field_name}));"""
        elif(type_checked == 2):
            field_type_jni = convert_jni_type(field.type.name)
            field_type_java = convert_java_type(field.type.name)
            #field_name = capitalize_first_letter(field.name)
            #field_name_low = lower_first_letter(field.name)
            fields_str += f"""\n\t\tjfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, \"{field_name_low}\", \"{field_type_jni}\");"""
            # fields_str += f"""\n\t\tjstring {arg_low}{field_name} = static_cast<jstring>(env->GetObjectField({arg_low},{arg_low}{field_name}FID);"""
            fields_str += f"""\n\t\tjstring {arg_low}{field_name} = (jstring)({env}->GetObjectField({arg_low},{arg_low}{field_name}FID));"""
            fields_str += f"""\n\t\tconst char* _{arg_low}{field_name}Temp = {env}->GetStringUTFChars({arg_low}{field_name}, nullptr);"""
            fields_str += f"""\n\t\tstd::string _{arg_low}{field_name}(_{arg_low}{field_name}Temp);"""
            fields_str += f"""
        _{arg_low}.set{field_name}(_{arg_low}{field_name});"""
        elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
            if(type_checked == 3):
                array = interface.arrays[field.type.name]
            elif(type_checked == 5):
                array = field.type
            elif(type_checked == 6):
                array = field.type.reference
            type_jni_array = convert_jni_type(array.type.name)
            type_java_array = convert_java_type(array.type.name)
            type_cpp_array = convert_cpp_type(array.type.name)
            #field_name = capitalize_first_letter(field.name)
            #field_name_low = lower_first_letter(field.name)
            if(array.type.name != "String"):
                fields_str += f"""\n\t\tjfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, \"{field_name_low}\", \"[{type_jni_array}\");
        {type_java_array}Array {arg_low}{field_name} = reinterpret_cast<{type_java_array}Array>({env}->GetObjectField({arg_low},{arg_low}{field_name}FID));
        {type_java_array}* {arg_low}{field_name}Data = {env}->Get{capitalize_first_letter(convert_aidl_type(array.type.name))}ArrayElements({arg_low}{field_name}, nullptr);
        jsize {arg_low}{field_name}Length = {env}->GetArrayLength({arg_low}{field_name});"""
            else:
                string_array_gen = ""
                if(type_checked == 3):
                    string_array_gen = f"{field.type.namespace.name}::{field.type.name}"
                elif(type_checked == 5):
                    string_array_gen = f"std::vector<std::string>"
                fields_str += f"""\n\t\t{string_array_gen} _{arg_low}{field_name};
        jfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, \"{field_name_low}\", \"[{type_jni_array}\");
        jobjectArray {arg_low}{field_name} = reinterpret_cast<jobjectArray>({env}->GetObjectField({arg_low}, {arg_low}{field_name}FID));
        jsize {arg_low}{field_name}Length = {env}->GetArrayLength({arg_low}{field_name});
        jstring {arg_low}{field_name}Str = {env}->NewStringUTF("");
        //jclass {arg_low}{field_name}StrClazz = {env}->GetObjectClass({arg_low}{field_name}Str);
        for(int s = 0; s < {arg_low}{field_name}Length; s++){{
            {arg_low}{field_name}Str = (jstring){env}->GetObjectArrayElement({arg_low}{field_name}, s);
            const char *{arg_low}{field_name}Cstr = {env}->GetStringUTFChars({arg_low}{field_name}Str, nullptr);
            _{arg_low}{field_name}.push_back(std::string({arg_low}{field_name}Cstr));
        }}
        {env}->DeleteLocalRef({arg_low}{field_name}Str);"""
            if(type_checked == 3 and array.type.name != "String"):
                fields_str += f"""\n\t\t/*{packages}::*/{field.type.namespace.name}::{field.type.name} _{arg_low}{field_name}({arg_low}{field_name}Data, {arg_low}{field_name}Data + {arg_low}{field_name}Length);"""
            elif(type_checked == 5):
                fields_str += f"""\n\t\tstd::vector<{type_cpp_array}> _{arg_low}{field_name}({arg_low}{field_name}Data, {arg_low}{field_name}Data + {arg_low}{field_name}Length);"""
            elif(type_checked == 6):
                fields_str += f"""\n\t\t/*{packages}::*/{field.type.reference.namespace.name}::{field.type.reference.name} _{arg_low}{field_name}({arg_low}{field_name}Data, {arg_low}{field_name}Data + {arg_low}{field_name}Length);"""
            
            fields_str += f"""\n\t\t_{arg_low}.set{field_name}(_{arg_low}{field_name});"""
        ## interface struct
        elif(type_checked == 4 or type_checked == 7):
            fields_str_temp = ""
            type_fields_jni = struct_fields(struct=field.type.reference.fields, java_class=java_class)
            defined_field = ""
            if(len(field.type.name.split('.')) > 1):
                defined_field = field.type.name.split('.')[0]
            else:
                defined_field = field.type.reference.namespace.name
            fields_str += f"""\n\t\tjfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, \"{field_name_low}\", \"L{java_class}{defined_field}{interface_extension}${field.type.name.split('.')[-1]};\");
        jobject {arg_low}{field_name} = {env}->GetObjectField({arg_low}, {arg_low}{field_name}FID);
        jclass {defined_field}{field.type.reference.name}Clazz = {env}->GetObjectClass({arg_low}{field_name});
        /*{packages}::*/{field.type.reference.namespace.name}::{field.type.reference.name} _{arg_low}{field_name};"""
            fields_str += struct_fields_method_in_gen(field, interface, packages, java_class, field_name_extends=arg_low)
            fields_str += f"""\n\t\t_{arg_low}.set{field_name}(_{arg_low}{field_name});
        """
            
        elif(type_checked == 8):
            reference_cap = (field.type.reference.namespace.name)
            reference_type = field.type.reference.name
            fields_str += f"""
        jfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, "{field_name_low}", "B");
        jbyte {arg_low}{field_name} = {env}->GetByteField({arg_low}, {arg_low}{field_name}FID);
        //jmethodID {reference_cap}{reference_type}EnumToInt = {env}->GetMethodID({lower_first_letter(interface.name)}Client->{reference_cap}Clazz, "{capitalize_first_letter(reference_type)}ToInt", "(L{java_class}{reference_cap}{interface_extension}${reference_type};)B");
        //jbyte {arg_low}{field_name_low}Int = {env}->CallByteMethod({reference_cap}Instance, {reference_cap}{reference_type}EnumToInt, {arg_low}{field_name});
        uint8_t _{arg_low}{field_name}Int = static_cast<uint8_t>({arg_low}{field_name});
        {reference_cap}::{reference_type} _{arg_low}{field_name} = {reference_cap}::{reference_type}::Literal(_{arg_low}{field_name}Int);
        _{arg_low}.set{field_name}(_{arg_low}{field_name});"""
        # Complex array
        elif(type_checked == 9):
            defined_field = field.type.reference.type.reference.namespace.name
            defined = field.type.reference.type.reference.namespace.name
            fields_str += f"""\n\t\tjfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, \"{field_name_low}\", \"[L{java_class}{defined_field}{interface_extension}${field.type.reference.type.name};\");
        jobjectArray {arg_low}{field_name} = (jobjectArray){env}->GetObjectField({arg_low}, {arg_low}{field_name}FID);"""
            fields_str += complex_array(field, interface, packages, java_class, arg_low, 6, is_implicit=False)
            fields_str += f"""_{arg_low}.set{field_name}(_{arg_low}{field_name});"""
        elif(type_checked == 10):
            defined_field = field.type.type.reference.namespace.name
            defined = field.type.type.reference.namespace.name
            fields_str += f"""\n\t\tjfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, \"{field_name_low}\", \"[L{java_class}{defined_field}{interface_extension}${field.type.type.reference.name};\");
        jobjectArray {arg_low}{field_name} = (jobjectArray){env}->GetObjectField({arg_low}, {arg_low}{field_name}FID);"""
            fields_str += complex_array(field, interface, packages, java_class, arg_low, 6, is_implicit=True)
            fields_str += f"""_{arg_low}.set{field_name}(_{arg_low}{field_name});"""
    
    ### 중복 선언 제거
    duplicated_line = set()
    unique_lines = []
    duplicated_words = []
    lines = fields_str.split('\n')
    for line in lines:
        if line not in duplicated_line or '}' in line:
            words = line.split()
            if(len(words) >= 2):
                if words[0] in ["jclass", "jmethodID"] and ("Clazz" or "Constructor" or "MID" in words[1]):
                    if(words[0],words[1]) not in duplicated_words:
                        duplicated_words.append((words[0], words[1]))
                        unique_lines.append(line)
                        duplicated_line.add(line)
                else:
                    duplicated_line.add(line)
                    unique_lines.append(line)
            else:
                duplicated_line.add(line)            
                unique_lines.append(line)
    fields_str = '\n'.join(unique_lines)
    ###
    
    
    return fields_str
    
def struct_fields_method_out_gen(arg, interface, packages, java_class, field_name_extends=""):
    fields_str = ""
    field_type_java = ""
    field_type_jni = ""
    field_name = ""
    array = ""
    type_checked = 0
    struct = arg.type.reference
    env = "env"
    defined = ""
    interface_extension = "JNI"
    if(len(arg.type.name.split('.')) > 1):
        defined = arg.type.name.split('.')[0]
    else:
        defined = arg.type.reference.namespace.name
        
    if(field_name_extends == ""):
        arg_low = field_name_extends + lower_first_letter(arg.name)
    else:
        arg_low = field_name_extends + capitalize_first_letter(arg.name)
    
    for field in arg.type.reference.fields.values():
        field_name = capitalize_first_letter(field.name)
        field_name_low = lower_first_letter(field.name)
        type_checked = check_type_ver2(field, interface)
        if(type_checked == 1):
            field_type_jni = convert_jni_type(field.type.name)
            field_type_java = convert_java_type(field.type.name)
            field_type_cpp = convert_cpp_type(field.type.name)
            fields_str += f"""{field_type_java} {arg_low}{field_name} = static_cast<{field_type_java}>(_{arg_low}.get{field_name}());
        """
        elif(type_checked == 2):
            field_type_jni = convert_jni_type(field.type.name)
            field_type_java = convert_java_type(field.type.name)
            fields_str += f"""{field_type_java} {arg_low}{field_name} = {env}->NewStringUTF((_{arg_low}.get{field_name}()).c_str());
        """
        elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
            if(type_checked == 3):
                array = interface.arrays[field.type.name]
                array_gen = "{}::{}".format(array.namespace.name, array.name)
            elif(type_checked == 5):
                array = field.type
                array_gen = "std::vector<{}>".format(convert_cpp_type(array.type.name))
            elif(type_checked == 6):
                array = field.type.reference
                array_gen = "{}::{}".format(array.type.reference.namespace.name, array.type.reference.name)
            type_java_array = convert_java_type(array.type.name)
            temp = ""
            temp_cast = ""
            if(isUnsigned(array.type.name) or array.type.name == "Int16"):
                temp += "Signed"
                temp_cast += f"""
        std::vector<{upcast_cpp_int(array.type.name)}> _{arg_low}{field_name}Signed;
        _{arg_low}{field_name}Signed.assign(_{arg_low}{field_name}.begin(), _{arg_low}{field_name}.end());"""
            if(array.type.name != "String"):
                fields_str += f"""{array_gen} _{arg_low}{field_name} = _{arg_low}.get{field_name}();{temp_cast}
        {type_java_array}* {arg_low}{field_name}Data = static_cast<{type_java_array}*>(_{arg_low}{field_name}{temp}.data());
        jsize {arg_low}{field_name}Length = static_cast<jsize>(_{arg_low}{field_name}{temp}.size());
        {type_java_array}Array {arg_low}{field_name};
        {env}->Set{capitalize_first_letter(convert_aidl_type(array.type.name))}ArrayRegion({arg_low}{field_name}, 0, {arg_low}{field_name}Length, {arg_low}{field_name}Data);
        """
            # String array
            else:
                fields_str += f"""{array_gen} _{arg_low}{field_name} = _{arg_low}.get{field_name}();
        jsize {arg_low}{field_name}Length = static_cast<jsize>(_{arg_low}{field_name}.size());
        jstring {arg_low}{field_name}Str = {env}->NewStringUTF("");
        jclass {arg_low}{field_name}StrClazz = {env}->GetObjectClass({arg_low}{field_name}Str);
        jobjectArray {arg_low}{field_name} = {env}->NewObjectArray({arg_low}{field_name}Length, {arg_low}{field_name}StrClazz, nullptr);
        for(int ss = 0; ss < {arg_low}{field_name}Length; ss++){{
            {arg_low}{field_name}Str = {env}->NewStringUTF(_{arg_low}{field_name}[ss].c_str());
            {env}->SetObjectArrayElement({arg_low}{field_name}, ss, {arg_low}{field_name}Str);
        }}
        {env}->DeleteLocalRef({arg_low}{field_name}Str);
        """
        ###
        elif(type_checked == 4 or type_checked == 7):
            type_fields_jni = struct_fields(struct=field.type.reference.fields, java_class=java_class)
            defined_field = ""
            if(len(field.type.name.split('.')) > 1):
                defined_field = field.type.name.split('.')[0]
            else:
                defined_field = field.type.reference.namespace.name
            fields_str += f"""_{arg_low}{field_name} = _{arg_low}.get{field_name}();
        jfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, \"{field_name_low}\", \"L{java_class}{defined_field}{interface_extension}${field.type.name.split('.')[-1]};\");
        jobject {arg_low}{field_name} = {env}->GetObjectField({arg_low}, {arg_low}{field_name}FID);
        jclass {defined_field}{field.type.reference.name}Clazz = {env}->GetObjectClass({arg_low}{field_name});
        /*{packages}::*/{field.type.reference.namespace.name}::{field.type.reference.name} _{arg_low}{field_name};
        jmethodID {defined_field}{field.type.reference.name}Constructor = {env}->GetMethodID({defined_field}{field.type.reference.name}Clazz, "<init>", "({type_fields_jni})V");"""
            
            fields_str += f"""{arg_low}{field_name} = {env}->NewObject({defined_field}{field.type.reference.name}Clazz, {defined_field}{field.type.reference.name}Constructor"""
            for value in field.type.reference.fields.values():
                fields_str += ", {}{}{}".format(arg_low,field_name,capitalize_first_letter(value.name))
            fields_str += ");\n\t\t"
        elif(type_checked == 8):
            reference_cap = (field.type.reference.namespace.name)
            reference_type = field.type.reference.name
            fields_str += f"""
        jfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, "{field_name_low}", "B");
        jbyte {arg_low}{field_name} = {env}->GetByteField({arg_low}, {arg_low}{field_name}FID);
        //jmethodID {reference_cap}{reference_type}EnumToInt = {env}->GetMethodID({lower_first_letter(interface.name)}Client->{reference_cap}Clazz, "{capitalize_first_letter(reference_type)}ToInt", "(L{java_class}{reference_cap}{interface_extension}${reference_type};)B");
        //jbyte {arg_low}{field_name_low}Int = {env}->CallByteMethod({reference_cap}Instance, {reference_cap}{reference_type}EnumToInt, {arg_low}{field_name});
        uint8_t _{arg_low}{field_name_low}Int = static_cast<uint8_t>({arg_low}{field_name_low});
        {reference_cap}::{reference_type} _{arg_low}{field_name_low} = {reference_cap}::{reference_type}::Literal(_{arg_low}{field_name_low}Int);
        _{arg_low}.set{field_name}(_{arg_low}{field_name_low});"""
        elif(type_checked == 9):
            defined_field = field.type.reference.type.reference.namespace.name
        #     fields_str += f"""
        # jfieldID {arg_low}{field_name}FID = {env}->GetFieldID({defined}{arg.type.reference.name}Clazz, \"{field_name_low}\", \"L{java_class}{field.type.reference.type.reference.namespace.name}{interface_extension}${field.type.reference.type.reference.name};\");
        # jobject {arg_low}{field_name} = {env}->GetObjectField({arg_low}, {arg_low}{field_name}FID);
        # jclass {defined_field}{field.type.reference.name}Clazz = {env}->GetObjectClass({arg_low}{field_name});
        # /*{packages}::*/{field.type.reference.namespace.name}::{field.type.reference.name} _{arg_low}{field_name};
        # """
            fields_str += f"""
        {field.type.reference.namespace.name}::{field.type.reference.name} _{arg_low}{field_name} = _{arg_low}.get{field_name}();"""
            fields_str += complex_array(field, interface, packages, java_class, arg_low, 5, is_implicit=False)    
            
        elif(type_checked == 10):
            fields_str += f"""
        std::vector<{field.type.type.reference.namespace.name}::{field.type.type.reference.name}> _{arg_low}{field_name} = _{arg_low}.get{field_name}();"""
            fields_str += complex_array(field, interface, packages, java_class, arg_low, 5, is_implicit=True)    
        
    ### 중복 선언 제거
    duplicated_line = set()
    unique_lines = []
    duplicated_words = []
    lines = fields_str.split('\n')
    for line in lines:
        if line not in duplicated_line or '}' in line:
            words = line.split()
            if(len(words) >= 2):
                if words[0] in ["jclass", "jmethodID"] and ("Clazz" or "Constructor" or "MID" in words[1]):
                    if(words[0],words[1]) not in duplicated_words:
                        duplicated_words.append((words[0], words[1]))
                        unique_lines.append(line)
                        duplicated_line.add(line)
                else:
                    duplicated_line.add(line)
                    unique_lines.append(line)
            else:
                duplicated_line.add(line)            
                unique_lines.append(line)
    fields_str = '\n'.join(unique_lines)
    ###
    
    
    return fields_str


def generate_src_method(method, package_name, interface, java_package_name):
    package_names = package_name.split('.')
    src_str = ""
    java_package = ""
    java_class = ""
    for name in java_package_name:
        java_package += "{}_".format(name)
        java_class += "{}/".format(name)
    cpp_package = ""
    cpp_namespace = ""
    for name in package_names:
        cpp_package += "{}/".format(name)
        cpp_namespace += "{}::".format(name)
    version = interface.version.major
    method_low = lower_first_letter(method.name)
    method_cap = capitalize_first_letter(method.name)
    interface_cap = interface.name
    interface_low = lower_first_letter(interface.name)
    return_type = ""
    out_args = ""
    out_args_cpp_gen = ""
    out_args_cpp_val = ""
    out_args_return = ""
    out_args_after = ""
    out_args_type_jni = ""
    in_args = ""
    in_args_cpp_gen = ""
    in_args_cpp_val = ""
    env = "env"
    interface_extension = "JNI"
    
    errors_str = ""
    errors_method_call = ""
    if(method.errors):
        if(isinstance(method.errors, ast.Reference)):
            errors_str += f"""
        {method.errors.reference.namespace.name}::{method.errors.reference.name} _{lower_first_letter(method.errors.name)};"""
            errors_method_call = ", _{}".format(lower_first_letter(method.errors.name))
    
    # Method 1: Return type of method
    if len(method.out_args.values()) > 1:
        return_type = "jobject"
    elif len(method.out_args.values()) == 1:
        arg =  next(iter(method.out_args.values()))
        type_checked = check_type_ver2(arg, interface)
        if(type_checked == 1 or type_checked == 2):
            return_type = "{}".format(convert_java_type(arg.type.name))
        elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
            if(type_checked == 3):
                array = interface.arrays[arg.type.name]
            elif(type_checked == 5):
                array = arg.type
            elif(type_checked == 6):
                array = arg.type.reference
            return_type = "{}Array".format(convert_java_type(array.type.name))
        elif(type_checked == 8):
            return_type = "jbyte"
        elif(type_checked == 9 or type_checked == 10 or type_checked == 11):
            return_type = "jobjectArray"
        else:
            return_type = "jobject"
    else:
        return_type = "void"

    cnt = 1
    for arg in method.out_args.values():
        type_checked = check_type_ver2(arg, interface)
        arg_low = lower_first_letter(arg.name)
        arg_cap = capitalize_first_letter(arg.name)
        out_args_cpp_val += ", _{}".format(arg_low)
        out_args_return += "{}".format(arg_low)
        ### type 마다 다르게 처리됨
        if(type_checked == 1 or type_checked == 2):
            out_args_type_jni += "{}".format(convert_jni_type(arg.type.name))
            out_args_cpp_gen += "{} _{};\n\t\t".format(convert_cpp_type(arg.type.name), arg_low)
            if(type_checked == 1):
                out_args_after += "\n\t\t{} {} = static_cast<{}>(_{});".format(convert_java_type(arg.type.name), arg_low, convert_java_type(arg.type.name),arg_low)
            else:
                out_args_after += "\n\t\t{} {} = env->NewStringUTF(_{}.c_str());".format(convert_java_type(arg.type.name), arg_low, arg_low)
            
        elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
            if(type_checked == 3):
                array = interface.arrays[arg.type.name]
            elif(type_checked == 5):
                array = arg.type
            elif(type_checked == 6):
                array = arg.type.reference
            array_java_type = convert_java_type(array.type.name)
            array_jni_type = capitalize_first_letter(convert_java_code_type(array.type.name))
            array_cpp_type = upcast_cpp_int(array.type.name)
            out_args_type_jni += "[{}".format(convert_jni_type(array.type.name))
            if(type_checked == 3 or type_checked == 6):
                out_args_cpp_gen += f"""{arg.type.reference.namespace.name}::{arg.type.reference.name} _{arg_low};
        """
            elif(type_checked == 5):
                out_args_cpp_gen += f"""std::vector<{convert_cpp_type(array.type.name)}> _{arg_low};
        """
            ### jshort (int16_t) to int cast
            short_to_int = ""
            int_extension = ""
            if(isUnsigned(array.type.name) or array.type.name == "Int16"):
                out_args_after += f"""
        std::vector<{array_cpp_type}> _{arg_low}Signed;
        _{arg_low}Signed.assign(_{arg_low}.begin(), _{arg_low}.end());
        {array_java_type}* {arg_low}Data = static_cast<{array_java_type}*>(_{arg_low}Signed.data());"""
            # String array
            elif(array.type.name == "String"):
                out_args_after += f"""
        jsize {arg_low}Length = static_cast<jsize>(_{arg_low}.size());
        jstring {arg_low}Str = {env}->NewStringUTF("");
        jclass {arg_low}StrClazz = {env}->GetObjectClass({arg_low}Str);
        jobjectArray {arg_low} = {env}->NewObjectArray({arg_low}Length, {arg_low}StrClazz, nullptr);
        for(int sss = 0; sss < {arg_low}Length; sss++){{
            {arg_low}Str = {env}->NewStringUTF(_{arg_low}[sss].c_str());
            {env}->SetObjectArrayElement({arg_low}, sss, {arg_low}Str);
        }}
        {env}->DeleteLocalRef({arg_low}Str);
        """
            #
            else:
                out_args_after += short_to_int
                out_args_after += f"""
        {array_java_type}* {arg_low}Data = static_cast<{array_java_type}*>(_{int_extension}{arg_low}.data());"""
            if(array.type.name != "String"):
                out_args_after += f"""
        jsize {arg_low}Length = static_cast<jsize>(_{arg_low}.size());
        {array_java_type}Array {arg_low} = env->New{array_jni_type}Array({arg_low}Length);
        env->Set{array_jni_type}ArrayRegion({arg_low}, 0, {arg_low}Length, {arg_low}Data);
        """
        elif(type_checked == 4 or type_checked == 7):
            defined = capitalize_first_letter(arg.type.reference.namespace.name)
            struct_name = capitalize_first_letter(arg.type.reference.name)
            struct_fields_jni = struct_fields(arg.type.reference.fields,java_class=java_class)
            out_args_type_jni += "L{}{}JNI${};".format(java_class,defined,arg.type.reference.name)
            out_args_cpp_gen += f"""
        {defined}::{arg.type.reference.name} _{arg_low};
        """
            out_args_after += f"""jclass out{defined}{struct_name}Clazz = {env}->FindClass("{java_class}{defined}{interface_extension}${arg.type.reference.name}");
        jmethodID out{defined}{struct_name}Constructor = {env}->GetMethodID(out{defined}{struct_name}Clazz, "<init>", "({struct_fields_jni})V");
        """
            out_args_after += struct_fields_method_out_gen(arg,interface,cpp_package,java_class, "")
            out_args_after += f"""jobject {arg_low} = {env}->NewObject(out{defined}{struct_name}Clazz, out{defined}{struct_name}Constructor"""
            for field in arg.type.reference.fields.values():
                out_args_after += ", {}{}".format(arg_low, capitalize_first_letter(field.name));
            out_args_after += ");"
        elif(type_checked == 8):
            reference_cap = capitalize_first_letter(arg.type.reference.namespace.name)
            reference_type = capitalize_first_letter(arg.type.reference.name)
            out_args_type_jni += "B"
        #     out_args_cpp_gen += f"""jclass {reference_cap}{reference_type}Clazz = {env}->GetObjectClass({reference_cap}Instance);
        # {reference_cap}::{reference_type} _{arg_low};
        # """
            out_args_cpp_gen += f"""{reference_cap}::{reference_type} _{arg_low};
        """
            out_args_after += f"""uint8_t _{arg_low}Int = static_cast<uint8_t>(_{arg_low});
        jbyte {arg_low} = static_cast<jbyte>(_{arg_low}Int);
        """
        ### Complex array
        elif(type_checked == 9):
            out_args_cpp_gen += f"""
        {arg.type.reference.namespace.name}::{arg.type.reference.name} _{arg_low};
        """
            out_args_type_jni += "[L{}{}JNI${};".format(java_class,arg.type.reference.type.reference.namespace.name,arg.type.reference.type.reference.name)
            out_args_after += complex_array(arg, interface, cpp_namespace, java_class, "", 5)
        elif(type_checked == 10):
            out_args_cpp_gen += f"""
        std::vector<{arg.type.type.reference.namespace.name}::{arg.type.type.reference.name}> _{arg_low};
        """
            out_args_type_jni += "[L{}{}JNI${};".format(java_class,arg.type.type.reference.namespace.name,arg.type.type.reference.name)
            out_args_after += complex_array(arg, interface, cpp_namespace, java_class, "", 5, is_implicit=True)
        elif(type_checked == 11):
            out_args_cpp_gen += f"""
        {arg.type.reference.namespace.name}::{arg.type.reference.name} _{arg_low};
        """
            out_args_type_jni += "[L{}{}JNI${};".format(java_class,arg.type.reference.namespace.name,arg.type.reference.name)
            out_args_after += generate_src_map(arg, cpp_namespace, interface, java_class, "", 0, 4)
        ###
        if len(method.out_args.values()) > 1 and cnt < len(method.out_args.values()):
            out_args_return += ", "
            cnt += 1
    

    # In arguments
    for arg in method.in_args.values():
        ### type 마다 다르게 처리됨
        arg_low = lower_first_letter(arg.name)
        arg_cap = capitalize_first_letter(arg.name)
        type_checked = check_type_ver2(arg, interface)
        if(type_checked == 1):
            in_args += ", {} {}".format(convert_java_type(arg.type.name), arg_low)
            in_args_cpp_gen += "{} _{} = static_cast<{}>({});\n\t\t".format(convert_cpp_type(arg.type.name),arg_low,convert_cpp_type(arg.type.name),arg_low)
        elif(type_checked == 2):
            in_args += ", {} {}".format(convert_java_type(arg.type.name), arg_low)
            in_args_cpp_gen += "{} _{} = {}->GetStringUTFChars({}, nullptr);\n\t\t".format(convert_cpp_type(arg.type.name),arg_low,env,arg_low)
        elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
            if(type_checked == 3):
                array = interface.arrays[arg.type.name]
            elif(type_checked == 5):
                array = arg.type
            elif(type_checked == 6):
                array = arg.type.reference
            array_java_type = convert_java_type(array.type.name)
            if(array.type.name == "String"):
                array_java_type = "jobject"
            array_jni_type = capitalize_first_letter(convert_aidl_type(array.type.name))
            in_args += ", {}Array {}".format(array_java_type, arg_low)
            ### String array 별도 처리
            if(array.type.name != "String"):
                in_args_cpp_gen += f"""{array_java_type}* {arg_low}Data = {env}->Get{array_jni_type}ArrayElements({arg_low}, nullptr);
        jsize {arg_low}Length = {env}->GetArrayLength({arg_low});
        """
            else:
                in_args_string_gen = ""
                if(type_checked == 3):
                    in_args_string_gen = f"{arg.type.reference.namespace.name}::{arg.type.reference.name}"
                elif(type_checked == 5):
                    in_args_string_gen = f"std::vector<std::string>"
                in_args_cpp_gen += f"""{in_args_string_gen} _{arg_low};
        jsize {arg_low}Length = {env}->GetArrayLength({arg_low});
        jstring {arg_low}Str = {env}->NewStringUTF("");
        for(int sss = 0; sss < {arg_low}Length; sss++){{
            {arg_low}Str = (jstring){env}->GetObjectArrayElement({arg_low}, sss);
            const char *{arg_low}Cstr = {env}->GetStringUTFChars({arg_low}Str, nullptr);
            _{arg_low}.push_back(std::string({arg_low}Cstr));
        }}
        {env}->DeleteLocalRef({arg_low}Str);
        """
            if((type_checked == 3 and array.type.name != "String") or type_checked == 6):
                in_args_cpp_gen += f"""{arg.type.reference.namespace.name}::{arg.type.reference.name} _{arg_low}({arg_low}Data, {arg_low}Data + {arg_low}Length);
        """
            elif(type_checked == 5 and array.type.name != "String"):
                in_args_cpp_gen += f"""std::vector<{convert_cpp_type(array.type.name)}> _{arg_low}({arg_low}Data, {arg_low}Data + {arg_low}Length);
        """
        elif(type_checked == 4 or type_checked == 7):
            defined = capitalize_first_letter(arg.type.reference.namespace.name)
            if(type_checked == 4):
                struct_name = arg.type.name
            else:
                struct_name = arg.type.reference.name
            in_args += ", jobject {}".format(arg_low)
            in_args_cpp_gen += f"""jclass {defined}{struct_name}Clazz = {env}->GetObjectClass({arg_low});
        {defined}::{struct_name} _{arg_low};
        """
            in_args_cpp_gen += struct_fields_method_in_gen(arg,interface,cpp_package,java_class,"")
            
        elif(type_checked == 8):
            reference_cap = capitalize_first_letter(arg.type.reference.namespace.name)
            reference_type = capitalize_first_letter(arg.type.reference.name)
            in_args += ", jbyte {}".format(arg_low)
        #     in_args_cpp_gen += f"""jclass {reference_cap}{reference_type}Clazz = {env}->GetObjectClass({reference_cap}Instance);
        # jbyte {arg_low}Int = {arg_low};
        # uint8_t _{arg_low}Int = static_cast<uint8_t>({arg_low}Int);
        # {reference_cap}::{reference_type} _{arg_low} = {reference_cap}::{reference_type}::Literal(_{arg_low}Int);
        # """
            in_args_cpp_gen += f"""jbyte {arg_low}Int = {arg_low};
        uint8_t _{arg_low}Int = static_cast<uint8_t>({arg_low}Int);
        {reference_cap}::{reference_type} _{arg_low} = {reference_cap}::{reference_type}::Literal(_{arg_low}Int);
        """
        ### Complex Array
        elif(type_checked == 9):
            in_args += ", jobjectArray {}".format(arg_low)
            in_args_cpp_gen += complex_array(arg, interface, cpp_namespace, java_class, "", 6)
        elif(type_checked == 10):
            in_args += ", jobjectArray {}".format(arg_low)
            in_args_cpp_gen += complex_array(arg, interface, cpp_namespace, java_class, "", 6, is_implicit=True)
        elif(type_checked == 11):
            in_args += ", jobjectArray {}".format(arg_low)
            in_args_cpp_gen += generate_src_map(arg,cpp_namespace,interface,java_class,"", 0, 2)
        ###
        in_args_cpp_val += "_{}, ".format(arg_low)
    
    src_str += f"""
    JNIEXPORT {return_type} JNICALL
    Java_{java_package}{interface_cap}{interface_extension}_{method_cap}(JNIEnv *env, jobject instance, jlong proxyptr{in_args}){{"""
    # proxy translation
    src_str += f"""
        {interface_cap}Client* _{interface_cap}Client = reinterpret_cast<{interface_cap}Client*>(proxyptr);
        _{interface_cap}Client->{interface_cap}Instance = env->NewGlobalRef(instance);"""   
    # if there is an eumuerator in the in_args or out_args
    list_get = []
    # if(type_checked == 8 or type_checked == 4 or type_checked == 6 or type_checked == 7):
    for arg in method.in_args.values():
        if(isinstance(arg.type, ast.Reference)):
            if(isinstance(arg.type.reference, ast.Enumeration) and (arg.type.reference.namespace.name not in list_get)):
                list_get.append(arg.type.reference.namespace.name)
                src_str += f"""
        jobject {arg.type.reference.namespace.name}Instance = {env}->AllocObject(_{interface_cap}Client->{arg.type.reference.namespace.name}Clazz);
        """
            elif(isinstance(arg.type.reference, ast.Struct)):
                for field in arg.type.reference.fields.values():
                    if(isinstance(field.type, ast.Reference)):
                        if(isinstance(field.type.reference, ast.Enumeration) and (field.type.reference.namespace.name not in list_get)):
                            list_get.append(field.type.reference.namespace.name)
                            src_str += f"""
        jobject {field.type.reference.namespace.name}Instance = {env}->AllocObject(_{interface_cap}Client->{field.type.reference.namespace.name}Clazz);
        """
    for arg in method.out_args.values():
        if(isinstance(arg.type, ast.Reference)):
            if(isinstance(arg.type.reference, ast.Enumeration) and (arg.type.reference.namespace.name not in list_get)):
                list_get.append(arg.type.reference.namespace.name)
                src_str += f"""
        jobject {arg.type.reference.namespace.name}Instance = {env}->AllocObject(_{interface_cap}Client->{arg.type.reference.namespace.name}Clazz);
        """
            elif(isinstance(arg.type.reference, ast.Struct)):
                for field in arg.type.reference.fields.values():
                    if(isinstance(field.type, ast.Reference)):
                        if(isinstance(field.type.reference, ast.Enumeration) and (field.type.reference.namespace.name not in list_get)):
                            list_get.append(field.type.reference.namespace.name)
                            src_str += f"""
        jobject {field.type.reference.namespace.name}Instance = {env}->AllocObject(_{interface_cap}Client->{field.type.reference.namespace.name}Clazz);
        """ 
        

    
    # if return has multiple variables
    if len(method.out_args.values()) > 1:
        src_str += f"""
        jclass {method_low}Clazz = env->FindClass("{java_class}{interface_cap}{interface_extension}${method_cap}ReturnType");
        jmethodID {method_low}Constructor = env->GetMethodID({method_low}Clazz, "<init>", "({out_args_type_jni})V");"""
    # body
    src_str += f"""
        {in_args_cpp_gen}{out_args_cpp_gen}
        CommonAPI::CallStatus callStatus;{errors_str}
        _{interface_cap}Client->myProxy->{method.name}({in_args_cpp_val}callStatus{errors_method_call}{out_args_cpp_val});
        if(callStatus != CommonAPI::CallStatus::SUCCESS){{
            LOGE("{method_low} failed!");
        }}
        {out_args_after}"""
    # retrun
    if len(method.out_args.values()) > 1:
        src_str += f"""
        jobject {method_cap}ReturnType = env->NewObject({method_low}Clazz, {method_low}Constructor, {out_args_return});
        return {method_cap}ReturnType;
    }}\n"""
    elif len(method.out_args.values()) == 1:
        src_str += f"""
        return {out_args_return};
    }}\n"""
    else:
        src_str += f"""
    }}"""
        
    return src_str
############################### Broadcast #############################################################

### it is the same as attribute sub and unsub but slightly different
def generate_src_broadcast(broadcast, package_name, interface, java_package_name):
    src_str = ""
    package_names = package_name.split('.')
    cpp_package = ""
    for name in package_names:
        cpp_package += "::{}".format(name)
    
    java_package = ""
    java_class = ""
    for name in java_package_name:
        java_package += "{}_".format(name)
        java_class += "{}/".format(name)
    
    version = interface.version.major
    #interface_cap = capitalize_first_letter(interface.name)
    interface_cap = interface.name
    interface_low = lower_first_letter(interface.name)
    interface_extension = "JNI"
    broadcast_cap = capitalize_first_letter(broadcast.name)
    broadcast_low = lower_first_letter(broadcast.name)
    
    # out of broadcast ([content]) at the beginning of lambda
    out_args_lambda = ""
    out_args_jni = struct_fields(broadcast.out_args, java_class= java_class)
    count_args = 1
    for out_arg in broadcast.out_args.values():
        arg_type_checked = check_type_ver2(out_arg, interface)
        if(arg_type_checked == 1 or arg_type_checked == 2):
            out_args_lambda += "{} _{}".format(convert_cpp_type(out_arg.type.name),lower_first_letter(out_arg.name))
        elif(arg_type_checked > 2 and arg_type_checked <= 9):
            if(out_arg.type.name is None):
                out_args_lambda += "std::vector<{}> _{}".format(convert_cpp_type(out_arg.type.type.name),lower_first_letter(out_arg.name))
            else:
                if(isinstance(out_arg.type, ast.Reference)):
                    out_args_lambda += "{}::{} _{}".format(out_arg.type.reference.namespace.name, out_arg.type.reference.name, lower_first_letter(out_arg.name))
        elif(arg_type_checked == 10):
            out_args_lambda += "std::vector<{}::{}> _{}".format(out_arg.type.type.reference.namespace.name,convert_cpp_type(out_arg.type.type.name),lower_first_letter(out_arg.name))
        elif(arg_type_checked == 11):
            out_args_lambda += "{}::{} _{}".format(out_arg.type.reference.namespace.name,convert_cpp_type(out_arg.type.name),lower_first_letter(out_arg.name))
        #out_args_jni += 
        if(count_args < len(broadcast.out_args.values())):
            out_args_lambda += ", "
            count_args += 1
    
    env = "env"
    
    # broadcast 1
    src_str += f"""\tJNIEXPORT void JNICALL
    Java_{java_package}{interface_cap}{interface_extension}_subBroadcast{broadcast_cap}(JNIEnv *env, jobject instance, jlong proxyptr){{
        {interface_cap}Client* _{interface_cap}Client = reinterpret_cast<{interface_cap}Client*>(proxyptr);
        _{interface_cap}Client->{interface_cap}Instance = {env}->NewGlobalRef(instance);
        _{interface_cap}Client->myProxy->get{broadcast_cap}Event().subscribe(
            [_{interface_cap}Client]({out_args_lambda}){{
            JNIEnv* {env};
            if((jvm)->AttachCurrentThread(&{env},nullptr) != JNI_OK){{
                LOGE("Attach Error at subBroadcast{broadcast_cap}!");  
            }}
            jobject {interface_cap}Instance = _{interface_cap}Client->{interface_cap}Instance;
            jclass {interface_cap}Clazz = {env}->GetObjectClass({interface_cap}Instance);
            """
    
    # broadcast 2: Obtaining Interface and TypeCollection Clazz, affected by out_args of broadcast
    reference_list = [interface_cap]
    for out_arg in broadcast.out_args.values():
        if(isinstance(out_arg.type, ast.Reference)):
            if(out_arg.type.reference.namespace.name not in reference_list):
                reference_list.append(out_arg.type.reference.namespace.name)
                src_str += f"""jobject {capitalize_first_letter(out_arg.type.reference.namespace.name)}Instance = {env}->AllocObject(_{interface_cap}Client->{capitalize_first_letter(out_arg.type.reference.namespace.name)}Clazz);
                jclass {capitalize_first_letter(out_arg.type.reference.namespace.name)}Clazz = {env}->GetObjectClass({capitalize_first_letter(out_arg.type.reference.namespace.name)}Instance);
                """
    
# Starting from this part, things can be changed when integration with android stub occurs
    # broadcast 3: Obtaining Method ID of the handler
    src_str += f"""jmethodID {broadcast_cap}MID = {env}->GetMethodID({interface_cap}Clazz, "subBroadcast{broadcast_cap}Callback", "({out_args_jni})V");
                """
                
    # broadcast 4: Necessary jobs for each out_arg in out_args, same as sub_struct_gen
    for out_arg in broadcast.out_args.values():
        type_checked = check_type_ver2(out_arg, interface)
        if(type_checked < 1 or type_checked > 11):
            continue
        arg_cap = capitalize_first_letter(out_arg.name)
        arg_low = lower_first_letter(out_arg.name)
        ## Primitive except String
        if(type_checked == 1):
            type_java = convert_java_type(out_arg.type.name)
            src_str += f"""{type_java} {arg_low} = static_cast<{type_java}>(_{arg_low});
                """ 
        ## String
        elif(type_checked == 2):
            type_java = convert_java_type(out_arg.type.name)
            src_str += f"""{type_java} {arg_low} = {env}->NewStringUTF(_{arg_low}.c_str());
                """
        ## Arrays
        elif(type_checked == 3 or type_checked == 5 or type_checked ==6 ):
            if(type_checked == 3):
                array = interface.arrays[out_arg.type.name]
            elif(type_checked == 5):
                array = out_arg.type
            elif(type_checked == 6):
                array = out_arg.type.reference
            ### varibles for array
            type_array = capitalize_first_letter(convert_aidl_type(array.type.name))
            type_java_array = convert_java_type(array.type.name)
            type_cpp_array = upcast_cpp_int(array.type.name)
            ### jshort (int16_t) to int cast
            short_to_int = ""
            int_extension = ""
            if(isUnsigned(array.type.name) or array.type.name == "Int16"):
                src_str += f"""std::vector<{type_cpp_array}> _{arg_low}Signed;
                _{arg_low}Signed.assign(_{int_extension}{arg_low}.begin(), _{int_extension}{arg_low}.end());
                {type_java_array}* {arg_low}Data = static_cast<{type_java_array}*>(_{arg_low}Signed.data());
                """
            elif(array.type.name == "String"):
                src_str += f"""jsize {arg_low}Length = static_cast<jsize>(_{arg_low}.size());
                jstring {arg_low}Str = {env}->NewStringUTF("");
                jclass {arg_low}StrClazz = {env}->GetObjectClass({arg_low}Str);
                jobjectArray {arg_low} = {env}->NewObjectArray({arg_low}Length, {arg_low}StrClazz, nullptr);
                for(int s = 0; s < {arg_low}Length; s++){{
                    {arg_low}Str = {env}->NewStringUTF(_{arg_low}[s].c_str());
                    {env}->SetObjectArrayElement({arg_low}, s, {arg_low}Str);
                }}
                {env}->DeleteLocalRef({arg_low}Str);
                """
            else:
                src_str += short_to_int
                src_str += f"""{type_java_array}* {arg_low}Data = static_cast<{type_java_array}*>(_{int_extension}{arg_low}.data());
                """
            if(array.type.name != "String"):
                src_str += f"""jsize {arg_low}Length = static_cast<jsize>(_{arg_low}.size());
        \t\t{type_java_array}Array {arg_low} = {env}->New{type_array}Array({arg_low}Length);
        \t\t{env}->Set{type_array}ArrayRegion({arg_low}, 0, {arg_low}Length, {arg_low}Data);
                """
        ## Struct
        elif(type_checked == 4 or type_checked == 7):
            defined = out_arg.type.reference.namespace.name
            struct_name =  out_arg.type.reference.name
            src_str_temp = struct_fields_sub_gen(out_arg,interface,package_name,java_class,"")
            ### adding tabs for indentation
            lines = src_str_temp.split('\n')
            lines_tab = ['\t' + line for line in lines]
            lines_result = '\n'.join(lines_tab)
            src_str += lines_result
            ###
            src_str += f"""
            \tjobject {arg_low} = {env}->NewObject({defined}{struct_name}Clazz, {defined}{struct_name}Constructor"""
        #for field in interface.structs[attr_type].fields.values():
            for field in out_arg.type.reference.fields.values():
                src_str += ", {}{}".format(arg_low, capitalize_first_letter(field.name))
            src_str += f""");
                """
        ## Enumeration
        elif(type_checked == 8):
            reference_cap = capitalize_first_letter(out_arg.type.reference.namespace.name)
            reference_type = out_arg.type.reference.name
            src_str += f"""uint8_t _{arg_low}Int = static_cast<uint8_t>(_{arg_low});
        \t\tjbyte {arg_low} = static_cast<jbyte>(_{arg_low}Int);
                """
        ## Complex Array
        elif(type_checked == 9):
            src_str += complex_array(out_arg, interface, cpp_package, java_class, "", 4)
        elif(type_checked == 10):
            src_str += complex_array(out_arg, interface, cpp_package, java_class, "", 4, is_implicit=True)
        elif(type_checked == 11):
            src_str += generate_src_map(out_arg, package_name, interface, java_class, upper="", indentation=0, type=0)
        
# Until this part can be changed.

    # broadcast 5: Call Void Method, Detach Current Thread and Return
    src_str += f"""{env}->CallVoidMethod({interface_cap}Instance,{broadcast_cap}MID"""
    for out_arg in broadcast.out_args.values():
        src_str += ", {}".format(lower_first_letter(out_arg.name))
    src_str += ");"
    
    src_str += f"""
                jvm->DetachCurrentThread();
            }}
        );
    }}
    """
# unsub
    src_str += f"""
    JNIEXPORT void JNICALL\n\tJava_{java_package}{interface_cap}{interface_extension}_unsubBroadcast{broadcast_cap}(JNIEnv *env, jobject instance, jlong proxyptr, jint subscription){{
        {interface_cap}Client* _{interface_cap}Client = reinterpret_cast<{interface_cap}Client*>(proxyptr);
        _{interface_cap}Client->{interface_cap}Instance = {env}->NewGlobalRef(instance);
    \tint32_t _subscription = static_cast<int>(subscription);
    \t_{interface_cap}Client->myProxy->get{broadcast_cap}Event().unsubscribe(_subscription);
    }}\n"""

    src_str += """\n////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
////////////////////////////////////////////////////////////////////////////////////////////////////////////////////\n"""

    return src_str
        
######################################### JNI and STUB FROM NOW ON ##########################################
################################################ Attribute ##################################################
# casting for struct
def generate_jni_attribute_struct_cast(attribute, interface, upper="", isget=True, ismethod=False, iscomplex=False, depth=0):
    struct_cast = ""
    attribute_low = lower_first_letter(attribute.name)
    # attribute_cap = capitalize_first_letter(attribute.name)
    # type_service = convert_java_code_type(attribute.type.name)
    # type_checked = check_type_ver2(attribute, interface)
    if(upper != ""):
        if(ismethod is False):
            attribute_low = (upper + "." + attribute_low)
        else:
            attribute_low = (upper + "." + attribute.name)    
    else:
        if(ismethod is True):
            attribute_low = attribute.name

    if(iscomplex):
        attribute = attribute.type.reference

    if(isget):
        for_loop_depth = "m" * depth
        for field in attribute.type.reference.fields.values():
            field_name = field.name
            field_type = check_type_ver2(field, interface)
            if(field_type == 1 or field_type == 2):
                struct_cast += f"""
            {attribute_low}.{field_name} = _{attribute_low}.{field_name};"""
            elif(field_type == 3 or field_type == 5 or field_type == 6):
                type_data = ""
                if(field_type == 3 or field_type == 6):
                    type_data = ".data"
                struct_cast += f"""
            {attribute_low}.{field_name}{type_data} = _{attribute_low}.{field_name};"""
                ## String init, erase the if pharse above and activate it if needed
            #     if(field_type == 3 or field_type == 6):
            #         type_data = ".data"
            #         struct_cast += f"""{attribute_low}.{field_name} = new {field.type.reference.name}();
            # {attribute_low}.{field_name}.data = new {capitalize_first_letter(convert_java_code_type(field.type.reference.type.name))}[_{field_name}.length];"""
            #     elif(field_type == 5):
            #         struct_cast += f"""{attribute_low}.{field_name} = new {capitalize_first_letter(convert_java_code_type(field.type.type.name))}[_{field_name}.length];"""
            #     struct_cast += f"""
            # {attribute_low}.{field_name}{type_data} = _{field_name};
            # """
            
            elif(field_type == 4 or field_type == 7):
                #for field2 in field.type.reference.fields.values():
                struct_cast += f"""
            {attribute_low}.{field_name} = new {field.type.reference.namespace.name}.{field.type.reference.name}();"""
                struct_cast += generate_jni_attribute_struct_cast(field, interface, attribute_low,True)
            elif(field_type == 8):
                struct_cast += f"""
            {attribute_low}.{field_name} = _{attribute_low}.{field_name};"""
            elif(field_type == 9):
                struct_cast += f"""
            {attribute_low}.{field_name} = new {field.type.reference.name}();
            {attribute_low}.{field_name}.data = new {field.type.reference.type.name}[_{attribute_low}.{field_name}.length];"""
                struct_cast_temp = generate_stub_attribute_struct_cast(field, interface, upper=attribute_low, isget=True, ismethod= False, iscomplex= True, depth = depth+1)
                struct_cast_temp = struct_cast_temp.replace(f"_{attribute_low}.{field_name}.", f"_{attribute_low}.{field_name}[j{for_loop_depth}].")
                struct_cast_temp = struct_cast_temp.replace(f"{attribute_low}.{field_name}.", f"{attribute_low}.{field_name}.data[j{for_loop_depth}].")
                struct_cast_temp_lines = struct_cast_temp.split('\n')
                struct_cast_temp_lines = ['\t' + line for line in struct_cast_temp_lines]
                struct_cast_temp = '\n'.join(struct_cast_temp_lines)
                struct_cast += f"""
            for(int j{for_loop_depth} = 0; j{for_loop_depth} < {attribute_low}.{field_name}.data.length; j{for_loop_depth}++){{{struct_cast_temp}
            }}"""
            elif(field_type == 10):
                struct_cast += f"""
            {attribute_low}.{field_name} = new {field.type.type.name}[_{attribute_low}.{field_name}.length];"""
                struct_cast_temp = generate_stub_attribute_struct_cast(field, interface, upper=attribute_low, isget=True, ismethod= False, iscomplex= True, isimplicit=True, depth = depth+1)
                struct_cast_temp = struct_cast_temp.replace(f"_{attribute_low}.{field_name}.", f"_{attribute_low}.{field_name}[j{for_loop_depth}].")
                struct_cast_temp = struct_cast_temp.replace(f"{attribute_low}.{field_name}.", f"{attribute_low}.{field_name}[j{for_loop_depth}].")
                struct_cast_temp_lines = struct_cast_temp.split('\n')
                struct_cast_temp_lines = ['\t' + line for line in struct_cast_temp_lines]
                struct_cast_temp = '\n'.join(struct_cast_temp_lines)
                struct_cast += f"""
            for(int j{for_loop_depth} = 0; j{for_loop_depth} < {attribute_low}.{field_name}.length; j{for_loop_depth}++){{{struct_cast_temp}
            }}"""
    else:
        for_loop_depth = "n" * depth 
        for field in attribute.type.reference.fields.values():
            field_name = field.name
            field_type = check_type_ver2(field, interface)
            if(field_type == 1 or field_type == 2):
                struct_cast += f"""
            _{attribute_low}.{field_name} = {attribute_low}.{field_name};"""
            elif(field_type == 3 or field_type == 5 or field_type == 6):
                type_data = ""
                if(field_type == 3 or field_type == 6):
                    type_data = ".data"
                struct_cast += f"""
            _{attribute_low}.{field_name} = {attribute_low}.{field_name}{type_data};"""
                ## String init, erase the if pharse above and activate it if needed
            #     if(field_type == 3 or field_type == 6):
            #         type_data = ".data"
            #         struct_cast += f"""{attribute_low}.{field_name} = new {field.type.reference.name}();
            # {attribute_low}.{field_name}.data = new {capitalize_first_letter(convert_java_code_type(field.type.reference.type.name))}[_{field_name}.length];"""
            #     elif(field_type == 5):
            #         struct_cast += f"""{attribute_low}.{field_name} = new {capitalize_first_letter(convert_java_code_type(field.type.type.name))}[_{field_name}.length];"""
            #     struct_cast += f"""
            # {attribute_low}.{field_name}{type_data} = _{field_name};
            # """
            elif(field_type == 4 or field_type == 7):
                #for field2 in field.type.reference.fields.values():
                struct_cast += f"""
            _{attribute_low}.{field_name} = new {field.type.reference.namespace.name}JNI.{field.type.reference.name}();"""
                struct_cast += generate_jni_attribute_struct_cast(field, interface, attribute_low,False)
            elif(field_type == 8):
                struct_cast += f"""
            _{attribute_low}.{field_name} = {attribute_low}.{field_name};"""
            elif(field_type == 9):
                struct_cast += f"""
            _{attribute_low}.{field_name} = new {field.type.reference.type.reference.namespace.name}JNI.{field.type.reference.type.name}[{attribute_low}.{field_name}.data.length];"""
                struct_cast_temp = generate_stub_attribute_struct_cast(field, interface, upper=attribute_low, isget=False, ismethod= False, iscomplex= True, depth = depth+1)
                struct_cast_temp = struct_cast_temp.replace(f"_{attribute_low}.{field_name}.", f"_{attribute_low}.{field_name}[k{for_loop_depth}].")
                struct_cast_temp = struct_cast_temp.replace(f"{attribute_low}.{field_name}.", f"{attribute_low}.{field_name}.data[k{for_loop_depth}].")
                struct_cast_temp_lines = struct_cast_temp.split('\n')
                struct_cast_temp_lines = ['\t' + line for line in struct_cast_temp_lines]
                struct_cast_temp = '\n'.join(struct_cast_temp_lines)
                struct_cast += f"""
            for(int k{for_loop_depth} = 0; k{for_loop_depth} < {attribute_low}.{field_name}.data.length; k{for_loop_depth}++){{{struct_cast_temp}
            }}"""
            elif(field_type == 10):
                struct_cast += f"""
            _{attribute_low}.{field_name} = new {field.type.type.reference.namespace.name}JNI.{field.type.type.name}[{attribute_low}.{field_name}.length];"""
                struct_cast_temp = generate_stub_attribute_struct_cast(field, interface, upper=attribute_low, isget=False, ismethod= False, iscomplex= True, isimplicit=True, depth = depth+1)
                struct_cast_temp = struct_cast_temp.replace(f"_{attribute_low}.{field_name}.", f"_{attribute_low}.{field_name}[k{for_loop_depth}].")
                struct_cast_temp = struct_cast_temp.replace(f"{attribute_low}.{field_name}.", f"{attribute_low}.{field_name}[k{for_loop_depth}].")
                struct_cast_temp_lines = struct_cast_temp.split('\n')
                struct_cast_temp_lines = ['\t' + line for line in struct_cast_temp_lines]
                struct_cast_temp = '\n'.join(struct_cast_temp_lines)
                struct_cast += f"""
            for(int k{for_loop_depth} = 0; k{for_loop_depth} < {attribute_low}.{field_name}.length; k{for_loop_depth}++){{{struct_cast_temp}
            }}"""
        
    return struct_cast

# AIDL 분리로 casting 새로 만듬. stub 코드용, upper == name extension
def generate_stub_attribute_struct_cast(attribute, interface, upper="", isget=True, ismethod=False, iscomplex = False, isimplicit = False, depth=0):
    struct_cast = ""
    attribute_low = lower_first_letter(attribute.name)

    if(upper != ""):
        if(ismethod is False):
            attribute_low = (upper + "." + attribute_low)
        else:
            attribute_low = (upper + "." + attribute.name)    
    else:
        if(ismethod is True):
            attribute_low = lower_first_letter(attribute.name)

    if(iscomplex and not isimplicit):
        attribute = attribute.type.reference
    elif(isimplicit):
        attribute = attribute.type

    if(isget):
        for_loop_depth = "j" * depth
        for field in attribute.type.reference.fields.values():
            field_name = field.name
            field_type = check_type_ver2(field, interface)
            if(field_type == 1 or field_type == 2):
                struct_cast += f"""
            {attribute_low}.{field_name} = _{attribute_low}.{field_name};"""
            elif(field_type == 3 or field_type == 5 or field_type == 6):
                type_data = ""
                if(field_type == 3 or field_type == 6):
                    type_data = ".data"
                if(iscomplex):
                    if(field_type == 3 or field_type == 6):
                        struct_cast += f"""
            {attribute_low}.{field_name} = new {field.type.name}();
            {attribute_low}.{field_name}.data = new {capitalize_first_letter(convert_java_code_type(field.type.name))}[_{attribute_low}.{field_name}.length];"""
                    elif(field_type == 5):
                        struct_cast += f"""
            {attribute_low}.{field_name} = new {capitalize_first_letter(convert_java_code_type(field.type.type.name))}[_{attribute_low}.{field_name}.length];"""
                struct_cast += f"""
            {attribute_low}.{field_name}{type_data} = _{attribute_low}.{field_name};"""
            elif(field_type == 4 or field_type == 7):
                #for field2 in field.type.reference.fields.values():
                struct_cast += f"""
            {attribute_low}.{field_name} = new /*{field.type.reference.namespace.name}.*/{field.type.reference.name}();"""
                struct_cast += generate_stub_attribute_struct_cast(field, interface, attribute_low,True)
            elif(field_type == 8):
                struct_cast += f"""
            {attribute_low}.{field_name} = _{attribute_low}.{field_name};"""
            elif(field_type == 9):
                struct_cast += f"""
            {attribute_low}.{field_name} = new {field.type.reference.name}();
            {attribute_low}.{field_name}.data = new {field.type.reference.type.name}[_{attribute_low}.{field_name}.length];"""
                struct_cast_temp = generate_stub_attribute_struct_cast(field, interface, upper=attribute_low, isget=True, ismethod= False, iscomplex= True, depth = depth+1)
                struct_cast_temp = struct_cast_temp.replace(f"_{attribute_low}.{field_name}.", f"_{attribute_low}.{field_name}[j{for_loop_depth}].")
                struct_cast_temp = struct_cast_temp.replace(f"{attribute_low}.{field_name}.", f"{attribute_low}.{field_name}.data[j{for_loop_depth}].")
                struct_cast_temp_lines = struct_cast_temp.split('\n')
                struct_cast_temp_lines = ['\t' + line for line in struct_cast_temp_lines]
                struct_cast_temp = '\n'.join(struct_cast_temp_lines)
                struct_cast += f"""
            for(int j{for_loop_depth} = 0; j{for_loop_depth} < _{attribute_low}.{field_name}.length; j{for_loop_depth}++){{
                {attribute_low}.{field_name}.data[j{for_loop_depth}] = new {field.type.reference.type.reference.name}();{struct_cast_temp}
            }}"""
            elif(field_type == 10):
                struct_cast += f"""
            {attribute_low}.{field_name} = new {field.type.type.name}[_{attribute_low}.{field_name}.length];"""
                struct_cast_temp = generate_stub_attribute_struct_cast(field, interface, upper=attribute_low, isget=True, ismethod= False, iscomplex= True, isimplicit=True, depth = depth+1)
                struct_cast_temp = struct_cast_temp.replace(f"_{attribute_low}.{field_name}.", f"_{attribute_low}.{field_name}[j{for_loop_depth}].")
                struct_cast_temp = struct_cast_temp.replace(f"{attribute_low}.{field_name}.", f"{attribute_low}.{field_name}[j{for_loop_depth}].")
                struct_cast_temp_lines = struct_cast_temp.split('\n')
                struct_cast_temp_lines = ['\t' + line for line in struct_cast_temp_lines]
                struct_cast_temp = '\n'.join(struct_cast_temp_lines)
                struct_cast += f"""
            for(int j{for_loop_depth} = 0; j{for_loop_depth} < _{attribute_low}.{field_name}.length; j{for_loop_depth}++){{
                {attribute_low}.{field_name}[j{for_loop_depth}] = new {field.type.type.reference.name}();{struct_cast_temp}
            }}"""
            elif(field_type == 11):
                struct_cast += generate_jni_map_cast(field, attribute_low, interface, indentation=depth+1, type=1)
    else:
        for_loop_depth = "k" * depth
        for field in attribute.type.reference.fields.values():
            field_name = field.name
            field_type = check_type_ver2(field, interface)
            if(field_type == 1 or field_type == 2):
                struct_cast += f"""
            _{attribute_low}.{field_name} = {attribute_low}.{field_name};"""
            elif(field_type == 3 or field_type == 5 or field_type == 6):
                type_data = ""
                if(field_type == 3 or field_type == 6):
                    type_data = ".data"
                struct_cast += f"""
            _{attribute_low}.{field_name} = {attribute_low}.{field_name}{type_data};"""
            elif(field_type == 4 or field_type == 7):
                #for field2 in field.type.reference.fields.values():
                struct_cast += f"""
            _{attribute_low}.{field_name} = new {field.type.reference.namespace.name}JNI.{field.type.reference.name}();"""
                struct_cast += generate_stub_attribute_struct_cast(field, interface, attribute_low,False)
            elif(field_type == 8):
                struct_cast += f"""
            _{attribute_low}.{field_name} = {attribute_low}.{field_name};"""
            elif(field_type == 9):
                struct_cast += f"""
            _{attribute_low}.{field_name} = new {field.type.reference.type.reference.namespace.name}JNI.{field.type.reference.type.name}[{attribute_low}.{field_name}.data.length];"""
                struct_cast_temp = generate_stub_attribute_struct_cast(field, interface, upper=attribute_low, isget=False, ismethod= False, iscomplex= True, depth = depth+1)
                struct_cast_temp = struct_cast_temp.replace(f"_{attribute_low}.{field_name}.", f"_{attribute_low}.{field_name}[k{for_loop_depth}].")
                struct_cast_temp = struct_cast_temp.replace(f"{attribute_low}.{field_name}.", f"{attribute_low}.{field_name}.data[k{for_loop_depth}].")
                struct_cast_temp_lines = struct_cast_temp.split('\n')
                struct_cast_temp_lines = ['\t' + line for line in struct_cast_temp_lines]
                struct_cast_temp = '\n'.join(struct_cast_temp_lines)
                struct_cast += f"""
            for(int k{for_loop_depth} = 0; k{for_loop_depth} < {attribute_low}.{field_name}.data.length; k{for_loop_depth}++){{{struct_cast_temp}
            }}"""
            elif(field_type == 10):
                struct_cast += f"""
            _{attribute_low}.{field_name} = new {field.type.type.reference.namespace.name}JNI.{field.type.type.name}[{attribute_low}.{field_name}.length];"""
                struct_cast_temp = generate_stub_attribute_struct_cast(field, interface, upper=attribute_low, isget=False, ismethod= False, iscomplex= True, isimplicit=True, depth = depth+1)
                struct_cast_temp = struct_cast_temp.replace(f"_{attribute_low}.{field_name}.", f"_{attribute_low}.{field_name}[k{for_loop_depth}].")
                struct_cast_temp = struct_cast_temp.replace(f"{attribute_low}.{field_name}.", f"{attribute_low}.{field_name}[k{for_loop_depth}].")
                struct_cast_temp_lines = struct_cast_temp.split('\n')
                struct_cast_temp_lines = ['\t' + line for line in struct_cast_temp_lines]
                struct_cast_temp = '\n'.join(struct_cast_temp_lines)
                struct_cast += f"""
            for(int k{for_loop_depth} = 0; k{for_loop_depth} < {attribute_low}.{field_name}.length; k{for_loop_depth}++){{{struct_cast_temp}
            }}"""
            elif(field_type == 11):
                struct_cast += generate_jni_map_cast(field, upper=attribute_low, interface=interface, indentation=depth+1, type=2)
        
    return struct_cast
    
# casting str gen functions
def generate_jni_attribute_get_cast(attribute, interface):
    get_cast = ""
    attribute_low = lower_first_letter(attribute.name)
    attribute_cap = capitalize_first_letter(attribute.name)
    type_service = convert_java_code_type(attribute.type.name)
    type_checked = check_type_ver2(attribute, interface)
    
    # implicit array 
    if(type_checked != 5 and type_checked != 10 and type_checked != 12 and type_checked != 14):
        type_service = convert_java_code_type(attribute.type.name).split('.')[-1]
    
    # null error avoidance
    is_get_null = ""
    if(type_checked == 9 or type_checked == 10 or type_checked == 11):
        is_get_null = f"""if(_{attribute_low} == null){{
                return null;
            }}
            """
    
    
    if(type_checked == 1 or type_checked == 2):
        get_cast = f"""return myProxy.getAttribute{attribute_cap}Value();""" # no need to cast
    elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
        type_java = ""
        type_data = ""
        if(type_checked == 5):
            type_java = convert_java_code_type(attribute.type.type.name) + "[]"
            type_service = convert_java_code_type(attribute.type.type.name) + "[]"
            get_cast = f"""{type_java} _{attribute_low} = myProxy.getAttribute{attribute_cap}Value();
            {type_service} {attribute_low};
            {attribute_low}{type_data} = _{attribute_low};
            return {attribute_low};"""
        elif(type_checked == 3):
            type_java = convert_java_code_type(interface.arrays[attribute.type.name].type.name) + "[]"
            type_data = ".data"
            get_cast = f"""{type_java} _{attribute_low} = myProxy.getAttribute{attribute_cap}Value();
            {type_service} {attribute_low} = new {type_service}();
            {attribute_low}{type_data} = _{attribute_low};
            return {attribute_low};"""
        elif(type_checked == 6):
            type_java = convert_java_code_type(attribute.type.reference.type.name) + "[]"
            type_data = ".data"
            get_cast = f"""{type_java} _{attribute_low} = myProxy.getAttribute{attribute_cap}Value();
            {type_service} {attribute_low} = new {type_service}();
            {attribute_low}{type_data} = _{attribute_low};
            return {attribute_low};"""
    elif(type_checked == 4 or type_checked == 7):
        type_java = convert_java_code_type(attribute.type.name)
        get_cast = f"""{attribute.type.reference.namespace.name+"JNI."}{type_java.split('.')[-1]} _{attribute_low} = myProxy.getAttribute{attribute_cap}Value();
            {type_service} {attribute_low} = new {type_service}();"""
        get_cast += generate_stub_attribute_struct_cast(attribute, interface, upper="", isget=True)
        get_cast += f"""
            return {attribute_low};"""
    elif(type_checked == 8): #enumeration is treated as byte, there is a need to change the C++ code
        get_cast = f"""return myProxy.getAttribute{attribute_cap}Value();""" # no need to cast
    elif(type_checked == 9):
        get_cast_temp = generate_stub_attribute_struct_cast(attribute, interface, upper="", isget=True, ismethod= False, iscomplex= True)
        get_cast_temp = get_cast_temp.replace(f"_{attribute_low}.", f"_{attribute_low}[i].")
        get_cast_temp = get_cast_temp.replace(f"{attribute_low}.", f"{attribute_low}.data[i].")
        get_cast_temp_lines = get_cast_temp.split('\n')
        get_cast_temp_lines = ['\t' + line for line in get_cast_temp_lines]
        get_cast_temp = '\n'.join(get_cast_temp_lines)
        
        get_cast = f"""{attribute.type.reference.namespace.name}JNI.{attribute.type.reference.type.name}[] _{attribute_low} = myProxy.getAttribute{attribute_cap}Value();
            {is_get_null}{attribute.type.name} {attribute_low} = new {attribute.type.name}();
            {attribute_low}.data = new {attribute.type.reference.type.name}[_{attribute_low}.length];
            for(int i = 0; i < _{attribute_low}.length; i++){{
                {attribute_low}.data[i] = new {attribute.type.reference.type.name}();{get_cast_temp}
            }}
            return {attribute_low};"""
    elif(type_checked == 10):
        get_cast_temp = generate_stub_attribute_struct_cast(attribute, interface, upper="", isget=True, ismethod= False, iscomplex= True, isimplicit=True)
        get_cast_temp = get_cast_temp.replace(f"_{attribute_low}.", f"_{attribute_low}[i].")
        get_cast_temp = get_cast_temp.replace(f"{attribute_low}.", f"{attribute_low}[i].")
        get_cast_temp_lines = get_cast_temp.split('\n')
        get_cast_temp_lines = ['\t' + line for line in get_cast_temp_lines]
        get_cast_temp = '\n'.join(get_cast_temp_lines)
        
        get_cast = f"""{attribute.type.type.reference.namespace.name}JNI.{attribute.type.type.reference.name}[] _{attribute_low} = myProxy.getAttribute{attribute_cap}Value();
            {is_get_null}{attribute.type.type.reference.name}[] {attribute_low} = new {attribute.type.type.reference.name}[_{attribute_low}.length];
            for(int i = 0; i < _{attribute_low}.length; i++){{
                {attribute_low}[i] = new {attribute.type.type.reference.name}();{get_cast_temp}
            }}
            return {attribute_low};"""
    elif(type_checked == 11):
        get_cast_temp = generate_jni_map_cast(attribute, upper="", interface=interface, indentation=0, type=0)
        get_cast = f"""{attribute.type.reference.namespace.name}JNI.{attribute.type.reference.name}[] _{attribute_low} = myProxy.getAttribute{attribute_cap}Value();
            {is_get_null}{attribute.type.reference.name}[] {attribute_low} = new {attribute.type.reference.name}[_{attribute_low}.length];
            {get_cast_temp}
            
            return {attribute_low};"""
        
    return get_cast

def generate_jni_attribute_set_cast(attribute, interface):
    set_cast = ""
    attribute_low = lower_first_letter(attribute.name)
    attribute_cap = capitalize_first_letter(attribute.name)
    type_service = convert_java_code_type(attribute.type.name)
    type_checked = check_type_ver2(attribute, interface)
    if(type_checked == 1 or type_checked == 2):
        set_cast = f"""myProxy.setAttribute{attribute_cap}Value({attribute_low});"""    
    elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
        type_java = ""
        if(type_checked == 5):
            type_java = convert_java_code_type(attribute.type.type.name) + "[]"
            set_cast = f"""myProxy.setAttribute{attribute_cap}Value({attribute_low});"""
        elif(type_checked == 3):
            type_java = convert_java_code_type(interface.arrays[attribute.type.name].type.name) + "[]"
            set_cast = f"""{type_java} _{attribute_low} = {attribute_low}.data;
            myProxy.setAttribute{attribute_cap}Value(_{attribute_low});"""
        elif(type_checked == 6):
            type_java = convert_java_code_type(attribute.type.reference.type.name) + "[]"
            set_cast = f"""{type_java} _{attribute_low} = {attribute_low}.data;
            myProxy.setAttribute{attribute_cap}Value(_{attribute_low});"""
    elif(type_checked == 4 or type_checked == 7):
        type_java = convert_java_code_type(attribute.type.name)
        set_cast = f"""{attribute.type.reference.namespace.name+"JNI."}{type_java.split('.')[-1]} _{attribute_low} = new {attribute.type.reference.namespace.name+"JNI."}{type_java.split('.')[-1]}();"""
        #### for declaration for struct in struct is needed
        set_cast += generate_stub_attribute_struct_cast(attribute, interface, upper="", isget=False)
        set_cast += f"""
            myProxy.setAttribute{attribute_cap}Value(_{attribute_low});"""
    elif(type_checked == 8):
        set_cast = f"""myProxy.setAttribute{attribute_cap}Value({attribute_low});"""
    elif(type_checked == 9):
        set_cast_temp = generate_stub_attribute_struct_cast(attribute, interface, upper="", isget=False, ismethod= False, iscomplex = True)
        set_cast_temp = set_cast_temp.replace(f"_{attribute_low}.", f"_{attribute_low}[i].")
        set_cast_temp = set_cast_temp.replace(f"{attribute_low}.", f"{attribute_low}.data[i].")
        set_cast_temp_lines = set_cast_temp.split('\n')
        set_cast_temp_lines = ['\t' + line for line in set_cast_temp_lines]
        set_cast_temp = '\n'.join(set_cast_temp_lines)
        
        set_cast = f"""{attribute.type.reference.namespace.name}JNI.{attribute.type.reference.type.name}[] _{attribute_low} = new {attribute.type.reference.namespace.name}JNI.{attribute.type.reference.type.name}[{attribute_low}.data.length];
            for(int i = 0; i < {attribute_low}.data.length; i++){{
                _{attribute_low}[i] = new {attribute.type.reference.namespace.name}JNI.{attribute.type.reference.type.name}();{set_cast_temp}
            }}
            myProxy.setAttribute{attribute_cap}Value(_{attribute_low});"""
    elif(type_checked == 10):
        set_cast_temp = generate_stub_attribute_struct_cast(attribute, interface, upper="", isget=False, ismethod= False, iscomplex = True, isimplicit=True)
        set_cast_temp = set_cast_temp.replace(f"_{attribute_low}.", f"_{attribute_low}[i].")
        set_cast_temp = set_cast_temp.replace(f"{attribute_low}.", f"{attribute_low}[i].")
        set_cast_temp_lines = set_cast_temp.split('\n')
        set_cast_temp_lines = ['\t' + line for line in set_cast_temp_lines]
        set_cast_temp = '\n'.join(set_cast_temp_lines)
        
        set_cast = f"""{attribute.type.type.reference.namespace.name}JNI.{attribute.type.type.reference.name}[] _{attribute_low} = new {attribute.type.type.reference.namespace.name}JNI.{attribute.type.type.reference.name}[{attribute_low}.length];
            for(int i = 0; i < {attribute_low}.length; i++){{
                _{attribute_low}[i] = new {attribute.type.type.reference.namespace.name}JNI.{attribute.type.type.reference.name}();{set_cast_temp}
            }}
            myProxy.setAttribute{attribute_cap}Value(_{attribute_low});"""
    elif(type_checked == 11):
        set_cast_temp = generate_jni_map_cast(attribute, upper="", interface=interface, indentation=0,type=2)
        set_cast = f"""{attribute.type.reference.namespace.name}JNI.{attribute.type.reference.name}[] _{attribute_low} = new {attribute.type.reference.namespace.name}JNI.{attribute.type.reference.name}[{attribute_low}.length];
            {set_cast_temp}
            myProxy.setAttribute{attribute_cap}Value(_{attribute_low});"""

    return set_cast
    
def generate_jni_map_struct_cast(value, map_low, interface, upper="", indentation=0, type=0):
    cast_str = ""
    
    k_or_v = ".value"
    if(upper != ""):
        upper = "." + upper
        
    if(type == 0 or type == 1):
        indent = "m"*indentation
        for field in value.reference.fields.values():
            type_checked = check_type_ver2(field, interface)
            if(type_checked == 1 or type_checked == 2):
                cast_str += f"""{map_low}[m{indent}]{k_or_v}{upper}.{field.name} = _{map_low}[m{indent}]{k_or_v}{upper}.{field.name};
                """
            elif(type_checked == 4):
                cast_str += f"""{map_low}[m{indent}]{k_or_v}{upper}.{field.name} = new {field.type.reference.name}();
                """
                cast_str += generate_jni_map_struct_cast(field, map_low, field.name, indentation, type)
    elif(type == 2):
        indent = "m"*indentation
        for field in value.reference.fields.values():
            type_checked = check_type_ver2(field, interface)
            if(type_checked == 1 or type_checked == 2):
                cast_str += f"""_{map_low}[m{indent}]{k_or_v}{upper}.{field.name} = {map_low}[m{indent}]{k_or_v}{upper}.{field.name};
                """
            elif(type_checked == 4):
                cast_str += f"""_{map_low}[m{indent}]{k_or_v}{upper}.{field.name} = new {field.type.reference.namespace.name}JNI.{field.type.reference.name}();
                """
                cast_str += generate_jni_map_struct_cast(field, map_low, field.name, indentation, type)
    
    return cast_str
    
def generate_jni_map_cast(map, upper="", interface=None, indentation=0, type=0):
    # type 0: attribute handler or bcast callback / 1: get / 2: set / 3: method in / 4: method out
    map_str = ""
    map_low = lower_first_letter(map.name)
    if(upper != ""):
        upper = upper + "."
    
    if(type == 0 or type == 1):
        indent = "m"*indentation
        if(not isinstance(map.type.reference.value_type, ast.Reference)):
            map_str += f"""for(int m{indent} = 0; m{indent} < _{map_low}.length; m{indent}++){{
                {upper}{map_low}[m{indent}] = new {map.type.reference.name}();
                {upper}{map_low}[m{indent}].key = _{upper}{map_low}[m{indent}].key;
                {upper}{map_low}[m{indent}].value = _{upper}{map_low}[m{indent}].value;
            }}
            """ 
        else:
            if(isinstance(map.type.reference.value_type.reference, ast.Struct)):
                cast_str = generate_jni_map_struct_cast(map.type.reference.value_type, map_low, interface, "", indentation, 0)
                map_str += f"""for(int m{indent} = 0; m{indent} < _{map_low}.length; m{indent}++){{
                {upper}{map_low}[m{indent}] = new {map.type.reference.name}();
                {upper}{map_low}[m{indent}].key = _{upper}{map_low}[m{indent}].key;
                {upper}{map_low}[m{indent}].value = new {map.type.reference.value_type.reference.name}();
                {cast_str}
            }}
            """ 
            elif(isinstance(map.type.reference.value_type.reference, ast.Array)):
                map_str += f"""for(int m{indent} = 0; m{indent} < _{map_low}.length; m{indent}++){{
                {upper}{map_low}[m{indent}] = new {map.type.reference.name}();
                {upper}{map_low}[m{indent}].key = _{upper}{map_low}[m{indent}].key;
                {upper}{map_low}[m{indent}].value = new {map.type.reference.value_type.reference.name}();
                {upper}{map_low}[m{indent}].value.data = _{upper}{map_low}[m{indent}].value;
            }}
            """ 
    
    elif(type == 2):
        indent = "m"*indentation
        if(not isinstance(map.type.reference.value_type, ast.Reference)):
            map_str += f"""for(int m{indent} = 0; m{indent} < {map_low}.length; m{indent}++){{
                _{upper}{map_low}[m{indent}] = new {map.type.reference.namespace.name}JNI.{map.type.reference.name}();
                _{upper}{map_low}[m{indent}].key = {upper}{map_low}[m{indent}].key;
                _{upper}{map_low}[m{indent}].value = {upper}{map_low}[m{indent}].value;
            }}
            """
        else:
            if(isinstance(map.type.reference.value_type.reference, ast.Struct)):
                cast_str = generate_jni_map_struct_cast(map.type.reference.value_type, map_low, interface, "", indentation, 2)
                map_str += f"""for(int m{indent} = 0; m{indent} < {map_low}.length; m{indent}++){{
                _{upper}{map_low}[m{indent}] = new {map.type.reference.namespace.name}JNI.{map.type.reference.name}();
                _{upper}{map_low}[m{indent}].key = {upper}{map_low}[m{indent}].key;
                _{upper}{map_low}[m{indent}].value = new {map.type.reference.value_type.reference.namespace.name}JNI.{map.type.reference.value_type.reference.name}();
                {cast_str}
            }}
            """ 
            elif(isinstance(map.type.reference.value_type.reference, ast.Array)):
                map_str += f"""for(int m{indent} = 0; m{indent} < _{map_low}.length; m{indent}++){{
                _{upper}{map_low}[m{indent}] = new {map.type.reference.namespace.name}JNI.{map.type.reference.name}();
                _{upper}{map_low}[m{indent}].key = {upper}{map_low}[m{indent}].key;
                _{upper}{map_low}[m{indent}].value = {upper}{map_low}[m{indent}].value.data;
            }}
            """ 
            
    
    return map_str


# stub code에서 사용할 handler, sub, get, set, unsub 필요함. 그리고 반환하는 것까지
def generate_jni_attribute(attribute, interface, jni_attribute_cnt):
    attr_type = attribute.type.name
    attribute_cap = capitalize_first_letter(attribute.name)
    attribute_low = lower_first_letter(attribute.name)
    type_java = convert_java_code_type(attribute.type.name)
    type_service = convert_java_code_type(attribute.type.name)
    type_checked = check_type_ver2(attribute, interface)
    get_cast_str = generate_jni_attribute_get_cast(attribute, interface)
    set_cast_str = generate_jni_attribute_set_cast(attribute, interface)
    if(type_checked == 5 or type_checked == 10):
        type_java = convert_java_code_type(attribute.type.type.name) + "[]"
        type_service = convert_java_code_type(attribute.type.type.name) + "[]"
    elif(type_checked == 3):
        type_java = convert_java_code_type(interface.arrays[attribute.type.name].type.name) + "[]"
    elif(type_checked == 6):
        type_java = convert_java_code_type(attribute.type.reference.type.name) + "[]"
    elif(type_checked == 8):
        type_java = "byte"
        type_service = "byte"
        attr_type = "byte"
    elif(type_checked == 9):
        type_java = attribute.type.reference.type.name + "[]"
        type_service = attribute.type.name
        attr_type = attribute.type.reference.type.name + "[]"
    elif(type_checked == 10):
        type_java = attribute.type.type.reference.name + "[]"
        type_service = attribute.type.type.reference.name
        attr_type = attribute.type.type.reference.name + "[]"
    elif(type_checked == 11):
        type_java = attribute.type.reference.name + "[]"
        type_service = attribute.type.reference.name + "[]"
        attr_type = attribute.type.reference.name + "[]"
        

    # attr_type change for typecollection struct and enum
    if(type_checked == 7):
        if(attribute.type.reference.namespace.name != interface.name):
            attr_temp1 = attr_type.split('.')[0] + "JNI"
            attr_temp2 = attr_type.split('.')[-1]
            attr_type = attr_temp1 + "." + attr_temp2
            java_temp1 = type_java.split('.')[0] + "JNI"
            java_temp2 = type_java.split('.')[-1]
            type_java = java_temp1 + "." + java_temp2
        
    set_flag = 0
    if('readonly' not in attribute.flags):
        set_flag = 1
    else:
        set_flag = 0
    
    java_interface = ""
    if(isinstance(attribute.type, ast.Reference)):
        if(isinstance(attribute.type.reference, ast.Struct)):# or isinstance(attribute.type.reference, ast.Enumeration)):
            java_interface = attribute.type.reference.namespace.name+"JNI."
        if(type_checked == 9):
            java_interface = attribute.type.reference.namespace.name+"JNI."
    if(type_checked == 10):
        java_interface = attribute.type.type.reference.namespace.name+"JNI."
    if(type_checked == 11):
        java_interface = attribute.type.reference.namespace.name + "JNI."
        
    attribute_cast = ""
    jni_str = ""
    stub_handler = ""
    stub_main = ""
    
    ## attribute cast
    if(type_checked == 3 or type_checked == 6):
        attribute_cast = f"""/*{attribute.type.reference.namespace.name}.*/{type_service.split('.')[-1]} {attribute_low} = new /*{attribute.type.reference.namespace.name}.*/{type_service.split('.')[-1]}();
            {attribute_low}.data = _{attribute_low};"""
    elif(type_checked == 4 or type_checked == 7):
        attribute_cast = f"""/*{attribute.type.reference.namespace.name}.*/{type_service.split('.')[-1]} {attribute_low} = new /*{attribute.type.reference.namespace.name}.*/{type_service.split('.')[-1]}();"""
        attribute_cast += generate_stub_attribute_struct_cast(attribute,interface,upper="",isget=True,ismethod=False)
    elif(type_checked == 9):
        attribute_cast = f"""/*{attribute.type.reference.namespace.name}.*/{type_service.split('.')[-1]} {attribute_low} = new /*{attribute.type.reference.namespace.name}.*/{type_service.split('.')[-1]}();
            {attribute_low}.data = new {attribute.type.reference.type.name}[_{attribute_low}.length];"""
        attribute_cast_temp = generate_stub_attribute_struct_cast(attribute, interface, upper="", isget=True, ismethod= False, iscomplex= True)
        attribute_cast_temp = attribute_cast_temp.replace(f"_{attribute_low}.", f"_{attribute_low}[i].")
        attribute_cast_temp = attribute_cast_temp.replace(f"{attribute_low}.", f"{attribute_low}.data[i].")
        attribute_cast_temp_lines = attribute_cast_temp.split('\n')
        attribute_cast_temp_lines = ['\t' + line for line in attribute_cast_temp_lines]
        attribute_cast_temp = '\n'.join(attribute_cast_temp_lines)
        for_loop_temp = f"""
            for(int i = 0; i < _{attribute_low}.length; i++){{
                //{attribute.type.reference.namespace.name}JNI.{attribute.type.reference.type.name} _{attribute_low}Element = _{attribute_low}[i];
                {attribute_low}.data[i] = new {attribute.type.reference.type.name}();
            {attribute_cast_temp}
            }}"""
        attribute_cast += for_loop_temp
    elif(type_checked == 10):
        attribute_cast = f"""{type_service.split('.')[-1]} {attribute_low} = new {attribute.type.type.reference.name}[_{attribute_low}.length];"""
        attribute_cast_temp = generate_stub_attribute_struct_cast(attribute, interface, upper="", isget=True, ismethod= False, iscomplex= True, isimplicit=True)
        attribute_cast_temp = attribute_cast_temp.replace(f"_{attribute_low}.", f"_{attribute_low}[i].")
        attribute_cast_temp = attribute_cast_temp.replace(f"{attribute_low}.", f"{attribute_low}[i].")
        attribute_cast_temp_lines = attribute_cast_temp.split('\n')
        attribute_cast_temp_lines = ['\t' + line for line in attribute_cast_temp_lines]
        attribute_cast_temp = '\n'.join(attribute_cast_temp_lines)
        for_loop_temp = f"""
            for(int i = 0; i < _{attribute_low}.length; i++){{
                {attribute_low}[i] = new {attribute.type.type.reference.name}();
            {attribute_cast_temp}
            }}"""
        attribute_cast += for_loop_temp
    elif(type_checked == 11):
        attribute_cast = f"""{type_service.split('.')[-1]} {attribute_low} = new {type_service.split('[]')[0]}[_{attribute_low}.length];
            """
        attribute_cast += generate_jni_map_cast(attribute, "", interface)
    # Not in use
    else:
        if(type_checked % 2 == 0):
            attribute_cast = f"""{type_java} {attribute_low} = _{attribute_low};"""
        else:
            attribute_cast = f"""{type_java.split('.')[-1]} {attribute_low} = _{attribute_low};"""
    
    
    
    if(type_checked >= 1 and type_checked <= 11):
        stub_handler += f"""
    private static ArrayList<{capitalize_first_letter(interface.name)}{attribute_cap}Handler> {attribute_cap}Handler = new ArrayList<>();
    void Attribute{attribute_cap}Handle({java_interface}{type_java.split('.')[-1]} _{attribute_low}){{
        if(this.{attribute_cap}Handler != null){{
            {attribute_cast}
            for({capitalize_first_letter(interface.name)}{attribute_cap}Handler handler : this.{attribute_cap}Handler){{
                try {{
                    handler.run{attribute_cap}Handler({attribute_low});
                }} catch (RemoteException e) {{
                    throw new RuntimeException(e);
                }}
            }}
        }}
    }}
    """
        stub_main += f"""
        @Override
        public void subscribeAttribute{attribute_cap}({capitalize_first_letter(interface.name)}{attribute_cap}Handler handler) throws RemoteException {{
            if(myProxy == null){{
                if(!proxyGeneration()){{
                    return;
                }}
            }}
            if(!{capitalize_first_letter(interface.name)}Service.{attribute_cap}Handler.contains(handler)){{
                {capitalize_first_letter(interface.name)}Service.{attribute_cap}Handler.add(handler);
                if({capitalize_first_letter(interface.name)}Service.{attribute_cap}Handler.size() == 1){{
                    myProxy.subscribeAttribute{attribute_cap}();    
                }}
            }}
        }}"""
        # set
        if(set_flag):
            stub_main += f"""
        @Override
        public void setAttribute{attribute_cap}Value({type_service.split('.')[-1]} {attribute_low}) throws RemoteException {{
            if(myProxy == null){{
                if(!proxyGeneration()){{
                    return;
                }}
            }}
            {set_cast_str}
        }}"""
        # get
        return_null = ""
        if(type_service.split('.')[-1] == "void"):
            return_null = ""
        elif(type_service.split('.')[-1] in ['Int8', 'UInt8', 'Int16', 'UInt16', 'Int32', 'UInt32', 'Int64', 'UInt64', 'Double', 'Float']):
            return_null = "0"
        elif(type_service.split('.')[-1] == 'boolean'):
            return_null = "false"
        else:
            return_null = " null"
        stub_main += f"""
        @Override
        public {type_service.split('.')[-1]} getAttribute{attribute_cap}Value() throws RemoteException {{
            if(myProxy == null){{
                if(!proxyGeneration()){{
                    return {return_null};
                }}
            }}
            {get_cast_str}
        }}"""
        # unsubscribe
        stub_main += f"""
        @Override
        public void unsubscribeAttribute{attribute_cap}({capitalize_first_letter(interface.name)}{attribute_cap}Handler handler) throws RemoteException {{
            if(myProxy == null){{
                if(!proxyGeneration()){{
                    return;
                }}
            }}
            if({capitalize_first_letter(interface.name)}Service.{attribute_cap}Handler.contains(handler)){{
                {capitalize_first_letter(interface.name)}Service.{attribute_cap}Handler.remove(handler);
                if({capitalize_first_letter(interface.name)}Service.{attribute_cap}Handler.size() == 0){{
                    myProxy.unsubscribeAttribute{attribute_cap}(); 
                }}
            }}
        }}
        """
        
    #subscribe wrapper
    if(type_checked >= 1 and type_checked <= 11):
        jni_str += f"""
    int Attribute{attribute_cap}Subscription = -1;
    public void subscribeAttribute{attribute_cap}(){{
        subAttribute{attribute_cap}(this.proxyptr);
        ++Attribute{attribute_cap}Subscription;
    }}
        """

    # Get Set Wrapper
    if(type_checked >= 1 and type_checked <= 11):
        jni_str += f"""
    public {type_java} getAttribute{attribute_cap}Value(){{
        return getAttribute{attribute_cap}Value(this.proxyptr, service.timeout, service.sender);   
    }}
        """
        if(set_flag):
            if(type_java == "short"):
                if_short = "(short)"
            else:
                if_short = ""
            if(type_checked == 1 or type_checked == 2):
                attr_type_set = type_java
            elif(type_checked == 3):
                attr_type_set = convert_java_code_type(interface.arrays[attribute.type.name].type.name)+"[]"
            elif(type_checked == 5):
                attr_type_set = convert_java_code_type(attribute.type.type.name)+"[]"
            elif(type_checked == 6):
                attr_type_set = convert_java_code_type(attribute.type.reference.type.name)+"[]"
            elif(type_checked == 8):
                attr_type_set = "byte"
            elif(type_checked == 9):
                attr_type_set = attr_type
            elif(type_checked == 10):
                attr_type_set = attribute.type.type.reference.name+"[]"
            elif(type_checked == 11):
                attr_type_set = attribute.type.reference.name+"[]"
            else:
                attr_type_set = attr_type
            jni_str += f"""
    public void setAttribute{attribute_cap}Value({attr_type_set} {attribute_low}){{
        setAttribute{attribute_cap}Value(this.proxyptr, service.timeout, service.sender,{if_short}{attribute_low});   
    }}
        """
    
    # JNI native functions
    if(type_checked == 1 or type_checked == 2 or type_checked == 9 or type_checked == 10 or type_checked == 11):
        jni_str += f"""
    public native void subAttribute{attribute_cap}(long proxyptr);
    public void subAttribute{attribute_cap}Handler({type_java} {attribute_low}){{
        service.Attribute{attribute_cap}Handle({attribute_low});
    }}"""
        if(set_flag):
            jni_str += f"""
    public native {type_java} getAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender);
    public native {type_java} setAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender, {type_java} {attribute_low});
    public native void unsubAttribute{attribute_cap}(long proxyptr, int subscription);\n\n"""
        else:
            jni_str += f"""
    public native {type_java} getAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender);
    public native void unsubAttribute{attribute_cap}(long proxyptr, int subscription);\n\n"""
    elif(type_checked == 3 or type_checked == 5 or type_checked == 6):
        if(type_checked == 3):
            array = interface.arrays[attribute.type.name]
        elif(type_checked == 5):
            array = attribute.type
        elif(type_checked == 6):
            array = attribute.type.reference
            
        type_java_array = convert_java_code_type(array.type.name)
        jni_str += f"""
    public native void subAttribute{attribute_cap}(long proxyptr);
    public void subAttribute{attribute_cap}Handler({type_java_array}[] {attribute_low}){{
        service.Attribute{attribute_cap}Handle({attribute_low});
    }}"""
        if(set_flag):
            jni_str += f"""
    public native {type_java_array}[] getAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender);
    public native {type_java_array}[] setAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender, {type_java_array}[] {attribute_low});
    public native void unsubAttribute{attribute_cap}(long proxyptr, int subscription);\n\n"""
        else:
            jni_str += f"""
    public native {type_java_array}[] getAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender);
    public native void unsubAttribute{attribute_cap}(long proxyptr, int subscription);\n\n"""
    elif(type_checked == 4 or type_checked == 7):
        if(type_checked == 4):
            struct = interface.structs[attr_type]
        
    #     ## {struct_name}ToCPP
        jni_str += f"""
    public native void subAttribute{attribute_cap}(long proxyptr);
    public void subAttribute{attribute_cap}Handler({attr_type} {attribute_low}){{
        service.Attribute{attribute_cap}Handle({attribute_low});
    }}"""
        
        
        ## sub, get, set, unsub if readonly no set
        if(set_flag):
            jni_str += f"""
    public native {attr_type} getAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender);
    public native {attr_type} setAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender, {attr_type} {attribute_low});
    public native void unsubAttribute{attribute_cap}(long proxyptr, int subscription);
    
    """
        else:
            jni_str += f"""
    public native {attr_type} getAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender);
    public native void unsubAttribute{attribute_cap}(long proxyptr, int subscription);
    
    """
    elif(type_checked == 8):
        jni_str += f"""
    public native void subAttribute{attribute_cap}(long proxyptr);
    public void subAttribute{attribute_cap}Handler({attr_type} {attribute_low}){{
        service.Attribute{attribute_cap}Handle({attribute_low});
    }}"""
    
        if(set_flag):
            jni_str += f"""
    public native {attr_type} getAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender);
    public native {attr_type} setAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender, {attr_type} {attribute_low});
    public native void unsubAttribute{attribute_cap}(long proxyptr, int subscription);
    
    """
        else:
            jni_str += f"""
    public native {attr_type} getAttribute{attribute_cap}Value(long proxyptr, int timeout, int sender);
    public native void unsubAttribute{attribute_cap}(long proxyptr, int subscription);
    
    """
    # Unsub Wrapper
    jni_str += f"""
    public void unsubscribeAttribute{attribute_cap}(){{
        if(this.Attribute{attribute_cap}Subscription >= 0){{
            unsubAttribute{attribute_cap}(this.proxyptr, this.Attribute{attribute_cap}Subscription--);
        }}
    }}
    ///////////////////////////////////////////////////////////////////////////////////////"""

    return jni_str, stub_main, stub_handler

########################################### Method ############################################
# out_cast
def generate_jni_method_out_cast(method, interface, upper=""):
    struct_cast = ""
    
    for field in method.out_args.values():
        field_name = lower_first_letter(field.name)
        if(upper != ""):
            field_name = upper + "." + field_name
        field_type = check_type_ver2(field, interface)
        if(field_type == 1 or field_type == 2):
            struct_cast += f"""
            {field_name} = _{field_name};"""
        elif(field_type == 3 or field_type == 5 or field_type == 6):
            type_data = ""
            ###### 06.04 String 일 때 초기화를 해줘야 하나? 구조체 내부에 있는거면 초기화 해줘야하는 듯
            if(field_type == 3 or field_type == 6):
                type_data = ".data"
                struct_cast += f"""{field_name} = new {field.type.reference.name}();
            {field_name}.data = new {capitalize_first_letter(convert_java_code_type(field.type.reference.type.name))}[_{field_name}.length];"""
            elif(field_type == 5):
                struct_cast += f"""{field_name} = new {capitalize_first_letter(convert_java_code_type(field.type.type.name))}[_{field_name}.length];"""
            struct_cast += f"""
            {field_name}{type_data} = _{field_name};
            """
        elif(field_type == 4 or field_type == 7):
            #for field2 in field.type.reference.fields.values():
            if(len(method.out_args.values()) > 1):
                struct_cast += f"""{field_name} = new {field.type.name}();"""
            struct_cast += generate_stub_attribute_struct_cast(field, interface, upper,isget=True,ismethod=True)
        elif(field_type == 8):
            struct_cast += f"""
            {field_name} = _{field_name};"""
        elif(field_type == 9):
            struct_cast_temp = generate_stub_attribute_struct_cast(field, interface, upper,isget=True,ismethod=True, iscomplex=True)
            struct_cast_temp = struct_cast_temp.replace(f"{field_name}.", f"{field_name}.data[i].")
            struct_cast_temp_lines = struct_cast_temp.split('\n')
            struct_cast_temp_lines = ['\t' + line for line in struct_cast_temp_lines]
            struct_cast_temp = '\n'.join(struct_cast_temp_lines)
        
            struct_cast += f"""{field_name}.data = new {field.type.reference.type.name}[_{field_name}.length];
            for(int i = 0; i < _{field_name}.length; i ++){{
                {field_name}[i] = new {field.type.reference.type.name}();
                {struct_cast_temp}
            }}
            """
        elif(field_type == 10):
            struct_cast_temp = generate_stub_attribute_struct_cast(field, interface, upper,isget=True,ismethod=True, iscomplex=True, isimplicit=True)
            struct_cast_temp = struct_cast_temp.replace(f"{field_name}.", f"{field_name}[i].")
            struct_cast_temp_lines = struct_cast_temp.split('\n')
            struct_cast_temp_lines = ['\t' + line for line in struct_cast_temp_lines]
            struct_cast_temp = '\n'.join(struct_cast_temp_lines)
            # {field.type.type.reference.name}[] #
            struct_cast += f"""{field_name} = new {field.type.type.reference.name}[_{field_name}.length];
            for(int i = 0; i < _{field_name}.length; i ++){{
                {field_name}[i] = new {field.type.type.reference.name}();
                {struct_cast_temp}
            }}
            """
        elif(field_type == 11):
            struct_cast_temp = generate_jni_map_cast(field, upper, interface, indentation=0, type=1)
            struct_cast += f"""{field_name} = new {field.type.reference.name}[_{field_name}.length];
                {struct_cast_temp}
            """
        
        
    return struct_cast

# stub code에 추가할 내용 필요(완료), returun 해서 stub code에 반환 필요
def generate_jni_method(method, package_name, interface ,java_package_name):
    jni_str = ""
    stub_str = ""
    jni_str += f"""
    /////////////////////////////////////////////////////////////////////////////////////////
    """
    
    method_low = lower_first_letter(method.name)
    method_cap = capitalize_first_letter(method.name)
    out_args_gen = ""
    out_args_con1 = "public {}ReturnType(){{\n\t".format(method_cap)
    out_args_con2 = "public {}ReturnType(".format(method_cap)
    out_args_con3 = ""
    return_type = ""
    return_type_service = ""
    return_type_jni = ""
    return_service = ""
    return_method = ""
    return_in_cast = ""
    return_out_cast = ""
    return_result = ""
    
    if len(method.out_args.values()) > 1:
        cnt = 1
        for arg in method.out_args.values():
            type_checked = check_type_ver2(arg,interface)
            arg_type = convert_java_code_type(arg.type.name)
            if(type_checked == 3):
                arg_type = convert_java_code_type(interface.arrays[arg.type.name].type.name) + "[]"
            elif(type_checked == 5):
                arg_type = convert_java_code_type(arg.type.type.name) + "[]"
            elif(type_checked == 6):
                arg_type = convert_java_code_type(arg.type.reference.type.name) + "[]"
            elif(type_checked == 8):
                arg_type = "byte"
            elif(type_checked == 9):
                arg_type = arg.type.reference.type.name + "[]"
            elif(type_checked == 10):
                arg_type = arg.type.type.reference.name + "[]"
            elif(type_checked == 11):
                arg_type = arg.type.reference.name + "[]"
            ### type별 변화
            out_args_con2 += "{} {}".format(arg_type, lower_first_letter(arg.name))
            out_args_gen += "public {} {};\n\t\t".format(arg_type,lower_first_letter(arg.name))
            out_args_con3 += "\t\tthis.{} = {};\n\t".format(lower_first_letter(arg.name), lower_first_letter(arg.name))
         
            if cnt < len(method.out_args.values()):
                out_args_con2 += ", "
                cnt += 1
        out_args_con2 += "){\n\t"
        #for arg in method.out_args.values():
            ### type별 변화
            
            ###
            #out_args_con1 += "\tthis.{} = 0;\n\t".format(arg.name)
            
        out_args_con1 += "\t}\n"
        out_args_con3 += "\t}\n"
        
        out_args_con2 += out_args_con3
        
        
        # if returnType needed
        jni_str += f"""
    static class {method_cap}ReturnType{{
        {out_args_gen}
        {out_args_con1}
        {out_args_con2}
    }}
    """
    
    if len(method.out_args.values()) > 1:
        return_type = "{}ReturnType".format(method_cap)
        return_type_service = return_type
        return_service = f"""{return_type} {method.name}Service = new {return_type}();"""
        return_result = f"""return {method.name}Service;"""
    elif len(method.out_args.values()) == 1:
        arg = next(iter(method.out_args.values()))
        type_checked = check_type_ver2(arg,interface)
        arg_type = convert_java_code_type(arg.type.name)
        return_type_service = arg_type
        return_type_service_init = ";"
        if(type_checked == 3):
            arg_type = convert_java_code_type(interface.arrays[arg.type.name].type.name) + "[]"
        elif(type_checked == 5):
            arg_type = convert_java_code_type(arg.type.type.name) + "[]"
            return_type_service = convert_java_code_type(arg.type.type.name) + "[]"
        elif(type_checked == 6):
            arg_type = convert_java_code_type(arg.type.reference.type.name) + "[]"
        elif(type_checked == 8):
            arg_type = "byte"
            return_type_service = "byte"
        elif(type_checked == 9):
            # arg_type = arg.type.reference.namespace.name + "JNI." + arg.type.reference.type.name + "[]"
            arg_type = arg.type.reference.type.name + "[]"
            return_type_service = arg.type.reference.name
            return_type_service_init = f""" = new {return_type_service}();"""
        elif(type_checked == 10):
            # arg_type = arg.type.type.reference.namespace.name + "JNI." + arg.type.type.reference.name + "[]"
            arg_type = arg.type.type.reference.name + "[]"
            return_type_service = arg.type.type.reference.name + "[]"
            return_type_service_init = f""";"""
        elif(type_checked == 11):
            arg_type = arg.type.reference.name + "[]"
            return_type_service = arg.type.reference.name + "[]"
            return_type_service_init = f""";"""
            
        if(type_checked >= 3 and type_checked <= 7 and type_checked != 5):
            return_type_service_init = " = new {}();".format(return_type_service)
        return_type = "{}".format(arg_type)
        return_service = f"""{return_type_service} {lower_first_letter(arg.name)}{return_type_service_init}"""
        return_result = f"""return {lower_first_letter(arg.name)};"""
    else:
        return_type = "void"
        return_type_service = "void"
        return_service = "//No Return value"
        return_result = ""
        
    in_args = ""
    in_args_jni = ""
    in_args_call = ""
    in_args_call_jni = ""
    in_args_valid = ""
    if len(method.in_args.values()) >= 1 :
        in_args_valid = ", "
    cnt = 1
    for arg in method.in_args.values():
        type_checked = check_type_ver2(arg,interface)
        arg_type = convert_java_code_type(arg.type.name)
        arg_type_service = convert_java_code_type(arg.type.name)
        if(type_checked == 3):
            arg_type = convert_java_code_type(interface.arrays[arg.type.name].type.name) + "[]"
            return_in_cast += f"""{arg_type} _{lower_first_letter(arg.name)} = {lower_first_letter(arg.name)}.data;"""
            in_args_call += "_{}".format(lower_first_letter(arg.name))
            in_args_call_jni += "{}".format(lower_first_letter(arg.name))
        elif(type_checked == 5):
            arg_type = convert_java_code_type(arg.type.type.name) + "[]"
            arg_type_service = convert_java_code_type(arg.type.type.name) + "[]"
            in_args_call += "{}".format(lower_first_letter(arg.name))
            in_args_call_jni += "{}".format(lower_first_letter(arg.name))
        elif(type_checked == 6):
            arg_type = convert_java_code_type(arg.type.reference.type.name) + "[]"
            return_in_cast += f"""{arg_type} _{lower_first_letter(arg.name)} = {lower_first_letter(arg.name)}.data;"""
            in_args_call += "_{}".format(lower_first_letter(arg.name))
            in_args_call_jni += "{}".format(lower_first_letter(arg.name))
        elif(type_checked == 4 or type_checked == 7):
            return_in_cast += f"""{arg.type.reference.namespace.name+"JNI."}{arg_type.split('.')[-1]} _{lower_first_letter(arg.name)} = new {arg.type.reference.namespace.name+"JNI."}{arg_type.split('.')[-1]}();"""
            return_in_cast += generate_jni_attribute_struct_cast(arg,interface,upper="",isget=False)
            in_args_call += "_{}".format(lower_first_letter(arg.name))
            in_args_call_jni += "{}".format(lower_first_letter(arg.name))
        elif(type_checked == 8):
            arg_type = "byte"
            arg_type_service = "byte"
            return_in_cast += f"""byte _{lower_first_letter(arg.name)} = {lower_first_letter(arg.name)};"""
            in_args_call += "_{}".format(lower_first_letter(arg.name))
            in_args_call_jni += "{}".format(lower_first_letter(arg.name))
        elif(type_checked == 9):
            arg_type = arg.type.reference.type.name + "[]"
            arg_type_service = arg.type.reference.name
            return_in_cast_temp = generate_stub_attribute_struct_cast(arg, interface, upper="", isget=False, ismethod= False, iscomplex = True)
            return_in_cast_temp = return_in_cast_temp.replace(f"_{lower_first_letter(arg.name)}.", f"_{lower_first_letter(arg.name)}[i].")
            return_in_cast_temp = return_in_cast_temp.replace(f"{lower_first_letter(arg.name)}.", f"{lower_first_letter(arg.name)}.data[i].")
            return_in_cast_temp_lines = return_in_cast_temp.split('\n')
            return_in_cast_temp_lines = ['\t' + line for line in return_in_cast_temp_lines]
            return_in_cast_temp = '\n'.join(return_in_cast_temp_lines)
            return_in_cast += f"""{arg.type.reference.namespace.name}JNI.{arg.type.reference.type.name}[] _{lower_first_letter(arg.name)} = new {arg.type.reference.namespace.name}JNI.{arg.type.reference.type.name}[{lower_first_letter(arg.name)}.data.length];
            for(int i = 0; i < {lower_first_letter(arg.name)}.data.length; i++){{
                _{lower_first_letter(arg.name)}[i] = new {arg.type.reference.namespace.name}JNI.{arg.type.reference.type.name}();{return_in_cast_temp}
            }}"""
            in_args_call += "_{}".format(lower_first_letter(arg.name))
            in_args_call_jni += "{}".format(lower_first_letter(arg.name))
        elif(type_checked == 10):
            arg_type = arg.type.type.reference.name + "[]"
            arg_type_service = arg.type.type.reference.name + "[]"
            return_in_cast_temp = generate_stub_attribute_struct_cast(arg, interface, upper="", isget=False, ismethod= False, iscomplex = True, isimplicit=True)
            return_in_cast_temp = return_in_cast_temp.replace(f"_{lower_first_letter(arg.name)}.", f"_{lower_first_letter(arg.name)}[i].")
            return_in_cast_temp = return_in_cast_temp.replace(f"{lower_first_letter(arg.name)}.", f"{lower_first_letter(arg.name)}[i].")
            return_in_cast_temp_lines = return_in_cast_temp.split('\n')
            return_in_cast_temp_lines = ['\t' + line for line in return_in_cast_temp_lines]
            return_in_cast_temp = '\n'.join(return_in_cast_temp_lines)
            return_in_cast += f"""{arg.type.type.reference.namespace.name}JNI.{arg.type.type.reference.name}[] _{lower_first_letter(arg.name)} = new {arg.type.type.reference.namespace.name}JNI.{arg.type.type.reference.name}[{lower_first_letter(arg.name)}.length];
            for(int i = 0; i < {lower_first_letter(arg.name)}.length; i++){{
                _{lower_first_letter(arg.name)}[i] = new {arg.type.type.reference.namespace.name}JNI.{arg.type.type.reference.name}();{return_in_cast_temp}
            }}"""
            in_args_call += "_{}".format(lower_first_letter(arg.name))
            in_args_call_jni += "{}".format(lower_first_letter(arg.name))
        elif(type_checked == 11):
            arg_type = arg.type.reference.name + "[]"
            arg_type_service = arg.type.reference.name + "[]"
            return_in_cast_temp = generate_jni_map_cast(arg, upper="",interface=interface, indentation=0,type=2)
            return_in_cast += f"""{arg.type.reference.namespace.name}JNI.{arg.type.reference.name}[] _{lower_first_letter(arg.name)} = new {arg.type.reference.namespace.name}JNI.{arg.type.reference.name}[{lower_first_letter(arg.name)}.length];
            {return_in_cast_temp}
            """
            in_args_call += "_{}".format(lower_first_letter(arg.name))
            in_args_call_jni += "{}".format(lower_first_letter(arg.name))
        else:
            in_args_call += "{}".format(lower_first_letter(arg.name))
            in_args_call_jni += "{}".format(lower_first_letter(arg.name))
        in_args += "{} {}".format(arg_type_service, lower_first_letter(arg.name))
        if len(arg_type.split('.')) > 1:
            in_args_jni += "{} {}".format(arg_type.split('.')[0]+"JNI."+arg_type.split('.')[-1], lower_first_letter(arg.name))
        else:
            in_args_jni += "{} {}".format(arg_type, lower_first_letter(arg.name))
        
        if cnt < len(method.in_args.values()):
                in_args += ", "
                in_args_jni += ", "
                in_args_call += ", "
                in_args_call_jni += ", "
                cnt += 1
    
    if(return_type != "void"):
        if(len(method.out_args.values())>1):
            return_method = f"""{capitalize_first_letter(interface.name)}JNI.{return_type} _{method.name}Service = myProxy.{method.name}({in_args_call});"""
            #return_out_cast = generate_jni_attribute_struct_cast()
            return_out_cast = generate_jni_method_out_cast(method,interface,upper=method.name+"Service")
        else:
            arg_temp = next(iter(method.out_args.values()))
            type_temp = check_type_ver2(arg_temp, interface)
            if(type_temp == 1 or type_temp == 2):
                return_method = f"""{convert_java_code_type(arg_temp.type.name)} _{lower_first_letter(arg_temp.name)} = myProxy.{method.name}({in_args_call});"""
            elif(type_temp == 5):
                return_method = f"""{convert_java_code_type(arg_temp.type.type.name)}[] _{lower_first_letter(arg_temp.name)} = myProxy.{method.name}({in_args_call});"""
            elif(type_temp == 4 or type_temp == 7):
                return_method = f"""{arg_temp.type.reference.namespace.name+"JNI."}{return_type.split('.')[-1]} _{lower_first_letter(arg_temp.name)} = myProxy.{method.name}({in_args_call});"""
            elif(type_temp == 8):
                return_method = f"""byte _{lower_first_letter(arg_temp.name)} = myProxy.{method.name}({in_args_call});"""
            elif(type_temp == 9):
                return_method = f"""{arg_temp.type.reference.type.reference.namespace.name+"JNI."}{return_type} _{lower_first_letter(arg_temp.name)} = myProxy.{method.name}({in_args_call});"""
            elif(type_temp == 10):
                return_method = f"""{arg_temp.type.type.reference.namespace.name+"JNI."}{return_type} _{lower_first_letter(arg_temp.name)} = myProxy.{method.name}({in_args_call});"""
            elif(type_temp == 11):
                return_method = f"""{arg_temp.type.reference.namespace.name+"JNI."}{return_type} _{lower_first_letter(arg_temp.name)} = myProxy.{method.name}({in_args_call});"""
            else:
                return_method = f"""{return_type} _{lower_first_letter(arg_temp.name)} = myProxy.{method.name}({in_args_call});"""
            return_out_cast = generate_jni_method_out_cast(method,interface,upper="")
    else:
        return_method = f"""myProxy.{method.name}({in_args_call});"""
    
    # method call
    if len(return_type.split('.')) > 1:
        return_type_jni = return_type.split('.')[0]+"JNI."+return_type.split('.')[-1]
    else:
        return_type_jni = return_type
    fireandForget = ""
    if(return_type_jni == "void"):
        fireandForget = ""
    else:
        fireandForget = "return "
    
    jni_str += f"""
    public {return_type_jni} {method.name}({in_args_jni}){{
        {fireandForget}{method_cap}(this.proxyptr{in_args_valid}{in_args_call_jni});
    }}
    public native {return_type_jni} {method_cap}(long proxyptr{in_args_valid}{in_args_jni});
    """
    return_null = ""
    if(return_type_service == "void"):
        return_null = ""
    elif(return_type_service in ['Int8', 'UInt8', 'Int16', 'UInt16', 'Int32', 'UInt32', 'Int64', 'UInt64', 'Double', 'Float']):
        return_null = "0"
    elif(return_type_service == 'boolean'):
        return_null = "false"
    else:
        return_null = " null"
    stub_str += f"""
        @Override
        public {return_type_service} {method.name}({in_args}) throws RemoteException{{
            if(myProxy == null){{
                if(!proxyGeneration()){{
                    return{return_null};
                }}
            }}
            {return_service}
            {return_in_cast}
            {return_method}
            {return_out_cast}
            {return_result}
        }}
        """
    jni_str += f"""
    /////////////////////////////////////////////////////////////////////////////////////////"""
    
    return jni_str, stub_str
################################################ TypeCollection and Data Types #######################################
###JNI Typecollection generation 하는 부분
def generate_jni_typecollection(typecollection, java_package, is_typecollection = True):
    jni_str = ""
    if(is_typecollection):
        jni_str = f"""package {java_package};"""
    typecollection_cap = capitalize_first_letter(typecollection.name)
    typecollection_low = lower_first_letter(typecollection.name)
    if(is_typecollection):
        jni_str +=f"""
public class {typecollection_cap}JNI{{
    """
    for structs in typecollection.structs.values():
        attr_type = structs.name
        struct = typecollection.structs[attr_type]
        jni_str += f"""
    public static class {attr_type} {{"""
        for field in struct.fields.values():
            type_checked_field = check_type_ver2(field, typecollection)
            if(type_checked_field == 3 or type_checked_field == 5 or type_checked_field == 6):
                if(type_checked_field == 3):
                    array = typecollection.arrays[field.type.name]
                elif(type_checked_field == 5):
                    array = field.type
                elif(type_checked_field == 6):
                    array = field.type.reference
                jni_str += f"""\n\t\t{convert_java_code_type(array.type.name)}[] {field.name};"""    
            elif(type_checked_field == 7): #or (type_checked_field == 8 and field.type.reference.namespace.name != typecollection.name)):
                jni_str += f"""\n\t\t{convert_java_code_type(field.type.name).split('.')[0]+"JNI."}{convert_java_code_type(field.type.name).split('.')[-1]} {field.name};"""
            elif(type_checked_field == 8):
                jni_str += f"""\n\t\tbyte {field.name};"""
            elif(type_checked_field == 9):
                jni_str += f"""\n\t\t{field.type.reference.type.reference.name}[] {field.name};"""
            elif(type_checked_field == 10):
                jni_str += f"""\n\t\t{field.type.type.reference.name}[] {field.name};"""
            elif(type_checked_field == 11):
                jni_str += f"""\n\t\t{field.type.reference.name}[] {field.name};"""
            else:
                jni_str += f"""\n\t\t{convert_java_code_type(field.type.name)} {field.name};"""
        jni_str += "\n\n\t\tpublic {}(){{}}".format(attr_type)
        jni_str += f"""
        \n\t\tpublic {attr_type}("""
        cnt = 1
        for field in struct.fields.values():
            type_checked_field = check_type_ver2(field, typecollection)
            if(type_checked_field == 3 or type_checked_field == 5 or type_checked_field == 6):
                if(type_checked_field == 3):
                    array = typecollection.arrays[field.type.name]
                elif(type_checked_field == 5):
                    array = field.type
                elif(type_checked_field == 6):
                    array = field.type.reference
                jni_str += "{}[] {}".format(convert_java_code_type(array.type.name),field.name)
            elif(type_checked_field == 7): # or (type_checked_field == 8 and field.type.reference.namespace.name != typecollection.name)):
                jni_str += "{}{} {}".format(convert_java_code_type(field.type.name).split('.')[0]+"JNI.",convert_java_code_type(field.type.name).split('.')[-1], field.name)
            elif(type_checked_field == 8):
                jni_str += "byte {}".format(field.name)
            elif(type_checked_field == 9):
                jni_str += "{}[] {}".format(field.type.reference.type.reference.name, field.name)
            elif(type_checked_field == 10):
                jni_str += "{}[] {}".format(field.type.type.reference.name, field.name)
            elif(type_checked_field == 11):
                jni_str += "{}[] {}".format(field.type.reference.name, field.name)
            else:
                jni_str += "{} {}".format(convert_java_code_type(field.type.name), field.name)
            if(cnt < len(struct.fields.values())):
                jni_str += ", "
                cnt += 1
        jni_str += "){"
        for field in struct.fields.values():
            jni_str += f"""\n\t\t\tthis.{field.name} = {field.name};"""
        jni_str += "\n\t\t}\n\t}"
        jni_str += f"""
    public {attr_type} {capitalize_first_letter(attr_type.split('.')[-1])}ToCPP() {{
        return new {attr_type}();
    }}"""
    
    for maps in typecollection.maps.values():
        value_type = ""
        if(isinstance(maps.value_type, ast.Reference)):
            if(isinstance(maps.value_type.reference, ast.Struct)):
                value_type = convert_java_code_type(maps.value_type.name)
            elif(isinstance(maps.value_type.reference, ast.Array)):
                value_type = convert_java_code_type(maps.value_type.reference.type.name) + "[]"
        elif(isinstance(maps.value_type, ast.Array)):
            value_type = convert_java_code_type(maps.value_type.type.name) + "[]"
        elif(maps.value_type.name == 'ByteBuffer'):
            value_type = "byte[]"
        else:
            value_type = convert_java_code_type(maps.value_type.name)
        jni_str += f"""
    public static class {maps.name} {{
        {convert_java_code_type(maps.key_type.name)} key;
        {value_type} value;
        public {maps.name}() {{}}
        public {maps.name}({convert_java_code_type(maps.key_type.name)} key, {value_type} value){{
            this.key = key;
            this.value = value;
        }}
    }}"""
        jni_str += f"""
    public {maps.name} {capitalize_first_letter(maps.name.split('.')[-1])}ToCPP() {{
        return new {maps.name}();
    }}"""

    if(is_typecollection):
        jni_str += f"""
}}""" # end of typecollection
        
    return jni_str
####################################### Broadcast #########################################################################
def generate_jni_broadcast(broadcast, interface):
    jni_str = ""
    broadcast_cap = capitalize_first_letter(broadcast.name)
    stub_main = ""
    stub_handler = ""
    
    # broadcast 1 JNI gen
    jni_str += f"""///////////////////////////////////////////////////////////////////////////////////////
    int {broadcast_cap}Subscription = -1;
    public native void subBroadcast{broadcast_cap}(long proxyptr);
    public native void unsubBroadcast{broadcast_cap}(long proxyptr, int subscription);
    public void subscribe{broadcast_cap}(){{
        subBroadcast{broadcast_cap}(this.proxyptr);
        ++this.{broadcast_cap}Subscription;
    }}
    public void unsubscribe{broadcast_cap}(){{
        if(this.{broadcast_cap}Subscription >= 0){{
            unsubBroadcast{broadcast_cap}(this.proxyptr, this.{broadcast_cap}Subscription--);
        }}
    }}
    """
    # broadcast 2 Callback, not needed after integrating the code with Stub
    
    # braodcast 4 JNI Callback gen
    out_args = ""
    out_args_call = ""
    jni_str += f"""
    public void subBroadcast{broadcast_cap}Callback("""
    count_args = 1
    for out_arg in broadcast.out_args.values():
        arg_type_checked = check_type_ver2(out_arg, interface)
        if(arg_type_checked == 1 or arg_type_checked == 2):
            jni_str += "{} {}".format(convert_java_code_type(out_arg.type.name),(out_arg.name))
            out_args += "{} _{}".format(convert_java_code_type(out_arg.type.name),lower_first_letter(out_arg.name))
            out_args_call += "{}".format(lower_first_letter(out_arg.name))
        elif(arg_type_checked == 3 or arg_type_checked == 5 or arg_type_checked == 6):
            if(out_arg.type.name is None):
                jni_str += "{}[] {}".format(convert_java_code_type(out_arg.type.type.name),out_arg.name)
                out_args += "{}[] _{}".format(convert_java_code_type(out_arg.type.type.name),lower_first_letter(out_arg.name))
                out_args_call += "{}".format(lower_first_letter(out_arg.name))
            else:
                jni_str += "{}[] {}".format(convert_java_code_type(out_arg.type.reference.type.name), out_arg.name)
                out_args += "{}[] _{}".format(convert_java_code_type(out_arg.type.reference.type.name),lower_first_letter(out_arg.name))
                out_args_call += "{}".format(lower_first_letter(out_arg.name))
        elif(arg_type_checked == 8):
            jni_str += "{} {}".format("byte", out_arg.name)
            out_args += "{} _{}".format("byte",lower_first_letter(out_arg.name))
            out_args_call += "{}".format(lower_first_letter(out_arg.name))
        elif(arg_type_checked == 9):
            jni_str += "{}[] {}".format(out_arg.type.reference.type.name,out_arg.name)
            out_args += "{}JNI.{}[] _{}".format(out_arg.type.reference.namespace.name,out_arg.type.reference.type.name, lower_first_letter(out_arg.name))
            out_args_call += "{}".format(lower_first_letter(out_arg.name))
        elif(arg_type_checked == 10):
            jni_str += "{}[] {}".format(out_arg.type.type.reference.name, lower_first_letter(out_arg.name))
            out_args += "{}JNI.{}[] _{}".format(out_arg.type.type.reference.namespace.name,out_arg.type.type.reference.name,lower_first_letter(out_arg.name))
            out_args_call += "{}".format(lower_first_letter(out_arg.name))
        elif(arg_type_checked == 11):
            jni_str += "{}[] {}".format(out_arg.type.reference.name, lower_first_letter(out_arg.name))
            out_args += "{}JNI.{}[] _{}".format(out_arg.type.reference.namespace.name,out_arg.type.reference.name,lower_first_letter(out_arg.name))
            out_args_call += "{}".format(lower_first_letter(out_arg.name))
        else:
            jni_str += "{} {}".format(out_arg.type.name, (out_arg.name))
            out_args += "{}JNI.{} _{}".format(out_arg.type.reference.namespace.name,out_arg.type.name, lower_first_letter(out_arg.name))
            out_args_call += "{}".format(lower_first_letter(out_arg.name))
        #out_args_jni += 
        if(count_args < len(broadcast.out_args.values())):
            jni_str += ", "
            out_args_call += ", "
            out_args += ", "
            count_args += 1
    jni_str += f"""){{
        service.{broadcast_cap}Callback("""
    count_args_call = 1
    for out_arg in broadcast.out_args.values():
        arg_type_checked = check_type_ver2(out_arg, interface)
        if(arg_type_checked == 1 or arg_type_checked == 2):
            jni_str += "{}".format((out_arg.name))
        elif(arg_type_checked == 3 or arg_type_checked == 5 or arg_type_checked == 6):
            if(out_arg.type.name is None):
                jni_str += "{}".format(out_arg.name)
            else:
                jni_str += "{}".format(out_arg.name)
        else:
            jni_str += "{}".format(out_arg.name)
        #out_args_jni += 
        if(count_args_call < len(broadcast.out_args.values())):
            jni_str += ", "
            count_args_call += 1
    jni_str += f""");
    }}
    ///////////////////////////////////////////////////////////////////////////////////////
    """
    
    # bcast cast for callback, needs to be done for out_args
    broadcast_cast = ""
    for arg in broadcast.out_args.values():
        cast_type = check_type_ver2(arg, interface)
        arg_java = convert_java_code_type(arg.type.name)
        if(arg_java is None):
            arg_java = convert_java_code_type(arg.type.type.name) + "[]"
        if(cast_type == 3 or cast_type == 6):
            broadcast_cast += f"""{arg.type.name.split('.')[-1]} {lower_first_letter(arg.name)} = new {arg.type.name.split('.')[-1]}();
            {lower_first_letter(arg.name)}.data = _{lower_first_letter(arg.name)};
            """
        elif(cast_type == 4 or cast_type == 7):
            broadcast_cast += f"""{arg.type.name.split('.')[-1]} {lower_first_letter(arg.name)} = new {arg.type.name.split('.')[-1]}();"""
            broadcast_cast += generate_stub_attribute_struct_cast(arg,interface,upper="",isget=True) + "\n\t\t\t"
        elif(cast_type == 8):
            broadcast_cast += f"""byte {lower_first_letter(arg.name)} = _{lower_first_letter(arg.name)};
            """
        elif(cast_type == 9 or cast_type == 10):
            broadcast_cast_temp = ""
            if(cast_type == 9):
                broadcast_cast += f"""{arg.type.name.split('.')[-1]} {lower_first_letter(arg.name)} = new {arg.type.name.split('.')[-1]}();
            {lower_first_letter(arg.name)}.data = new {arg.type.reference.type.name}[_{lower_first_letter(arg.name)}.length];"""
                broadcast_cast_temp = generate_stub_attribute_struct_cast(arg, interface, upper="", isget=True, ismethod= False, iscomplex= True)
                broadcast_cast_temp = broadcast_cast_temp.replace(f"_{lower_first_letter(arg.name)}.", f"_{lower_first_letter(arg.name)}[i].")
                broadcast_cast_temp = broadcast_cast_temp.replace(f"{lower_first_letter(arg.name)}.", f"{lower_first_letter(arg.name)}.data[i].")
            else:
                broadcast_cast += f"""{arg.type.type.name.split('.')[-1]}[] {lower_first_letter(arg.name)} = new {arg.type.type.name.split('.')[-1]}[_{lower_first_letter(arg.name)}.length];"""
                broadcast_cast_temp = generate_stub_attribute_struct_cast(arg, interface, upper="", isget=True, ismethod= False, iscomplex= True, isimplicit=True)
                broadcast_cast_temp = broadcast_cast_temp.replace(f"_{lower_first_letter(arg.name)}.", f"_{lower_first_letter(arg.name)}[i].")
                broadcast_cast_temp = broadcast_cast_temp.replace(f"{lower_first_letter(arg.name)}.", f"{lower_first_letter(arg.name)}[i].")
            broadcast_cast_temp_lines = broadcast_cast_temp.split('\n')
            broadcast_cast_temp_lines = ['\t' + line for line in broadcast_cast_temp_lines]
            broadcast_cast_temp = '\n'.join(broadcast_cast_temp_lines)
            if(cast_type == 9):
                for_loop_temp = f"""
            for(int i = 0; i < _{lower_first_letter(arg.name)}.length; i++){{
                {lower_first_letter(arg.name)}.data[i] = new {arg.type.reference.type.name}();
                {broadcast_cast_temp}
            }}
            """
            elif(cast_type == 10):
                for_loop_temp = f"""
            for(int i = 0; i < _{lower_first_letter(arg.name)}.length; i++){{
                {lower_first_letter(arg.name)}.data[i] = new {arg.type.type.reference.name}();
                {broadcast_cast_temp}
            }}
            """
            broadcast_cast += for_loop_temp
        elif(cast_type == 11):
            broadcast_cast += f"""{arg.type.name.split('.')[-1]}[] {lower_first_letter(arg.name)} = new {arg.type.name.split('.')[-1]}[_{lower_first_letter(arg.name)}.length];
            """
            broadcast_cast += generate_jni_map_cast(arg, upper="",interface=interface, indentation=0, type=0)
        else:
            broadcast_cast += f"""{arg_java} {lower_first_letter(arg.name)} = _{lower_first_letter(arg.name)};
            """

    # AIDL 분리 버전
    stub_handler += f"""
    private static ArrayList<{capitalize_first_letter(interface.name)}{broadcast_cap}Callback> {broadcast_cap}Callback = new ArrayList<>();
    void {broadcast_cap}Callback({out_args}){{
        if(this.{broadcast_cap}Callback != null){{
            {broadcast_cast}for({capitalize_first_letter(interface.name)}{broadcast_cap}Callback callback : this.{broadcast_cap}Callback){{
                try {{
                    callback.on{broadcast_cap}Received({out_args_call});
                }} catch (RemoteException e) {{
                    throw new RuntimeException(e);
                }}
            }}
        }}
    }}
    """
    
    # stub main
    ## subscribe # 분리하는 버전
    stub_main += f"""
        @Override
        public void subscribe{broadcast_cap}({capitalize_first_letter(interface.name)}{broadcast_cap}Callback callback) throws RemoteException {{
            if(myProxy == null){{
                if(!proxyGeneration()){{
                    return;
                }}
            }}
            if(!{capitalize_first_letter(interface.name)}Service.{broadcast_cap}Callback.contains(callback)){{
                {capitalize_first_letter(interface.name)}Service.{broadcast_cap}Callback.add(callback);
                if({capitalize_first_letter(interface.name)}Service.{broadcast_cap}Callback.size() == 1){{
                    myProxy.subscribe{broadcast_cap}();
                }}
            }}
        }}
        
        @Override
        public void unsubscribe{broadcast_cap}({capitalize_first_letter(interface.name)}{broadcast_cap}Callback callback) throws RemoteException {{
            if(myProxy == null){{
                if(!proxyGeneration()){{
                    return;
                }}
            }}
            if({capitalize_first_letter(interface.name)}Service.{broadcast_cap}Callback.contains(callback)){{
                {capitalize_first_letter(interface.name)}Service.{broadcast_cap}Callback.remove(callback);
                if({capitalize_first_letter(interface.name)}Service.{broadcast_cap}Callback.size() == 1){{
                    myProxy.unsubscribe{broadcast_cap}();
                }}
            }}
        }}
        """
    
    
    
    return jni_str, stub_main, stub_handler
###############################################################################################################################
################################ FIDL AST into codes #######################################################################
def generate_src_client_from_fidl_interface(interface, package_name, java_package_name, typecollection):
    jni_str = ""
    interface_str = ""
    list_references = set()
    stub_handler = ""
    stub_main = ""
    stub_handler_temp = ""
    stub_main_temp = ""
    jni_str += generate_jni_typecollection(interface, java_package_name, False)
    
    ### Map을 구조체 배열로 casting 하는 것
    # if(interface.maps):
    #     for map in interface.maps.values():
    #         map_to_struct = ast.Struct("map")
            
    #         field_key = ast.StructField("key", map.key_type)
    #         field_value = ast.StructField("value", map.value_type)
            
    #         map_to_struct.fields.update({field_key.name:field_key.type})
    #         map_to_struct.fields.update({field_value.name:field_value.type})
            
    #         map_array = ast.Array(map.name, map_to_struct)
    #         interface.arrays.update({map.name:map_array})
            
    #         print(dir(map_array), map_array.type, check_type_ver2(map_array, interface))
            
            
    
    ### 변수명 겹치는거 처리하는 부분
    if (interface.attributes):
        for attribute in interface.attributes.values():
            if(isinstance(attribute.type, ast.Reference)):
                if(isinstance(attribute.type.reference, ast.Attribute) or isinstance(attribute.type.reference, ast.Method) or isinstance(attribute.type.reference, ast.Broadcast)):
                    if(attribute.type.name.split('.')[0] in interface.enumerations):
                        attribute.type.reference = interface.enumerations[attribute.type.name]
                    elif(attribute.type.name.split('.')[0] in interface.structs):
                        attribute.type.reference = interface.structs[attribute.type.name]
                    elif(attribute.type.name.split('.')[0] in interface.arrays):
                        attribute.type.reference = interface.arrays[attribute.type.name]
                    elif(attribute.type.name.split('.')[0] in typecollection):
                        attribute.type.reference = typecollection[attribute.type.name.split('.')[0]][attribute.type.name.split('.')[-1]]
    if (interface.methods):
        for method in interface.methods.values():
            for arg in method.out_args.values():
                if(isinstance(arg.type, ast.Reference)):
                    if(isinstance(arg.type.reference, ast.Attribute) or isinstance(arg.type.reference, ast.Method) or isinstance(arg.type.reference, ast.Broadcast)):
                        if(arg.type.name.split('.')[0] in interface.enumerations):
                            arg.type.reference = interface.enumerations[arg.type.name]
                        elif(arg.type.name.split('.')[0] in interface.structs):
                            arg.type.reference = interface.structs[arg.type.name]
                        elif(arg.type.name.split('.')[0] in interface.arrays):
                            arg.type.reference = interface.arrays[arg.type.name]
                        elif(arg.type.name.split('.')[0] in typecollection):
                            arg.type.reference = typecollection[arg.type.name.split('.')[0]][arg.type.name.split('.')[-1]]
            for arg in method.in_args.values():
                if(isinstance(arg.type, ast.Reference)):
                    if(isinstance(arg.type.reference, ast.Attribute) or isinstance(arg.type.reference, ast.Method) or isinstance(arg.type.reference, ast.Broadcast)):
                        if(arg.type.name.split('.')[0] in interface.enumerations):
                            arg.type.reference = interface.enumerations[arg.type.name]
                        elif(arg.type.name.split('.')[0] in interface.structs):
                            arg.type.reference = interface.structs[arg.type.name]
                        elif(arg.type.name.split('.')[0] in interface.arrays):
                            arg.type.reference = interface.arrays[arg.type.name]
                        elif(arg.type.name.split('.')[0] in typecollection):
                            arg.type.reference = typecollection[arg.type.name.split('.')[0]][arg.type.name.split('.')[-1]]
    if (interface.broadcasts):
        for broadcast in interface.broadcasts.values():
            for arg in broadcast.out_args.values():
                if(isinstance(arg.type, ast.Reference)):
                    if(isinstance(arg.type.reference, ast.Attribute) or isinstance(arg.type.reference, ast.Method) or isinstance(arg.type.reference, ast.Broadcast)):
                        if(arg.type.name.split('.')[0] in interface.enumerations):
                            arg.type.reference = interface.enumerations[arg.type.name]
                        elif(arg.type.name.split('.')[0] in interface.structs):
                            arg.type.reference = interface.structs[arg.type.name]
                        elif(arg.type.name.split('.')[0] in interface.arrays):
                            arg.type.reference = interface.arrays[arg.type.name]
                        elif(arg.type.name.split('.')[0] in typecollection):
                            arg.type.reference = typecollection[arg.type.name.split('.')[0]][arg.type.name.split('.')[-1]]
    ###
    
    jni_attribute_cnt = 1
    if(interface.attributes):
        for attribute in interface.attributes.values():
            if(isinstance(attribute.type, ast.Reference)):
                list_references.add(attribute.type.reference)
            interface_str += generate_src_attribute(attribute, package_name, interface, java_package_name)
            jni_str_temp, stub_main_temp, stub_handler_temp  = generate_jni_attribute(attribute, interface, jni_attribute_cnt=jni_attribute_cnt)
            jni_str += jni_str_temp
            stub_handler += stub_handler_temp
            stub_main += stub_main_temp
            jni_attribute_cnt += 1
    if(interface.broadcasts):
        for broadcast in interface.broadcasts.values():
            interface_str += generate_src_broadcast(broadcast=broadcast,package_name=package_name,interface=interface,java_package_name=java_package_name)
    if(interface.methods):
        for method in interface.methods.values():
            for arg in method.in_args.values():
                if(isinstance(arg.type, ast.Reference)):
                    list_references.add(arg.type.reference)
            for arg in method.out_args.values():
                if(isinstance(arg.type, ast.Reference)):
                    list_references.add(arg.type.reference)
            interface_str += generate_src_method(method, package_name, interface, java_package_name)
            jni_str_temp, stub_main_temp = generate_jni_method(method, package_name, interface, java_package_name)
            jni_str += jni_str_temp
            stub_main += stub_main_temp
    #interface_str += "\n}"
    return interface_str, jni_str, stub_main, stub_handler


def convert_to_src_client(packages, jni_version, jpackage_name, output_dir):
    interfaces = OrderedDict()
    stub_main = OrderedDict()
    stub_handler = OrderedDict()
    jnis = OrderedDict()
    extends = OrderedDict()
    jni_typecollection = OrderedDict()
    imports = list()
    java_package_name = jpackage_name.split(".")
    java_packages = ""
    java_class = ""
    package_name = ""
    for name in java_package_name:
        java_packages += "{}_".format(name)
        java_class += "{}/".format(name)
        
    versions = OrderedDict()
    # package_names = package_name.split(".")
    # cpp_package = ""
    # cpp_header = ""
    # for name in package_names:
    #     cpp_package += "::{}".format(name)
    #     cpp_header += "{}/".format(name)
    os.makedirs(output_dir + '/src', exist_ok=True)
    os.makedirs(output_dir + '/stub', exist_ok=True)

    for package in packages.values():
        ## exception
        # try:
        package_name = package.name
        package_names = package.name.split(".")
        cpp_package = ""
        cpp_header = ""
        for name in package_names:
            cpp_package += "::{}".format(name)
            cpp_header += "{}/".format(name)
        if(package.interfaces):
            for interface in package.interfaces.values():
                # Unsupported data type filtering
                # if(interface.maps):
                #    raise Exception("Interface {}, Maps are not supported".format(interface.name))
                
                
                interface_str, jni_attr_str, stub_main_str, stub_handler_str = generate_src_client_from_fidl_interface(interface, package.name, java_package_name, package.typecollections)
                interfaces[interface.name] = interface_str
                jnis[interface.name] = jni_attr_str
                stub_main[interface.name] = stub_main_str
                stub_handler[interface.name] = stub_handler_str
                versions[interface.name] = interface.version.major
                extends[interface.name] = interface.extends if interface.extends else None
                if(interface.broadcasts):
                    for broadcast in interface.broadcasts.values(): 
                        jni_str_temp, stub_main_temp, stub_handler_temp = generate_jni_broadcast(broadcast, interface)
                        jnis[interface.name] += jni_str_temp
                        stub_main[interface.name] += stub_main_temp
                        stub_handler[interface.name] += stub_handler_temp
        if(package.typecollections):
            for typecollection in package.typecollections.values():
        #         interface_str, import_str = generate_aidl_interface_from_fidl_typecollection(typecollection, package_name)
        #         interfaces[typecollection.name] = interface_str
                jni_typecollection_str = generate_jni_typecollection(typecollection, jpackage_name)
                jni_typecollection[typecollection.name] = jni_typecollection_str
                imports.append(typecollection.name)
        ## exception
        # except (Exception) as e:
        #     print("ERROR during code generation: {}".format(e))
        #     continue
    
    for interface, interface_str in interfaces.items():
        version_str = versions[interface]
        src_str = ""
        src_str += "// Auto-generated by FIDL-SRC Converter\n"
        src_str += "// Filename: {}Client.cpp\n\n".format(interface)
        src_str += "#include <iostream>\n#include <jni.h>\n#include <string.h>\n#include <CommonAPI/CommonAPI.hpp>\n#include \"v{}/{}{}Proxy.hpp\"\n\n".format(version_str,cpp_header,interface)
        if(extends[interface] is not None):
            src_str += "//extends interface {}\n\n".format(extends[interface],extends[interface]) #flattening
        src_str += "#define LOGI(...) ((void)__android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__))\n#define LOGE(...) ((void)__android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__))\n#include <android/log.h>\n#define LOG_TAG \"{}ClientCPP\"\n".format(interface)
        src_str += "using namespace v{}{};\n\n".format(version_str,cpp_package)
        
        # 변수들
        interface_cap = interface
        interface_low = interface
        interface_extension = "JNI"
        #######
        
        class_code_template = f"""class {interface_cap}Client{{\n\tpublic:\n\t{interface_cap}Client(){{\n\t}};\n\tstd::shared_ptr<{interface_cap}Proxy<>> myProxy;\n\tvoid main(std::string pinstance, std::string pconnection);\n\tjclass {interface_cap}Clazz;\n\tjobject {interface_cap}Instance;"""
        for item in imports:
            class_code_template += "\n\tjclass {}Clazz;\n\t//jobject {}Instance".format(item, item)
        class_code_template += f"""\n}};
        \n"""
        
        src_str += class_code_template

        src_str += "JavaVM *jvm;\nJNIEnv *jenv;\n"
        javainit_code_template = """jobject {interface_cap}Instance = nullptr;"""
        javainit_values = {
            "interface_cap": capitalize_first_letter(interface)
        }
        #src_str += javainit_code_template.format(**javainit_values)
        
        #for item in imports:
        #    src_str += "\njobject {}Instace = nullptr;".format(item)
        
        src_str += f"""\nJNIEXPORT jint JNICALL JNI_OnLoad(JavaVM* vm, void* reserved){{\n\tjvm = vm;\n\tif ((vm)->GetEnv((void**)&jenv, {jni_version}) != JNI_OK) {{\n\t\treturn JNI_ERR; //Failed to obtain JNIEnv\n\t}}\n\treturn {jni_version};\n}}"""


        start_code_template = f"""\n\tJNIEXPORT jlong JNICALL\n\tJava_{java_packages}{interface_cap}JNI_start(JNIEnv *env, jobject instance, jstring pinstance, jstring pconnection){{
        {interface_cap}Client* _{interface_cap}Client = new {interface_cap}Client();
        const char* char_instance = env->GetStringUTFChars(pinstance,nullptr);
		std::string _instance(char_instance);
        const char* char_connection = env->GetStringUTFChars(pconnection,nullptr);
		std::string _connection(char_connection);
        _{interface_cap}Client->main(_instance, _connection);
        _{interface_cap}Client->{interface_cap}Clazz = static_cast<jclass>(env->NewGlobalRef(env->FindClass("{java_class}{interface_cap}{interface_extension}")));
        _{interface_cap}Client->{interface_cap}Instance = nullptr;
        if(!(_{interface_cap}Client->myProxy->isAvailable())){{
            delete _{interface_cap}Client;
            _{interface_cap}Client = nullptr;
            return (jlong)0;
        }}
        else{{
            return reinterpret_cast<jlong>(_{interface_cap}Client);
        }}
    """
    #### 여기서부터 계속 작업해야 함. 우선 global variable을 최대한 줄이기 위한 테스트들. -> 전부 줄였음. 02.28
        for item in imports:
            start_code_template += f"""_{interface_cap}Client->{capitalize_first_letter(item)}Clazz = static_cast<jclass>(env->NewGlobalRef(env->FindClass("{java_class}{capitalize_first_letter(item)}{interface_extension}")));"""
        start_code_template += f"""}}\n"""


        main_code_template = f"""\n\nvoid {interface_cap}Client::main(std::string pinstance, std::string pconnection){{\n\tstd::shared_ptr<CommonAPI::Runtime> runtime = CommonAPI::Runtime::get();\n\t
    std::string domain = \"local\";\n\t//std::string instance = \"{package_name}.{interface_cap}\";\n\tstd::string instance = pinstance;\n\tstd::string connection = pconnection;
    myProxy = runtime->buildProxy<{interface_cap}Proxy>(domain, instance,connection);
    int8_t break_cnt = 0;
    while(!myProxy->isAvailable()){{
        std::this_thread::sleep_for(std::chrono::microseconds(10));
        if(break_cnt == 50){{
            break;
        }}
        break_cnt++;
    }}
}}
"""

        src_str += main_code_template

        # imports_set = set()
        # if(extends.get(interface)):
        #     for _import in imports.get(extends.get(interface)).split('\n'):
        #         if(_import):
        #             imports_set.add(_import)        
        # for _import in imports.get(interface).split('\n'):
        #     if(_import):
        #         imports_set.add(_import)
        # imports_set = list(imports_set)
        # for _import in imports_set:
        #     src_str += _import + "\n"
        #src_str += "\ninterface {} {{ \n".format(interface)
        #if(extends.get(interface)):
        #    src_str += interfaces.get(extends.get(interface))
        
        interface_extend_str = interface_str
        ## if interface extends 구현 측면에서 flattening 필요
        if(extends[interface] is not None):
            interface_extend_temp = interfaces[extends[interface]]
            word_to_replace = capitalize_first_letter(extends[interface])
            pattern = r'{}'.format(re.escape(word_to_replace))
            replacement_word = capitalize_first_letter(interface)
            interface_extend = re.sub(pattern, replacement_word, interface_extend_temp)
            interface_extend_str += interface_extend
        src_str += "extern \"C\"{"
        src_str += interface_extend_str
        src_str += start_code_template #.format(**start_values)
        src_str += "}\n"

        

        f = open("{}/src/{}Client.cpp".format(output_dir,interface), "w")
        f.write(src_str)
        f.close()

    #stub_str = ""
    
    for interface, stub_main_str in stub_main.items():
        stub_str = f"""package {jpackage_name};\n
import android.app.Service;
import android.content.Intent;
import android.os.IBinder;
import android.os.RemoteException;
import android.util.Log;
import java.util.ArrayList;
    
public class {capitalize_first_letter(interface)}Service extends Service{{
    public {capitalize_first_letter(interface)}Service(){{}}
    private {capitalize_first_letter(interface)}JNI myProxy;
    public static int timeout = 1000; // Needs to be changed
    public static int sender = 5555; // Needs to be changed
    public static String connection = ""; // Needs to be changed
    public static String instance = ""; // Needs to be changed
    private static final String TAG = "{capitalize_first_letter(interface)}Service";
    
    public boolean proxyGeneration(){{
        if(myProxy == null){{
            myProxy = new {capitalize_first_letter(interface)}JNI(this, instance, connection);
        }}
        if(myProxy.proxyptr == 0){{
            Log.d(TAG, "Proxy Connection Failed!");
            myProxy = null;
            return false;
        }}
        else{{
            Log.d(TAG, "Proxy Connection Succeeded!");
            return true;
        }}
    }}
    
    @Override
    public void onCreate(){{
        super.onCreate();
        myProxy = new {capitalize_first_letter(interface)}JNI(this, instance, connection);
        if(myProxy.proxyptr == 0){{
            Log.d(TAG, "Proxy Connection Failed!");
            myProxy = null;
        }}
        Log.d(TAG, "onCreate");
    }}
    @Override
    public IBinder onBind(Intent intent){{
        Log.d(TAG, "onBind");
        return binder;
    }}"""
        if(extends[interface] is not None):
            stub_main_extend_temp = stub_main[extends[interface]]
            word_to_replace = capitalize_first_letter(extends[interface])
            pattern = r'{}'.format(re.escape(word_to_replace))
            replacement_word = capitalize_first_letter(interface)
            #stub_main_extend_temp.replace(word_to_replace, replacement_word)
            stub_main_extend = re.sub(pattern, replacement_word, stub_main_extend_temp)
            stub_main_str += stub_main_extend
        stub_str += f"""
    private final {capitalize_first_letter(interface)}.Stub binder = new {capitalize_first_letter(interface)}.Stub(){{{stub_main_str}
    }};"""
        stub_handler_str = stub_handler[interface]
        if(extends[interface] is not None):
            stub_handler_extend_temp = stub_handler[extends[interface]]
            word_to_replace = capitalize_first_letter(extends[interface])
            pattern = r'{}'.format(re.escape(word_to_replace))
            replacement_word = capitalize_first_letter(interface)
            stub_handler_extend = re.sub(pattern,replacement_word,stub_handler_extend_temp)
            stub_handler_str += stub_handler_extend
        stub_str += stub_handler_str
        stub_str += f"""
}}"""
        f = open("{}/stub/{}.java".format(output_dir,capitalize_first_letter(interface)+"Service"), "w")
        f.write(stub_str)
        f.close()
        
        # f = open("outputs/stub/{}.java".format(capitalize_first_letter(interface)+"Service"), "w")
        # f.write(stub_str)
        # f.close()


    for interface, interface_str in jnis.items():
        jni_str = "package {};\n\n".format(jpackage_name)
        if(extends[interface] is not None):
            jni_str += "public class {}JNI extends {}JNI{{\n".format(capitalize_first_letter(interface), capitalize_first_letter(extends[interface]))
        else:
            jni_str += "public class {}JNI {{\n".format(capitalize_first_letter(interface))
        jni_str += "\n\tstatic {{\n\t\tSystem.loadLibrary(\"{}-Client\");\n\t}}\n\n".format(interface)
        jni_str += "\tpublic long proxyptr;\n\tpublic native long start(String instance, String connection);\n"
        jni_str += "\tprivate {}Service service;\n".format(capitalize_first_letter(interface))
        jni_str += interface_str
        jni_str += "\n\t{}JNI({}Service service, String instance, String connection){{\n\t\tthis.proxyptr = start(instance, connection);\n\t\tthis.service = service;\n\t}}\n".format(interface,interface)
        jni_str += "\n}"
        f = open("{}/src/{}.java".format(output_dir,interface+"JNI"), "w")
        f.write(jni_str)
        f.close()

    for typecollection, typecollection_str in jni_typecollection.items():
        jni_str = ""
        jni_str += typecollection_str
        f = open("{}/src/{}.java".format(output_dir, typecollection+"JNI"), "w")
        f.write(jni_str)
        f.close()

######################################### Argument parser ####################################################################

def parse_command_line():
    parser = argparse.ArgumentParser(
        description="Behavioral cloning model trainer.")
    parser.add_argument(
        "-C", "--CLI",dest="cli", action="store_true", help="Use this option to run the tool as CLI"
    )
    parser.add_argument(
        "-V", "--jni_version", dest="jniversion", action="store", help="Version of the JNI.", required=False
    )
    parser.add_argument(
        "-J", "--packagejava", dest="packagejava", action = "store", help="Package name of Java", required=False
    )
    parser.add_argument(
        "-O", "--output", dest="output_dir", action="store", help="Output directory.", required=False, default='outputs'
    )
    # parser.add_argument(
    #     "fidl", nargs="+",
    #     help="Input FIDL file.")
    
    if not parser.parse_known_args()[0].cli:
        parser.add_argument(
            "fidl", nargs="*", help="Input FIDL file."
        )
    else:
        parser.add_argument(
            "fidl", nargs="+", help="Input FIDL file."
        )
    
    parser.add_argument(
        "-I", "--import", dest="import_dirs", metavar="import_dir",
        action="append", help="Model import directories.")
    
    args = parser.parse_args()
    
    if args.cli and not args.jniversion :
        parser.error("--jni_version is required if -C or --CLI is given")
    if args.cli and not args.packagejava :
        parser.error("--packagejava is required if -C or --CLI is given")
        
    return args
    
############################################ Main ####################################################################################    
    
def main(args, option=2):
    
    # If for CLI
    processor = Processor()
    if args.import_dirs:
        processor.package_paths.extend(args.import_dirs)
    for fidl in args.fidl:
        try:
            processor.import_file(fidl)
        except (LexerException, ParserException, ProcessorException) as e:
            print("ERROR: {}".format(e))
            continue
        
    dump_packages(processor.packages)
    jni_list = ['JNI_VERSION_1_1','JNI_VERSION_1_2','JNI_VERSION_1_4','JNI_VERSION_1_6','JNI_VERSION_1_8','JNI_VERSION_9','JNI_VERSION_10','JNI_VERSION_19','JNI_VERSION_20','JNI_VERSION_21']

    jni_version = args.jniversion
    if jni_version not in jni_list:
        print("ERROR: There is no matching JNI version!")
        return 0
    if(option == 0):
        convert_to_aidl(processor.packages, args.packagejava, args.output_dir)
    elif(option == 1):
        convert_to_src_client(processor.packages, jni_version, args.packagejava, args.output_dir)
    elif(option == 2):
        convert_to_aidl(processor.packages, args.packagejava, args.output_dir)
        convert_to_src_client(processor.packages, jni_version, args.packagejava, args.output_dir)
    

if __name__ == "__main__":
    args = parse_command_line()
    args.jniversion = "JNI_VERSION_"+args.jniversion
    main(args)
