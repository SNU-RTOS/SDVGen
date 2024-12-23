import sys
import os
import argparse
from aidl_parser import AIDLParser

class FDEPLGenerator:
    def __init__(self, parser_data: AIDLParser, aidl_filename: str, output_path: str = None):
        self.data = parser_data
        self.aidl_filename = aidl_filename
        
        if output_path is None:
            base_name = os.path.splitext(os.path.basename(aidl_filename))[0]
            output_path = os.path.join("outputs", "fdepl", f"{base_name}.fdepl")
        self.output_path = output_path

    def generate_fdepl(self):
        lines = []
        
        # Add auto-generated comment
        lines.append(f"//Auto generated FDEPL from {self.aidl_filename}.aidl")
        lines.append("")
        
        # Add imports
        lines.append('import "platform:/plugin/org.genivi.commonapi.someip/deployment/CommonAPI-4-SOMEIP_deployment_spec.fdepl"')
        base_name = os.path.splitext(os.path.basename(self.aidl_filename))[0]
        lines.append(f'import "{base_name}.fidl"')
        lines.append("")

        # Add interface deployment
        interface_fqn = f"{self.data.package_name}.{self.data.interface_name}"
        lines.append(f"define org.genivi.commonapi.someip.deployment for interface {interface_fqn} {{")
        
        # Add service ID
        lines.append(f"    SomeIpServiceID = {self.data.someip_interface.service_id}")
        lines.append("")
        
        # Add attributes
        self._add_attributes(lines)
        
        # Add methods
        self._add_methods(lines)
        
        # Add broadcasts
        self._add_broadcasts(lines)
        
        self._add_type_definitions(lines)
        
        lines.append("}")
        lines.append("")

        # Add provider deployment
        lines.append(f"define org.genivi.commonapi.someip.deployment for provider as Provider_{self.data.interface_name} {{")
        lines.append(f"    instance {interface_fqn} {{")
        lines.append(f'        InstanceId = "{self.data.package_name}.Provider_{self.data.interface_name}"')
        lines.append(f"        SomeIpInstanceID = {self.data.someip_interface.instance_id}")
        lines.append("    }")
        lines.append("}")

        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)

        # Write to file
        with open(self.output_path, 'w') as f:
            f.write('\n'.join(lines))
        print(f"\nFDEPL file generated successfully: {self.output_path}")

    def _add_type_definitions(self, lines):
        # Add arrays
        for array_name in self.data.arrays:
            array_config = self.data.someip_types["arrays"].get(array_name, {})
            lines.append(f"    array {array_name} {{")
            
            # Only add non-default values
            if array_config.get("min_length", 0) != 0:
                lines.append(f"        SomeIpArrayMinLength = {array_config['min_length']}")
            if array_config.get("max_length", 0) != 0:
                lines.append(f"        SomeIpArrayMaxLength = {array_config['max_length']}")
            if array_config.get("length_width", 4) != 4:
                lines.append(f"        SomeIpArrayLengthWidth = {array_config['length_width']}")
            
            lines.append("    }")
            lines.append("")

        # Add structs
        for struct_name in self.data.structs:
            struct_config = self.data.someip_types["structs"].get(struct_name, {})
            lines.append(f"    struct {struct_name} {{")
            
            # Only add non-default value
            if struct_config.get("length_width", 0) != 0:
                lines.append(f"        SomeIpStructLengthWidth = {struct_config['length_width']}")
            
            lines.append("    }")
            lines.append("")
            
        # Add enumerations
        for enum_name, enum_values in self.data.enumerations.items():
            lines.append(f"    enumeration {enum_name} {{")
            
            # Add backing type only if it's not the default
            enum_config = self.data.someip_types["enumerations"].get(enum_name, {})
            backing_type = enum_config.get("backing_type", "UInt8")
            if backing_type != "UInt8":
                lines.append(f"        EnumBackingType = {backing_type}")
            
            # Add all enumerators
            for value in enum_values:
                lines.append(f"        {value} {{}}")
            
            lines.append("    }")
            lines.append("")

    def _add_attributes(self, lines):
        for attr_name, attr in self.data.attributes.items():
            if attr_name in self.data.someip_attributes:
                someip_info = self.data.someip_attributes[attr_name]
                lines.append(f"    attribute {attr_name} {{")
                
                if attr["getter"] and someip_info.getter_id is not None:
                    lines.append(f"        SomeIpGetterID = {someip_info.getter_id}")
                    lines.append(f"        SomeIpGetterReliable = {str(someip_info.getter_reliable).lower()}")
                    lines.append("")

                if attr["setter"] and someip_info.setter_id is not None:
                    lines.append(f"        SomeIpSetterID = {someip_info.setter_id}")
                    lines.append(f"        SomeIpSetterReliable = {str(someip_info.setter_reliable).lower()}")
                    lines.append("")

                if attr["notifier"] and someip_info.notifier_id is not None:
                    lines.append(f"        SomeIpNotifierID = {someip_info.notifier_id}")
                    lines.append(f"        SomeIpNotifierReliable = {str(someip_info.notifier_reliable).lower()}")
                    lines.append(f"        SomeIpNotifierEventGroups = {{{someip_info.notifier_event_group}}}")
                
                lines.append("    }")
                lines.append("")

    def _add_methods(self, lines):
        for method in self.data.methods:
            if method["name"] in self.data.someip_methods:
                someip_info = self.data.someip_methods[method["name"]]
                lines.append(f"    method {method['name']} {{")
                lines.append(f"        SomeIpMethodID = {someip_info.method_id}")
                lines.append(f"        SomeIpReliable = {str(someip_info.method_reliable).lower()}")
                
                if(someip_info.method_endianess == "le"):
                    lines.append(f"        SomeIpMethodEndianess = {someip_info.method_endianess}") # {le, be} (default: be)
                
                if(someip_info.method_requestST > 0):
                    lines.append(f"        SomeIpMethodSeparationTime = {someip_info.method_requestST}")
                if(someip_info.method_responseST > 0):
                    lines.append(f"        SomeIpMethodSeparationTimeResponse = {someip_info.method_responseST}")
                
                if method["arguments"]:
                    lines.append("        in {}")
                
                if method["return_type"] != "void":
                    lines.append("        out {}")
                
                lines.append("    }")
                lines.append("")

    def _add_broadcasts(self, lines):
        for bcast_name, bcast in self.data.broadcasts.items():
            if bcast_name in self.data.someip_broadcasts:
                someip_info = self.data.someip_broadcasts[bcast_name]
                lines.append(f"    broadcast {bcast_name} {{")
                lines.append(f"        SomeIpEventID = {someip_info.event_id}")
                lines.append(f"        SomeIpEventReliable = {str(someip_info.event_reliable).lower()}")
                lines.append(f"        SomeIpEventGroups = {{{someip_info.event_group}}}")
                lines.append("    }")
                lines.append("")

class IDTracker:
    def __init__(self):
        self.used_low_ids = set()  # IDs < 0x8000
        self.used_high_ids = set()  # IDs >= 0x8000

    def is_id_used(self, new_id: int) -> bool:
        if new_id < 0x8000:
            return new_id in self.used_low_ids
        else:
            return new_id in self.used_high_ids

    def add_id(self, new_id: int):
        if new_id < 0x8000:
            self.used_low_ids.add(new_id)
        else:
            self.used_high_ids.add(new_id)

def get_valid_id(prompt: str, id_tracker: IDTracker = None, is_method = True) -> int:
    while True:
        try:
            id_value = int(input(prompt))
            if(not is_method):
                id_value += 32768
            if not 0 <= id_value < 65536:  # 0xFFFF + 1
                print("Error: ID must be less than 65536 (0x10000)")
                continue
            
            # If we're tracking IDs, check for uniqueness
            if id_tracker:
                if id_tracker.is_id_used(id_value):
                    print(f"Error: ID {id_value} (0x{id_value:04x}) is already in use")
                    continue

                id_tracker.add_id(id_value)
            
            return id_value
        except ValueError:
            print("Error: Please enter a valid number")

def get_boolean(prompt: str) -> bool:
    while True:
        value = input(prompt).lower()
        if value in ['true', 't', 'yes', 'y', '1']:
            return True
        if value in ['false', 'f', 'no', 'n', '0']:
            return False
        print("Please enter true/false, yes/no, or 1/0")

def main():
    print("FDEPL GENERATOR")
    # # Get AIDL file path
    # aidl_file = input("Enter AIDL file path: ")
    
    # try:
    #     with open(aidl_file, 'r') as file:
    #         aidl_content = file.read()
    # except FileNotFoundError:
    #     print(f"Error: File '{aidl_file}' not found.")
    #     return
    
    # # Parse AIDL file
    # parser = AIDLParser(aidl_content, aidl_file)
    # parser.parse()
    
    # # Get interface IDs
    # service_id = get_valid_id("Enter Service ID: ")
    # instance_id = get_valid_id("Enter Instance ID: ")
    # parser.set_someip_interface_info(service_id, instance_id)
    
    # # Get attribute information
    # for attr_name, attr in parser.attributes.items():
    #     print(f"\nConfiguring attribute: {attr_name}")
        
    #     if attr["getter"]:
    #         getter_id = get_valid_id("Enter Getter ID: ")
    #         getter_reliable = get_boolean("Is getter reliable? (true/false): ")
    #     else:
    #         getter_id = getter_reliable = None
            
    #     if attr["setter"]:
    #         setter_id = get_valid_id("Enter Setter ID: ")
    #         setter_reliable = get_boolean("Is setter reliable? (true/false): ")
    #     else:
    #         setter_id = setter_reliable = None
            
    #     if attr["notifier"]:
    #         notifier_id = get_valid_id("Enter Notifier ID: ")
    #         notifier_reliable = get_boolean("Is notifier reliable? (true/false): ")
    #         notifier_event_group = get_valid_id("Enter Notifier Event Group ID: ")
    #     else:
    #         notifier_id = notifier_reliable = notifier_event_group = None
        
    #     parser.set_attribute_info(attr_name, getter_id, getter_reliable,
    #                             setter_id, setter_reliable,
    #                             notifier_id, notifier_reliable,
    #                             notifier_event_group)
    
    # # Get method information
    # for method in parser.methods:
    #     print(f"\nConfiguring method: {method['name']}")
    #     method_id = get_valid_id("Enter Method ID: ")
    #     parser.set_method_info(method["name"], method_id)
    
    # # Get broadcast information
    # for bcast_name in parser.broadcasts:
    #     print(f"\nConfiguring broadcast: {bcast_name}")
    #     event_id = get_valid_id("Enter Event ID: ")
    #     event_reliable = get_boolean("Is event reliable? (true/false): ")
    #     event_group = get_valid_id("Enter Event Group ID: ")
    #     parser.set_broadcast_info(bcast_name, event_id, event_reliable, event_group)
    
    # # Generate FDEPL file
    # generator = FDEPLGenerator(parser, aidl_file)
    # generator.generate_fdepl()

if __name__ == "__main__":
    main()