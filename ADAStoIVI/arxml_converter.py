#!/usr/bin/env python
################################################################
#          ARXML to Franca IDL and Franca Deployment           #
################################################################

import argparse, os, sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
import re # for string transformation

# First letter changing functions
def capitalize_first_letter(input_string):
    return input_string[0].upper() + input_string[1:]

def lower_first_letter(input_string):
    return input_string[0].lower() + input_string[1:]

# Primitive types and Stirng
general_type = ["UInt8", "UInt16", "UInt32", "UInt64", "Int8", "Int16", "Int32", "Int64", "Boolean", "Float", "Double", "String"]

# Reserved names that cannot be used as a name of an element
reserved_names = ["info", "version", "interface", "struct", "enum", "const", "array", "map", "broadcast", "method", "attribute", "throws"]

def name_validation(name):
    if name in reserved_names:
        return name+"_"
    else:
        return name

# Type conversion from ARXML to FIDL, FDEPL
def convert_fidl_type(typename):
    if(typename == "uint8_t"):
        return "UInt8"
    elif(typename == "int8_t"):
        return "Int8"
    elif(typename == "uint16_t"):
        return "UInt16"
    elif(typename == "int16_t"):
        return "Int16"
    elif(typename == "uint32_t"):
        return "UInt32"
    elif(typename == "int32_t"):
        return "Int32"
    elif(typename == "uint64_t"):
        return "UInt64"
    elif(typename == "int64_t"):
        return "Int64"
    elif(typename == "bool"):
        return "Boolean"
    elif(typename == "float"):
        return "Float"
    elif(typename == "double"):
        return "Double"
    elif(typename == "String"):
        return "String"
    else:
        return typename

# Array, Enumeration, and Struct Class
# <CATEGORY> VECTOR </CATEGORY>
class Array:
    def __init__(self,root, imports):
        self.name = None
        self.type = None
        self.imports = imports
        self.minLength = "0"
        self.maxLength = "0"
        self.lenWidth = "4"
        self.__get_name__(root)
        self.__get_type__(root)
        
    def __get_name__(self,root):
        name_node = find_first_root(root, "SHORT-NAME")
        if name_node:
            self.name = name_validation(name_node.text)
            
    def __get_type__(self,root):
        type_node = find_roots_of_tag(root, "TEMPLATE-TYPE-REF")
        if type_node:
            self.type = convert_fidl_type(type_node[0].text.split('/')[-1])
            if self.type not in general_type and self.type not in self.imports:
                # print("Array append " + self.type)
                self.imports.append(self.type)

# <COMPU-METHOD>
class Enumeration:
    def __init__(self,root, datatype):
        self.name = None
        self.enumerators = []
        self.backingtype = None
        self.__get_name__(root, datatype)
        self.__get_enumerators__(root)
        
    
    def __get_name__(self,root, datatype):
        name_node = find_first_root(root, "SHORT-NAME")
        if name_node:
            self.name = name_validation(name_node.text)
        backingtype = find_first_root(datatype, "TYPE-REFERENCE-REF")
        if backingtype:
            self.backingtype = convert_fidl_type(backingtype.text.split('/')[-1])
            
    def __get_enumerators__(self, root):
        enumerators = find_roots_of_tag(root, "COMPU-SCALE")
        if enumerators:
            for enumerator in enumerators:
                enum_name = find_first_root(enumerator, "VT")
                enum_value = find_first_root(enumerator, "UPPER-LIMIT")
                if enum_value:
                    if "0x" in enum_value.text:
                        self.enumerators.append((name_validation(enum_name.text), str(int(enum_value.text, 16))))
                    else:
                        self.enumerators.append((name_validation(enum_name.text), enum_value.text))
                else:
                    self.enumerators.append((name_validation(enum_name.text), None))
                
        

# <CATEGORY> STRUCTURE </CATEGORY>
class Struct:
    def __init__(self,root, imports):
        self.name = None
        self.elements = []
        self.lenWidth = "0"
        self.imports = imports
        self.__get_name__(root)
        self.__get_elements__(root)
    
    def __get_name__(self,root):
        name_node = find_first_root(root, "SHORT-NAME")
        if name_node:
            self.name = name_validation(name_node.text)
    
    def __get_elements__(self,root):
        elements = find_roots_of_tag(root, "CPP-IMPLEMENTATION-DATA-TYPE-ELEMENT")
        if elements:
            for element in elements:
                element_name = find_first_root(element, "SHORT-NAME")
                element_type = find_first_root(element, "TYPE-REFERENCE-REF")
                self.elements.append((name_validation(element_name.text), convert_fidl_type(element_type.text.split('/')[-1])))
                if convert_fidl_type(element_type.text.split('/')[-1]) not in general_type and convert_fidl_type(element_type.text.split('/')[-1]) not in self.imports:
                    self.imports.append(convert_fidl_type(element_type.text.split('/')[-1]))

# <CATEGORY> ASSOCIATIVE_MAP </CATEGORY>
class Map:
    def __init__(self, root, imports):
        self.name = None
        self.key_type = None
        self.value_type = None
        self.imports = imports
        self.__get_name__(root)
        self.__get_types__(root)
    
    def __get_name__(self, root):
        name_node = find_first_root(root, "SHORT-NAME")
        if name_node:
            self.name = name_validation(name_node.text)
    
    def __get_types__(self, root):
        types = find_roots_of_tag(root, "TEMPLATE-TYPE-REF")
        if types and len(types) == 2:
            self.key_type = convert_fidl_type(types[0].text.split('/')[-1])
            if convert_fidl_type(types[0].text.split('/')[-1]) not in general_type and convert_fidl_type(types[0].text.split('/')[-1]) not in self.imports:
                self.imports.append(convert_fidl_type(types[0].text.split('/')[-1]))
            self.value_type = convert_fidl_type(types[1].text.split('/')[-1])
            if convert_fidl_type(types[1].text.split('/')[-1]) not in general_type and convert_fidl_type(types[1].text.split('/')[-1]) not in self.imports:
                self.imports.append(convert_fidl_type(types[1].text.split('/')[-1]))
        
                

# FIDL, FDEPL Broadcast Class
class Event:
    def __init__(self, root, imports):
        self.name = None    
        self.arg_name = None 
        self.type = None
        # argument에 대한 특정 있을 시 적용 필요
        # FDEPL from below
        self.eventId = None
        self.imports = imports
        self.reliable = "false"
        # self.priority : Non-AUTOSAR
        self.multicast = "false"
        self.eventgroups = []
        self.endianess = "be"
        self.crcWidth = "zero"
        self.__get_name__(root)
        self.__get_type__(root, imports)
        
    def __get_name__(self,root):
        name_node = find_first_root(root, "SHORT-NAME")
        if name_node:
            self.name = name_node.text
            
    # def __get_arg_name__(self,root):
    #     arg_node = find_roots_of_tag(root, "")
            
    def __get_type__(self,root,imports):
        type_node = find_roots_of_tag(root, "TYPE-TREF")
        if type_node:
            self.type = convert_fidl_type(type_node[0].text.split('/')[-1])
            if(self.type not in general_type and self.type not in self.imports):
                self.imports.append(self.type)
            
# FIDL, FDEPL Method class
class Method:
    def __init__(self,root, imports):
        self.name = None
        self.in_args = []
        self.out_args = []
        #
        self.imports = imports
        self.fire_and_forget = "false"
        # FDEPL from below
        self.methodId = None
        self.reliable = None # optional
        # self.priority : Non-AUTOSAR
        # self.errorCoding : Non-AUTOSAR
        self.endianess = "be"
        self.crcWidth = "zero"
        
        self.__get_name__(root)
        self.__get_arguments__(root, imports)
        self.__get_flag__(root)
        
    def __get_name__(self,root):
        name_node = find_first_root(root, "SHORT-NAME")
        if name_node:
            self.name = name_node.text
            
    def __get_arguments__(self,root, imports):
        argument_node = find_roots_of_tag(root, "ARGUMENT-DATA-PROTOTYPE")
        if argument_node:
            for argument in argument_node:
                name, type = get_name_and_type(argument)
                if (__get_direction__(argument) == "OUT"):
                    self.out_args.append((name_validation(name), type))
                    if(type not in general_type and type not in self.imports):
                        self.imports.append(type)
                elif (__get_direction__(argument) == "IN"):
                    self.in_args.append((name_validation(name), type))
                    if(type not in general_type and type not in self.imports):
                        self.imports.append(type)
                    
    def __get_flag__(self,root):
        flag_node = find_first_root(root, "FIRE-AND-FORGET")
        if flag_node:
            self.fire_and_forget = flag_node.text
        else:
            self.fire_and_forget = "false"
                                        
def get_name_and_type(node):
    name_node = find_first_root(node, "SHORT-NAME")
    if name_node:
        name = name_node.text
            
    type_node = find_roots_of_tag(node, "TYPE-TREF")
    if type_node:
        type = convert_fidl_type(type_node[0].text.split('/')[-1])
        
    return name, type

def __get_direction__(node):
    direction_node = find_first_root(node, "DIRECTION")
    if direction_node:
        return direction_node.text
    else:
        return "IN"
    

# FIDL, FDEPL Attribute class
class Field:
    def __init__(self, root, imports):
        self.name = None
        self.type = None
        # FDEPL from below
        # [HAS-* T/F, ID, TCP/UDP (reliable)]
        self.getter = OrderedDict()
        self.setter = OrderedDict()
        self.notifier = OrderedDict()
        # 
        self.imports = imports
        self.notifierMulticast = "false"
        self.eventgroups = []
        self.endianess = "be"
        self.crcWidth = "zero"
        self.__get_name__(root)
        self.__get_type__(root, imports)
        self.__has_getter__(root)
        self.__has_setter__(root)
        self.__has_notifier__(root)
        
    def __get_name__(self,root):
        name_node = find_roots_of_tag(root, "SHORT-NAME")
        if name_node:
            self.name = name_validation(name_node[0].text)
    
    def __get_type__(self,root, imports):
        type_node = find_roots_of_tag(root, "TYPE-TREF")
        if type_node:
            self.type = convert_fidl_type(type_node[0].text.split('/')[-1])
        if self.type not in general_type and self.type not in self.imports:
            # print(self.type)
            self.imports.append(self.type)
    
    # ID update needed, update done when instance parsing in interface class
    def __has_getter__(self,root):
        getter_node = find_roots_of_tag(root, "HAS-GETTER")
        if getter_node:
            # self.getter(getter_node[0].text)
            # self.getter[0] = (getter_node[0].text)
            self.getter["has_getter"] = getter_node[0].text
    
    def __has_setter__(self,root):
        setter_node = find_roots_of_tag(root, "HAS-SETTER")
        if setter_node:
            # self.setter.append(setter_node[0].text)
            # self.setter[0] = (setter_node[0].text)
            self.setter["has_setter"] = setter_node[0].text
    
    def __has_notifier__(self,root):
        notifier_node = find_roots_of_tag(root, "HAS-NOTIFIER")
        if notifier_node:
            # self.notifier.append(notifier_node[0].text)
            # self.notifier = (notifier_node[0].text)
            self.notifier["has_notifier"] = notifier_node[0].text

# FDEPL Instance class
class Instance:
    def __init__(self, root, init_root):
        self.name = None
        self.instanceId = None
        self.unicast = None # String, default: ""
        self.reliablePort = 0 # Integer, default: 0
        self.unreliablePort = 0 # Integer, default: 0
        self.multiEventgroups = [] # Integer[], optional
        self.multiAddress = [] # String[], optional
        self.multiPorts = [] # Integer[], optional
        self.multiThreshols = [] # Integer[], optional
        self.__get_name__(root)
        self.__get_instanceId__(root)
        self.__get_ports__(init_root)
        
    def __get_name__(self,root):
        name_node = find_first_root(root, "SHORT-NAME")
        if name_node:
            self.name = name_node.text
        else: # Raise error
            raise Exception("No SHORT-NAME in Instance")
            
    def __get_instanceId__(self, root):
        id_node = find_first_root(root, "SERVICE-INSTANCE-ID")
        if id_node:
            self.instanceId = id_node.text
        else: # Raise error
            raise Exception("No SERVICE-INSTANCE-ID in Instance")
            
    def __get_ports__(self, root):
        networks = find_roots_of_tag(root, "SOMEIP-SERVICE-INSTANCE-TO-MACHINE-MAPPING")
        if networks:
            for network in networks:
                instance_refs = find_roots_of_tag(network, "SERVICE-INSTANCE-REF")
                if instance_refs:
                    for instance_ref in instance_refs:
                        if self.name in instance_ref.text:
                            udp_node = find_first_root(network, "UDP-PORT")
                            tcp_node = find_first_root(network, "TCP-PORT")
                            if udp_node:
                                self.unreliablePort = udp_node.text
                            if tcp_node:
                                self.reliablePort = tcp_node.text
        

# FIDL & FDEPL Interface class
class Interface:
    def __init__(self, root, init_root, package=[]):
        self.name = None
        self.versions = ["N/A", "N/A"] # major = versions[0], minor = versions[1]
        self.packages = package
        self.fields = []
        self.events = []
        self.methods = []
        self.arrays= []
        self.enumerations = []
        self.structs = []
        self.maps = []
        self.serviceId = None
        self.instances = []
        self.imports = [] # for methods, fields, events that use data types that are not primitives
        self.references = [] # for data types that reference other data types
        self.strings = []
        self.__get_name__(root)
        print(f"Parsing {self.name}")
        #self.__get_versions__(root)
        self.__get_package__(root)
        self.__get_fields__(root)
        self.__get_events__(root)
        self.__get_methods__(root)
        self.__get_datatype__(init_root)
        while not (all(element in self.imports for element in self.references)):
            self.__get_reference__(init_root)
        
        self.__get_fdepl_interface__(init_root)
        self.__get_fdepl_instance__(init_root)
    
    # Interface name
    def __get_name__(self,root):
        name_node = find_first_root(root, "SHORT-NAME")
        if name_node:
            self.name = name_node.text
        else: # Raise error
            raise Exception("No SHORT-NAME in Interface")
        
    # Version information is in the FDEPL tree, not in use.
    def __get_versions__(self,root):
        major_node = find_first_root(root, "MAJOR-VERSION")
        if major_node:
            self.versions.append(major_node.text)
        else:
            self.versions.append("1")
        minor_node = find_first_root(root, "MINOR-VERSION")
        if minor_node:
            self.versions.append(minor_node.text)
        else:
            self.versions.append("0")
    
    # Interface package from ARXML file, it can be given through command line input
    def __get_package__(self,root):
        package_node = find_roots_of_tag(root, "SYMBOL-PROPS")
        if package_node and (self.packages == []):
            for package in package_node:
                name_node = find_first_root(package, "SHORT-NAME") # or SYMBOL
                self.packages.append(name_node.text)
    
    # Fields
    def __get_fields__(self,root):
        fields = find_roots_of_tag(root, "FIELD")
        for field in fields:
            self.fields.append(Field(field, self.imports))
    
    # Events
    def __get_events__(self,root):
        events = find_roots_of_tag(root, "VARIABLE-DATA-PROTOTYPE")
        for event in events:
            self.events.append(Event(event, self.imports))
    
    # Methods
    def __get_methods__(self,root):
        methods = find_roots_of_tag(root, "CLIENT-SERVER-OPERATION")
        for method in methods:
            self.methods.append(Method(method, self.imports))
    
    # Field, Event, Method에서 쓰이는 Data type들, Data type이 complex type이라면 추가적인 조치가 필요함.
    def __get_datatype__(self,init_root):
        datatypes = find_roots_of_tag(init_root, "STD-CPP-IMPLEMENTATION-DATA-TYPE")
        if datatypes:
            for datatype in datatypes:
                data_check = find_first_root(datatype, "CATEGORY")
                data_name = find_first_root(datatype, "SHORT-NAME")
                data_package = find_roots_of_tag(datatype, "SYMBOL")
                package_name = []
                if data_package:
                    for package in data_package:
                        package_name.append(package.text)
                if data_check and data_name.text in self.imports:
                    # print(data_name.text)
                    if data_check.text == "STRUCTURE":
                        self.structs.append(Struct(datatype, self.references))
                    # SOME/IP에서는 ARRAY와 VECTOR가 구분되나 vsomeip에서는 아님
                    elif data_check.text == "VECTOR" or data_check.text == "ARRAY":  
                        self.arrays.append(Array(datatype, self.references))
                    elif data_check.text == "TYPE_REFERENCE":
                        enum_nodes = find_roots_of_tag(init_root, "COMPU-METHOD")
                        if enum_nodes:
                            for enum_node in enum_nodes:
                                name_check = find_first_root(enum_node, "SHORT-NAME")
                                if name_check.text == data_name.text:
                                    self.enumerations.append(Enumeration(enum_node, datatype))
                                    break
                    elif data_check.text == "STRING":
                        self.strings.append(data_name.text)
                    elif data_check.text == "ASSOCIATIVE_MAP":
                        self.maps.append(Map(datatype, self.references))
                        #raise Exception("{}: Maps are not supported".format(self.name))
    
    # Array 또는 Struct가 primitive type 이외의 type을 참조하는 경우를 해결하기 위함.
    def __get_reference__(self,init_root):
        datatypes = find_roots_of_tag(init_root, "STD-CPP-IMPLEMENTATION-DATA-TYPE")
        #print(self.references)
        # print(self.imports)
        if datatypes:
            for datatype in datatypes:
                data_check = find_first_root(datatype, "CATEGORY")
                data_name = find_first_root(datatype, "SHORT-NAME")
                if data_check and (data_name.text in self.references) and (data_name.text not in self.imports):
                    # print(data_name.text, data_check.text)
                    if data_check.text == "STRUCTURE":
                        self.structs.append(Struct(datatype, self.references))
                        self.imports.append(data_name.text)
                    # SOME/IP에서는 ARRAY와 VECTOR가 구분되나 vsomeip에서는 아님
                    elif data_check.text == "VECTOR" or data_check.text == "ARRAY":  
                        self.arrays.append(Array(datatype, self.references))
                        self.imports.append(data_name.text)
                    elif data_check.text == "TYPE_REFERENCE":
                        enum_nodes = find_roots_of_tag(init_root, "COMPU-METHOD")
                        self.imports.append(data_name.text)
                        if enum_nodes:
                            # print("EEEE")
                            # print(data_name.text)
                            for enum_node in enum_nodes:
                                name_check = find_first_root(enum_node, "SHORT-NAME")
                                if name_check.text == data_name.text:
                                    self.enumerations.append(Enumeration(enum_node, datatype))
                                    break
                    elif data_check.text == "STRING":
                        self.strings.append(data_name.text)
                        self.references.remove(data_name.text)
                    elif data_check.text == "ASSOCIATIVE_MAP":
                        self.maps.append(Map(datatype, self.references))
                        #raise Exception("{}: Maps are not supported".format(self.name))
    
    # Interface for a FDEPL file
    def __get_fdepl_interface__(self,init_root):
        interfaces = find_root_named(init_root, "SOMEIP-SERVICE-INTERFACE-DEPLOYMENT", self.name)
        # There must be only one element in interfaces, if not exception is raised
        if interfaces:
            for instance in interfaces:
                major_node = find_first_root(instance, "MAJOR-VERSION")
                if major_node:
                    self.versions[0] = major_node.text
                else:
                    raise Exception("Major Version Not Specified")
                minor_node = find_first_root(instance, "MINOR-VERSION")
                if minor_node:
                    #self.versions.append(minor_node.text)
                    self.versions[1] = minor_node.text
                else:
                    raise Exception("Minor Version Not Specified")
                id_node = find_first_root(instance, "SERVICE-INTERFACE-ID")
                if id_node:
                    self.serviceId = id_node.text
                ##### ID 와 Reliable 뽑아내서 Name에 맞게 저장하는 것 필요~
                # FIELDS
                if self.fields:
                    for field in self.fields:
                        field_instance = find_root_named(instance, "SOMEIP-FIELD-DEPLOYMENT", field.name)
                        if field_instance:
                            field_get = find_first_root(field_instance[0], "GET")
                            if field_get:
                                field_get_id = find_first_root(field_get, "METHOD-ID")
                                field_get_protocol = find_first_root(field_get, "TRANSPORT-PROTOCOL")
                                if field_get_id:
                                    # field.getter.append(field_get_id.text)
                                    # field.getter[1] = (field_get_id.text)
                                    field.getter["id"] = field_get_id.text
                                else:
                                    raise Exception("{}: No Getter Id Specified")
                                if field_get_protocol:
                                    if field_get_protocol.text == "UDP":
                                        # field.getter.append("false")
                                        # field.getter[2] = "false"
                                        field.getter["protocol"] = "false"
                                    else:
                                        # field.getter.append("true")
                                        # field.getter[2] = "true"
                                        field.getter["protocol"] = "true"
                                else:
                                    # field.getter.append("false")
                                    # field.getter[2] = "false"
                                    field.getter["protocol"] = "false"
                                    # raise Exception("{}: No Getter Id Specified")
                            elif field.getter["has_getter"] == "true" and not field_get:
                                raise Exception("{} - {}: Has Getter But No Getter Id".format(self.name, field.name))
                            field_set = find_first_root(field_instance[0], "SET")
                            if field_set:
                                field_set_id = find_first_root(field_set, "METHOD-ID")
                                field_set_protocol = find_first_root(field_set, "TRANSPORT-PROTOCOL")
                                if field_set_id:
                                    # field.setter.append(field_set_id.text)
                                    # field.setter[1] = field_set_id.text
                                    field.setter["id"] = field_set_id.text
                                else:
                                    raise Exception("{} - {}: No Setter Id Specified".format(self.name, field.name))
                                if field_set_protocol:
                                    if field_set_protocol.text == "UDP":
                                        # field.setter.append("false")
                                        # field.setter[2] = "false"
                                        field.setter["protocol"] = "false"
                                    else:
                                        # field.setter.append("true")
                                        # field.setter[2] = "true"
                                        field.setter["protocol"] = "true"
                                else:
                                    # field.setter.append("false")
                                    field.setter["protocol"] = "false"
                                    # raise Exception("{} - {}: No Setter Id Specified".format(self.name, field.name))
                            elif field.setter["has_setter"] == "true" and not field_set:
                                raise Exception("{} - {}: Has Setter But No Setter Id".format(self.name, field.name))
                            field_notifier = find_first_root(field_instance[0], "NOTIFIER")
                            if field_notifier:
                                field_notifier_id = find_first_root(field_notifier, "EVENT-ID")
                                field_notifier_protocol = find_first_root(field_notifier, "TRANSPORT-PROTOCOL")
                                # event_groups = find_root_named(find_first_root(instance,"EVENT-GROUPS"), "SOMEIP-EVENT-GROUP", "Eventgroup_Notification_"+field.name)
                                event_groups = find_roots_of_tag(instance, "SOMEIP-EVENT-GROUP")
                                if field_notifier_id:
                                    ### Event id는 ARXML에서의 id에 0x8000을 더한 값임
                                    # field.notifier.append(str(int(field_notifier_id.text) + 32768))
                                    # field.notifier[1] = str(int(field_notifier_id.text) + 32768)
                                    field.notifier["id"] = str(int(field_notifier_id.text) + 32768)
                                else:
                                    raise Exception("{} - {}: No Notifier Id Specified".format(self.name, field.name))
                                if field_notifier_protocol:
                                    if field_notifier_protocol.text == "UDP":
                                        # field.notifier.append("false")
                                        # field.notifier[2] = "false"
                                        field.notifier["protocol"] = "false"
                                    else:
                                        # field.notifier.append("true")
                                        # field.notifier[2] = "true"
                                        field.notifier["protocol"] = "true"
                                else:
                                    # field.notifier.append("false")
                                    # raise Exception("{} - {}: No Notifier Id Specified".format(self.name, field.name))
                                    field.notifier["protocol"] = "false"
                                    
                                ### Event groups
                                if event_groups:
                                    for event_group in event_groups:
                                        event_groupIds = find_roots_of_tag(event_group, "EVENT-REF")
                                        if event_groupIds:       
                                            for event_groupId in event_groupIds:
                                                if field.name in event_groupId.text:
                                                    event_id = find_first_root(event_group, "EVENT-GROUP-ID")
                                                    if event_id:
                                                        field.eventgroups.append(event_id.text)
                            elif field.notifier["has_notifier"] == "true" and not field_notifier:
                                raise Exception("{} - {}: Has Notifier But No Notifier Id".format(self.name, field.name))
                            #print(field.getter, field.setter, field.notifier)
                # EVENTS
                if self.events:
                    for event in self.events:
                        event_instance = find_root_named(instance, "SOMEIP-EVENT-DEPLOYMENT", event.name)
                        if event_instance:
                            event_id = find_first_root(event_instance[0], "EVENT-ID")
                            event_protocol = find_first_root(event_instance[0], "TRANSPORT-PROTOCOL")
                            # event_groups = find_root_named(find_first_root(instance,"EVENT-GROUPS"), "SOMEIP-EVENT-GROUP", "Eventgroup_"+event.name)
                            event_groups = find_roots_of_tag(instance, "SOMEIP-EVENT-GROUP")
                            if event_id:
                                ### Event id는 ARXML에서의 id에 0x8000을 더한 값임
                                event.eventId = str(int(event_id.text) + 32768)
                            ## If not raise error
                            if event_protocol:
                                if event_protocol.text == "UDP":
                                    event.reliable = "false"
                                else:
                                    event.reliable = "true"
                            else:
                                event.reliable = "false"
                            if event_groups:
                                    for event_group in event_groups:
                                        event_groupIds = find_roots_of_tag(event_group, "EVENT-REF")
                                        if event_groupIds:       
                                            for event_groupId in event_groupIds:
                                                if event.name in event_groupId.text:
                                                    event_id = find_first_root(event_group, "EVENT-GROUP-ID")
                                                    if event_id:
                                                        event.eventgroups.append(event_id.text)
                # METHODS
                if self.methods:
                    for method in self.methods:
                        method_instance = find_root_named(instance, "SOMEIP-METHOD-DEPLOYMENT", method.name)
                        # method instance를 이상하게 정의해놓은 파일들이 있음. SHORT-NAME에 method명 말고 다른 이름 적혀 있는 경우
                        if method_instance:
                            method_id = find_first_root(method_instance[0], "METHOD-ID")
                            method_protocol = find_first_root(method_instance[0], "TRANSPORT-PROTOCOL")
                            if method_id:
                                method.methodId = method_id.text
                            ## If not raise error
                            if method_protocol:
                                if method_protocol.text == "UDP":
                                    method.reliable = "false"
                                else:
                                    method.reliable = "true"
                            else:
                                method.reliable = None
                        else:
                            method_instance = find_root_method(instance, "SOMEIP-METHOD-DEPLOYMENT", method.name)
                            if method_instance:
                                method_id = find_first_root(method_instance[0], "METHOD-ID")
                                method_protocol = find_first_root(method_instance[0], "TRANSPORT-PROTOCOL")
                                if method_id:
                                    method.methodId = method_id.text
                                ## If not raise error
                                if method_protocol:
                                    if method_protocol.text == "UDP":
                                        method.reliable = "false"
                                    else:
                                        method.reliable = "true"
                                else:
                                    method.reliable = None
                            else:
                                raise Exception("{}-{}: No method ID Specified".format(self.name, method.name))
                                
        else:
            raise Exception("{}: No matching instance".format(self.name))
    # Instances for a FDEPL file
    def __get_fdepl_instance__(self, init_root):
        # naming 규칙 정해지지 않았기에 SHORT-NAME으로 정확하게 찾을 수는 없고 포함하는 것들을 전부 찾는 방식
        instances = find_root_contains_name(init_root, "PROVIDED-SOMEIP-SERVICE-INSTANCE", self.name)
        if instances:
            for instance in instances:
                self.instances.append(Instance(instance, init_root))
                            
                        
                
            
        
# ARXML into a parse tree
class TreeNode: 
    def __init__(self, tag, text=None):
        self.tag = tag
        self.text = text
        self.children = []

def parse_arxml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()

    def parse_element(element):
        node = TreeNode(element.tag.split("}")[-1], element.text.strip() if element.text else None)
        for child in element:
            child_node = parse_element(child)
            if child_node:
                node.children.append(child_node)
        return node

    tree_root = parse_element(root)
    return tree_root

# Printing parsed tree
def print_tree(node, indent=0):
    print("  " * indent + node.tag + (": " + node.text if node.text else ""))
    for child in node.children:
        print_tree(child, indent + 1)

# Printing a tree from a specific position
def print_specific_tree(node, tag, indent = 0):
    for child in node.children:
        print(child.children)
        if(node.tag == tag):
            print("  " * indent + node.tag + (": " + node.text if node.text else ""))
            for child in node.children:
                print_tree(child, indent + 1)
        else:
            print_specific_tree(child, tag, indent)

# Finds the first node under root with the target_tag
def find_first_root(node, target_tag):
    if node.tag == target_tag:
        return node

    for child in node.children:
        result = find_first_root(child, target_tag)
        if result:
            return result

    return None

# Finds all the nodes under root with the target_tag
def find_roots_of_tag(node, target_tag):
    roots = []

    if node.tag == target_tag:
        roots.append(node)

    for child in node.children:
        results = find_roots_of_tag(child, target_tag)
        if results:
            roots.extend(results)

    return roots

# Find a node named as interface_name under root with the target_tag 
def find_root_named(node, target_tag, interface_name):
    roots = []
    nodes = []
    
    roots = find_roots_of_tag(node, target_tag)
            
    for root in roots:
        name = find_first_root(root, "SHORT-NAME")
        if(name.text == interface_name):
            nodes.append(root)
            
    return nodes

# Find a node named as interface_name under root with the target_tag and target_text
def find_root_tagged_named(node, target_tag, target_text, interface_name):
    roots = []
    nodes = []
    
    roots = find_roots_of_tag(node, target_tag)
            
    for root in roots:
        names = find_roots_of_tag(root, target_text)
        if names:
            for name in names:
                if(name.text == interface_name):
                    nodes.append(root)
            
    return nodes

# Find a node with a name that contains the interface_name, for instance node finding 
def find_root_contains_name(node, target_tag, interface_name):
    roots = []
    nodes = []
    
    roots = find_roots_of_tag(node, target_tag)
            
    for root in roots:
        name = find_first_root(root, "SERVICE-INTERFACE-DEPLOYMENT-REF")
        if(interface_name in name.text):
            nodes.append(root)
            
    return nodes

# Find a node wiht a METHOD-REF that contains the interface_name
# For finding method node with different SHORT-NAME
def find_root_method(node, target_tag, interface_name):
    roots = []
    nodes = []
    
    roots = find_roots_of_tag(node, target_tag)
            
    for root in roots:
        name = find_first_root(root, "METHOD-REF")
        if(name.text.split('/')[-1] == interface_name):
            nodes.append(root)
            
    return nodes

# Print an Interface
def dump_interface(interface):
    print(interface.name, interface.packages, interface.versions)
    if interface.fields:
        for field in interface.fields:
            print(field.name, field.type, field.getter, field.setter, field.notifier)
    if interface.events:
        for event in interface.events:
            print(event.name, event.type, event.eventId, event.reliable)
    if interface.methods:
        for method in interface.methods:
            print(method.name)
            for in_args in method.in_args:
                print(" " + in_args[0], in_args[1])
            for out_args in method.out_args:
                print(" " + out_args[0], out_args[1])
            print(method.methodId, method.reliable)

# String data type name transformation
def string_transformation(fidl_str, strings):
    if not strings:
        return fidl_str
    
    pattern = re.compile(r'\b('+'|'.join(re.escape(word) for word in strings) + r')\b')
    modified_str = pattern.sub("String", fidl_str)
    
    return modified_str
    

# FIDL generation
def generate_fidl_from_arxml(interface):
    ## Package, name, and version of the interface
    ### Package는 현재 ARXML에 있는 것 사용하도록 되어 있으나 바뀔 수 있음
    packages = ""
    packages += interface.packages[0]
    if len(interface.packages) > 1:
        for package in interface.packages[1:]:
            packages += "."+package
    ## FIDL string
    fidl_str = f"""package {packages}\n
interface {interface.name} {{
    version {{ major {interface.versions[0]} minor {interface.versions[1]} }}
    """
    
    ## Attributes in the interface
    if(interface.fields):
        fidl_str += f"""
    """
        for field in interface.fields:
            if field.setter["has_setter"] != "false":
                fidl_str += f"""attribute {field.type} {field.name}
    """
            else:
                fidl_str += f"""attribute {field.type} {field.name} readonly
    """
    ## Broadcasts in the interface
    if(interface.events):
        fidl_str += f"""
    """
        for event in interface.events:
            fidl_str += f"""broadcast {event.name} {{
        out {{
            {(event.type)} {lower_first_letter(event.name)}
        }}            
    }}
    """
    ## Methods in the interface
    if(interface.methods):
        fidl_str += f"""
    """
        for method in interface.methods:
            method_flag = ""
            if method.fire_and_forget == "true":
                method_flag = " fireAndForget"
            method_in = ""
            method_out = ""
            
            if method.in_args:
                method_in += "in {"
                for in_arg in method.in_args:
                    method_in += "\n\t\t\t{} {}".format(in_arg[1], in_arg[0])
                method_in += "\n\t\t}"
                
            if method.out_args:
                method_out += "out {"
                for out_arg in method.out_args:
                    method_out += "\n\t\t\t{} {}".format(out_arg[1], out_arg[0])
                method_out += "\n\t\t}"
            fidl_str += f"""method {method.name}{method_flag} {{
        {method_in}
        {method_out}
    }}
    """
    ## Explicit arrays in the interface
    if (interface.arrays):
        fidl_str += f"""
    """
        for array in interface.arrays:
            fidl_str += f"""array {array.name} of {array.type}
    """
    ## Structs in the interface
    if (interface.structs):
        fidl_str += f"""
    """
        for struct in interface.structs:
            struct_elements = ""
            for name, type in struct.elements:
                struct_elements += f"""
        {type} {name}"""
            
            fidl_str +=  f"""struct {struct.name} {{{struct_elements}
    }}
    """
    ## Enumerations in the interface
    if (interface.enumerations):
        fidl_str += f"""
    """
        for enumeration in interface.enumerations:
            enumeration_elements = ""
        #     for name, value in enumeration.enumerators:
        #         enumeration_elements += f"""
        # {name} = {value}"""
            for enumerator in enumeration.enumerators:
                if enumerator[1] != None:
                    enumeration_elements += f"""
            {enumerator[0]} = {enumerator[1]}"""
                else:
                    enumeration_elements = f"""
            {enumerator[0]}"""    
        
            fidl_str += f"""enumeration {enumeration.name} {{{enumeration_elements}
    }}
    """
    if (interface.maps):
        fidl_str += f"""
    """
        for map in interface.maps:
            fidl_str += f"""map {map.name} {{
        {map.key_type} to {map.value_type}
    }}
    """
    fidl_str += f"""
}}"""

    # Transform data types that are String but not defined with name String
    fidl_str = string_transformation(fidl_str, interface.strings)
    
    # print(fidl_str)
    return fidl_str

def generate_fdepl_from_arxml(interface):
    
    ## Package, name, and version of the interface
    ### Package는 현재 ARXML에 있는 것 사용하도록 되어 있으나 바뀔 수 있음
    packages = ""
    packages += interface.packages[0]
    if len(interface.packages) > 1:
        for package in interface.packages[1:]:
            packages += "."+package
    
    ## FDEPL string
    fdepl_str = f"""import \"platform:/plugin/org.genivi.commonapi.someip/deployment/CommonAPI-4-SOMEIP_deployment_spec.fdepl\"
import \"{interface.name}.fidl\"

define org.genivi.commonapi.someip.deployment for interface {packages}.{interface.name} {{
    
    SomeIpServiceID = {interface.serviceId}
    """
    if interface.fields:
        fdepl_str += f"""
    """
        for field in interface.fields:
            field_getter_str = ""
            field_setter_str = ""
            field_notifier_str = ""
            if field.getter["has_getter"] == "true":
                field_getter_str += "SomeIpGetterID = {}\n".format(field.getter["id"])
                field_getter_str += "\t\tSomeIpGetterReliable = {}\n".format(field.getter["protocol"])
            if field.setter["has_setter"] == "true":
                field_setter_str += "SomeIpSetterID = {}\n".format(field.setter["id"])
                field_setter_str += "\t\tSomeIpSetterReliable = {}\n".format(field.setter["protocol"])
            if field.notifier["has_notifier"] == "true":
                field_notifier_str += "SomeIpNotifierID = {}\n".format(field.notifier["id"])
                field_notifier_str += "\t\tSomeIpNotifierReliable = {}\n".format(field.notifier["protocol"])
                # Only one event group per event
                # field_notifier_str += "\t\tSomeIpEventGroups = {{{}}}\n".format((field.notifier[3]))
                # if len(field.notifier) > 3:   
                #     field_notifier_str += "\t\tSomeIpNotifierEventGroups = {{{}}}\n".format(field.notifier[3])
                field_notifier_str += "\t\tSomeIpNotifierEventGroups = {{{}}}\n".format((", ").join(field.eventgroups))
            fdepl_str += f"""attribute {field.name} {{
        {field_getter_str}
        {field_setter_str}
        {field_notifier_str}\t}}
    
    """
    
    ### Out Arguments 하고 Event Group 추가 필요
    if interface.events:
        for event in interface.events:
            event_str = ""
            fdepl_str += f"""broadcast {event.name} {{
        SomeIpEventID = {event.eventId}
        SomeIpEventReliable = {event.reliable}
        SomeIpEventGroups = {{{(", ".join(event.eventgroups))}}}
        out {{ }}
    }}
    
    """
    
    ### In / Out Argumetns 추가 필요
    if interface.methods:
        for method in interface.methods:
            fdepl_str += f"""method {method.name} {{
        SomeIpMethodID = {method.methodId}
        in {{ }}
        out {{ }}
    }}
    
    """
    if interface.arrays:
        for array in interface.arrays:
            fdepl_str += f"""array {array.name} {{ }}
    """
    
    if interface.structs:
        fdepl_str += f"""
    """
        for struct in interface.structs:
            fdepl_str += f"""struct {struct.name} {{ }}
    """
    
    if interface.enumerations:
        fdepl_str += f"""
    """
        for enumeration in interface.enumerations:
            enumeration_elements = ""
            enumeration_backingtype = ""
            if enumeration.backingtype is not None:
                if enumeration.backingtype != 'UInt8':
                    enumeration_backingtype += f"""EnumBackingType = {enumeration.backingtype}"""
                else:
                    enumeration_backingtype += f"""//EnumBackingType = {enumeration.backingtype}"""
            for name, value in enumeration.enumerators:
                enumeration_elements += f"""
        {name} {{}}"""
            fdepl_str += f"""enumeration {enumeration.name} {{
        {enumeration_backingtype}{enumeration_elements}
    }}
    """
    
    if interface.maps:
        fdepl_str += f"""
    """
        for map in interface.maps:
            fdepl_str += f"""map {map.name} {{ }}
    """
    
    fdepl_str += f"""
}}"""
    ### Interface에 해당하는 Instance 추가할 것
    if interface.instances:
        for instance in interface.instances:
            fdepl_str += f"""\n\ndefine org.genivi.commonapi.someip.deployment for provider as {instance.name} {{
    instance {packages}.{interface.name} {{
        InstanceId = \"{packages}.{instance.name}\"
        SomeIpInstanceID = {instance.instanceId}
        //SomeIpUnicastAddress: Modify it through vsomeip.json, the IP address of the host should be written
        //SomeIpReliableUnicastPort: {instance.reliablePort} Modify it through vsomeip.json, the TCP port of the host should be written
        //SomeIpUnreliableUnicastPort: {instance.unreliablePort} Modify it through vsomeip.json, the UDP port of the host should be written
        //SomeIpMulticastEventGroups = Optional
        //SomeIpMulticastAddresses = Optional
        //SomeIpMulticastPorts = Optional
    }}                
}}
"""

    return fdepl_str

def parse_command_line():
    parser = argparse.ArgumentParser(
        description="Parsar for ARXML to FIDL, FDPEL Conversion.")
    parser.add_argument(
        "-P", "--package", dest="package", action="store", help = "Use this option if you want to specify package of the FIDLs and FDEPLs", required=False
    )
    parser.add_argument(
        "-O", "--output", dest="output_dir", action="store", help="Output directory.", required=False, default='outputs'
    )
    parser.add_argument(
        "arxml", nargs="+", help="Input ARXML file(s)"
    )

    return parser.parse_args()

# Main
def main(args):
    
    try:
        for arxml in args.arxml:
            error_cnt = 0
            success_cnt = 0
            # current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.abspath(arxml)
            
            print(f"Parsing ARXML: {file_path}")
            
            tree = parse_arxml(file_path)
            if tree is None:
                raise Exception(f"Failed to parse ARMXL: {file_path}")
            roots = find_roots_of_tag(tree, "SERVICE-INTERFACE")
            package = []
            if args.package:
                package = args.package.split('.')
            Interfaces = []
            for root in roots:
                try:
                    Interfaces.append(Interface(root, tree, package = package))
                    success_cnt += 1
                    print(f"Parsing done without errors")
                except Exception as e:
                    print(f"INTERFACE PARSING ERROR {e}")
                    error_cnt += 1
                    if args.package:
                        package = args.package.split('.')
                    else:
                        package = []
                    continue
            os.makedirs(args.output_dir + '/fidl', exist_ok = True)
            
            for interface in Interfaces:
                try:
                    dump_interface(interface)
                    print(f"Generating FIDL, FDEPL of {interface.name}")
                    fidl_str = generate_fidl_from_arxml(interface)
                    if interface.instances:
                        fdepl_str = generate_fdepl_from_arxml(interface)
                    f = open("{}/fidl/{}.fidl".format(args.output_dir,interface.name), "w")
                    f.write(fidl_str)
                    f.close()
                    f = open("{}/fidl/{}.fdepl".format(args.output_dir,interface.name), "w")
                    f.write(fdepl_str)
                    f.close()
                    print(f"FIDL, FDPEL generation done without errors")
                except Exception as e:
                    print("CODE GENERATION ERROR at {}: {}".format(interface.name, e))
                    continue
            print(f"Total {success_cnt+error_cnt} interfaces in {file_path}\nSuccess: {success_cnt} Error: {error_cnt}")
    except (ET.ParseError, FileNotFoundError, Exception) as e:
        print("EXECUTION ERROR: {}".format(e))
        # sys.exit()
        
if __name__ == "__main__":
    args = parse_command_line()
    main(args)