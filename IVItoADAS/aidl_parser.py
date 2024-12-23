import re
import sys
import os
from typing import List, Dict, Any

# Deployment Information
class SomeIpMethodInfo:
    def __init__(self):
        self.method_id = None
        self.method_reliable = None
        self.method_endianess = None
        self.method_requestST = None
        self.method_responseST = None
        self.method_maxRequestLen = None
        self.method_maxResponseLen = None

class SomeIpAttributeInfo:
    def __init__(self):
        self.getter_id = None
        self.getter_reliable = None
        self.setter_id = None
        self.setter_reliable = None
        self.notifier_id = None
        self.notifier_reliable = None
        self.notifier_event_group = None

class SomeIpBroadcastInfo:
    def __init__(self):
        self.event_id = None
        self.event_reliable = None
        self.event_group = None

class SomeIpInterfaceInfo:
    def __init__(self):
        self.service_id = None
        self.instance_id = None

# AIDLParser
class AIDLParser:
    def __init__(self, file_content: str, file_path: str):
        self.content = file_content
        self.file_path = file_path
        self.package_name = ""
        self.imports: List[str] = []
        self.interface_name = ""
        self.attributes: Dict[str, Dict[str, Any]] = {}
        self.methods: List[Dict[str, Any]] = []
        self.broadcasts: Dict[str, Dict[str, Any]] = {}
        self.structs: Dict[str, List[Dict[str, str]]] = {}
        self.maps: Dict[str, Dict[str, str]] = {}
        self.arrays: Dict[str, str] = {}
        self.enumerations: Dict[str, List[str]] = {}
        # Deployment Information
        self.someip_interface = SomeIpInterfaceInfo()
        self.someip_methods: Dict[str, SomeIpMethodInfo] = {}
        self.someip_attributes: Dict[str, SomeIpAttributeInfo] = {}
        self.someip_broadcasts: Dict[str, SomeIpBroadcastInfo] = {}
        # SOMEIP type information including enumerations
        self.someip_types: Dict[str, Dict[str, Dict[str, Any]]] = {
            "arrays": {},
            "structs": {},
            "enumerations": {}
        }

    def set_type_info(self, type_config: Dict[str, Dict[str, Dict[str, Any]]]):
        """Set SOMEIP type configuration information"""
        self.someip_types = type_config

    def set_someip_interface_info(self, service_id: int, instance_id: int):
        self.someip_interface.service_id = service_id
        self.someip_interface.instance_id = instance_id

    def set_method_info(self, method_name: str, method_id: int, method_reliable: str, method_endianess: str, 
                        method_requestST: int, method_responseST: int): # method_maxRequestLen: int, method_maxResponseLen: int): 
        if method_name not in self.someip_methods:
            self.someip_methods[method_name] = SomeIpMethodInfo()
        self.someip_methods[method_name].method_id = method_id
        self.someip_methods[method_name].method_reliable = method_reliable
        self.someip_methods[method_name].method_endianess = method_endianess
        self.someip_methods[method_name].method_requestST = method_requestST
        self.someip_methods[method_name].method_responseST = method_responseST
        # self.someip_methods[method_name].method_maxRequestLen = method_maxRequestLen
        # self.someip_methods[method_name].method_maxResponseLen = method_maxResponseLen
        

    def set_attribute_info(self, attr_name: str, getter_id: int = None, 
                         getter_reliable: bool = None, setter_id: int = None, 
                         setter_reliable: bool = None, notifier_id: int = None,
                         notifier_reliable: bool = None, notifier_event_group: int = None):
        if attr_name not in self.someip_attributes:
            self.someip_attributes[attr_name] = SomeIpAttributeInfo()
        
        attr_info = self.someip_attributes[attr_name]
        if getter_id is not None:
            attr_info.getter_id = getter_id
            attr_info.getter_reliable = getter_reliable
        if setter_id is not None:
            attr_info.setter_id = setter_id
            attr_info.setter_reliable = setter_reliable
        if notifier_id is not None:
            attr_info.notifier_id = notifier_id
            attr_info.notifier_reliable = notifier_reliable
            attr_info.notifier_event_group = notifier_event_group

    def set_broadcast_info(self, broadcast_name: str, event_id: int,
                         event_reliable: bool, event_group: int):
        if broadcast_name not in self.someip_broadcasts:
            self.someip_broadcasts[broadcast_name] = SomeIpBroadcastInfo()
        
        bcast_info = self.someip_broadcasts[broadcast_name]
        bcast_info.event_id = event_id
        bcast_info.event_reliable = event_reliable
        bcast_info.event_group = event_group

    def validate_id(self, id_value: int) -> bool:
        return 0 <= id_value < 32768  # 0x8000
    
    def parse(self):
        self._parse_package()
        self._parse_imports()
        self._parse_interface()
        self._parse_functions()
        self._parse_parcelable()
        self._parse_enum()
        self._parse_imported_files()

    def _parse_package(self):
        package_match = re.search(r'package\s+([\w.]+);', self.content)
        if package_match:
            self.package_name = package_match.group(1)

    def _parse_imports(self):
        import_matches = re.findall(r'import\s+([\w.]+);', self.content)
        for imp in import_matches:
            parts = imp.split('.')
            if imp.startswith(self.package_name):
                self.imports.append(parts[-1])
            else:
                self.imports.append(imp)

    def _parse_interface(self):
        interface_match = re.search(r'interface\s+(\w+)', self.content)
        if interface_match:
            self.interface_name = interface_match.group(1)

    def _parse_functions(self):
        function_matches = re.findall(r'(\w+(?:\[\])?)\s+(\w+)\((.*?)\);', self.content, re.DOTALL)
        for return_type, name, args in function_matches:
            args_list = [arg.strip() for arg in args.split(',') if arg.strip()]
            
            if "Attribute" in name:
                self._process_attribute(name, return_type, args_list)
            elif name.startswith("subscribe") or name.startswith("unsubscribe"):
                self._process_broadcast(name, return_type, args_list)
            else:
                self._process_method(name, return_type, args_list)

    def _process_attribute(self, name, return_type, args_list):
        if name.startswith("get") or name.startswith("set"):
            attr_name = name.split("Attribute")[-1].split("Value")[0]
        else:  # For subscribe and unsubscribe
            attr_name = name.split("Attribute")[-1]

        if attr_name not in self.attributes:
            self.attributes[attr_name] = {
                "getter": False,
                "setter": False,
                "notifier": False,
                "data_type": None
            }
        
        if name.startswith("get"):
            self.attributes[attr_name]["getter"] = True
            self.attributes[attr_name]["data_type"] = return_type
        elif name.startswith("set"):
            self.attributes[attr_name]["setter"] = True
            self.attributes[attr_name]["data_type"] = args_list[-1].split()[1]
        elif name.startswith("subscribe") or name.startswith("unsubscribe"):
            self.attributes[attr_name]["notifier"] = True

    def _process_broadcast(self, name, return_type, args_list):
        broadcast_name = name.split("subscribe")[-1] if name.startswith("subscribe") else name.split("unsubscribe")[-1]
        if broadcast_name not in self.broadcasts:
            self.broadcasts[broadcast_name] = {
                "subscribe": False,
                "unsubscribe": False,
                "data_type": None
            }
        
        if name.startswith("subscribe"):
            self.broadcasts[broadcast_name]["subscribe"] = True
            if args_list:
                self.broadcasts[broadcast_name]["data_type"] = args_list[0].split()[0]
        elif name.startswith("unsubscribe"):
            self.broadcasts[broadcast_name]["unsubscribe"] = True

    def _process_method(self, name, return_type, args_list):
        self.methods.append({
            "name": name,
            "return_type": return_type,
            "arguments": args_list
        })

    def _parse_parcelable(self):
        parcelable_matches = re.findall(r'parcelable\s+(\w+)\s*{(.*?)}', self.content, re.DOTALL)
        for name, content in parcelable_matches:
            elements = [elem.strip() for elem in content.split(';') if elem.strip()]
            if len(elements) == 1 and '[]' in elements[0]:
                # This is an array
                data_type = elements[0].split()[0]
                self.arrays[name] = data_type
            elif len(elements) == 2 and 'key' in elements[0] and 'value' in elements[1]:
                # This is a map
                key_type = elements[0].split()[0]
                value_type = elements[1].split()[0]
                self.maps[name] = {"key": key_type, "value": value_type}
            else:
                # This is a struct
                struct_elements = []
                for elem in elements:
                    data_type, elem_name = elem.rsplit(' ', 1)
                    struct_elements.append({"name": elem_name, "type": data_type})
                self.structs[name] = struct_elements

    def _parse_enum(self):
        enum_matches = re.findall(r'enum\s+(\w+)\s*{(.*?)}', self.content, re.DOTALL)
        for name, content in enum_matches:
            enum_values = [value.strip() for value in content.split(',') if value.strip()]
            self.enumerations[name] = enum_values

    def _parse_imported_files(self):
        dir_path = os.path.dirname(self.file_path)
        for imp in self.imports:
            if "Handler" not in imp and "Callback" not in imp:
                imported_file_path = os.path.join(dir_path, f"{imp}.aidl")
                if os.path.exists(imported_file_path):
                    with open(imported_file_path, 'r') as file:
                        imported_content = file.read()
                    imported_parser = AIDLParser(imported_content, imported_file_path)
                    imported_parser.parse()
                    self.structs.update(imported_parser.structs)
                    self.maps.update(imported_parser.maps)
                    self.arrays.update(imported_parser.arrays)
                    self.enumerations.update(imported_parser.enumerations)

    def print_tree(self):
        print("AIDL Structure:")
        print(f"├── Package: {self.package_name}")
        print("├── Imports:")
        for imp in self.imports:
            print(f"│   ├── {imp}")
        if self.interface_name:
            print(f"├── Interface: {self.interface_name}")
            print("├── Attributes:")
            for attr_name, attr in self.attributes.items():
                print(f"│   ├── {attr_name}")
                print(f"│   │   ├── Data Type: {attr['data_type']}")
                print(f"│   │   ├── Getter: {attr['getter']}")
                print(f"│   │   ├── Setter: {attr['setter']}")
                print(f"│   │   └── Notifier: {attr['notifier']}")
            print("├── Methods:")
            for method in self.methods:
                print(f"│   ├── {method['name']}")
                print(f"│   │   ├── Return Type: {method['return_type']}")
                print(f"│   │   └── Arguments: {', '.join(method['arguments'])}")
            print("└── Broadcasts:")
            for broadcast_name, broadcast in self.broadcasts.items():
                print(f"    ├── {broadcast_name}")
                print(f"    │   └── Data Type: {broadcast['data_type']}")
        print("├── Structs:")
        for struct_name, elements in self.structs.items():
            print(f"│   ├── {struct_name}")
            for elem in elements:
                print(f"│   │   ├── {elem['name']}: {elem['type']}")
        print("├── Maps:")
        for map_name, map_types in self.maps.items():
            print(f"│   ├── {map_name}")
            print(f"│   │   ├── Key: {map_types['key']}")
            print(f"│   │   └── Value: {map_types['value']}")
        print("├── Arrays:")
        for array_name, array_type in self.arrays.items():
            print(f"│   ├── {array_name}: {array_type}")
        print("└── Enumerations:")
        for enum_name, enum_values in self.enumerations.items():
            print(f"    ├── {enum_name}")
            for value in enum_values:
                print(f"    │   ├── {value}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python aidl_parser.py <path_to_aidl_file>")
        sys.exit(1)

    aidl_file_path = sys.argv[1]

    try:
        with open(aidl_file_path, 'r') as file:
            aidl_content = file.read()
    except FileNotFoundError:
        print(f"Error: File '{aidl_file_path}' not found.")
        sys.exit(1)
    except IOError:
        print(f"Error: Unable to read file '{aidl_file_path}'.")
        sys.exit(1)

    try:
        parser = AIDLParser(aidl_content, aidl_file_path)
        parser.parse()
        parser.print_tree()
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)