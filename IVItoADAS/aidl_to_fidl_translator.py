import sys
import os
import argparse
from aidl_parser import AIDLParser
import json
from typing import Dict, Any, Optional
from aidl_to_fidl_generator import FIDLGenerator
from aidl_to_fdepl_generator import FDEPLGenerator, get_valid_id, get_boolean, IDTracker

class SomeIpConfig:
    def __init__(self, interface_name: str, output_dir: str):
        self.interface_name = interface_name
        self.config_path = os.path.join(output_dir, f"{interface_name}_someip_config.json")
        self.default_array_length_width = 4
        self.default_struct_length_width = 0
        self.default_enum_backing_type = "UInt8"
        self.valid_enum_types = ["UInt8", "UInt16", "UInt32", "UInt64"]

    def generate_template(self, aidl_parser: AIDLParser) -> Dict[str, Any]:
        """Generate a template configuration dictionary"""
        config = {
            "configuration": {
                "package": aidl_parser.package_name,  # Default to AIDL package name
                "version": {
                    "major": 0,
                    "minor": 0
                },
                "allow_fire_and_forget": False
            },
            "interface": {
                "service_id": None,
                "instance_id": None
            },
            "attributes": {},
            "methods": {},
            "broadcasts": {},
            "types": {
                "arrays": {},
                "structs": {},
                "enumerations": {}
            }
        }

        # Add template for enumerations
        for enum_name, enum_values in aidl_parser.enumerations.items():
            config["types"]["enumerations"][enum_name] = {
                "backing_type": self.default_enum_backing_type
            }


        # Add template for arrays
        for array_name in aidl_parser.arrays:
            config["types"]["arrays"][array_name] = {
                "min_length": 0,
                "max_length": 0,
                "length_width": self.default_array_length_width
            }

        # Add template for structs
        for struct_name in aidl_parser.structs:
            config["types"]["structs"][struct_name] = {
                "length_width": self.default_struct_length_width
            }

        # Add template for attributes
        for attr_name, attr in aidl_parser.attributes.items():
            attr_config = {}
            if attr["getter"]:
                attr_config["getter"] = {
                    "id": None,  # Example: 1
                    "reliable": True
                }
            if attr["setter"]:
                attr_config["setter"] = {
                    "id": None,  # Example: 2
                    "reliable": True
                }
            if attr["notifier"]:
                attr_config["notifier"] = {
                    "id": None,  # Example: 3
                    "reliable": True,
                    "event_group": None  # Example: 1
                }
            config["attributes"][attr_name] = attr_config

        # Add template for methods
        for method in aidl_parser.methods:
            config["methods"][method["name"]] = {
                "id": None,  # Example: 100
                "reliable": True,
                "endianess": "be",
                "request separation time (optional)": 0,
                "response separation time (optional)": 0
            }

        # Add template for broadcasts
        for bcast_name in aidl_parser.broadcasts:
            config["broadcasts"][bcast_name] = {
                "id": None,  # Example: 200
                "reliable": True,
                "event_group": None  # Example: 2
            }

        return config

    def update_config_if_needed(self, config: Dict[str, Any], aidl_parser: AIDLParser) -> Dict[str, Any]:
        """Update configuration with any missing fields"""
        updated = False
        
        # Ensure configuration section exists
        if "configuration" not in config:
            config["configuration"] = {
                "package": aidl_parser.package_name,
                "version": {
                    "major": 0,
                    "minor": 0
                },
                "allow_fire_and_forget": False
            }
            updated = True
        else:
            # Check configuration fields
            if "package" not in config["configuration"]:
                config["configuration"]["package"] = aidl_parser.package_name
                updated = True
            if "version" not in config["configuration"]:
                config["configuration"]["version"] = {"major": 0, "minor": 0}
                updated = True
            elif "major" not in config["configuration"]["version"] or "minor" not in config["configuration"]["version"]:
                config["configuration"]["version"] = {"major": 0, "minor": 0}
                updated = True
            if "allow_fire_and_forget" not in config["configuration"]:
                config["configuration"]["allow_fire_and_forget"] = False
                updated = True
        
        # Ensure types section exists
        if "types" not in config:
            config["types"] = {"arrays": {}, "structs": {}, "enumerations": {}}
            updated = True

        # Check enumerations
        if "enumerations" not in config["types"]:
            config["types"]["enumerations"] = {}
            updated = True
        
        for enum_name in aidl_parser.enumerations:
            if enum_name not in config["types"]["enumerations"]:
                config["types"]["enumerations"][enum_name] = {
                    "backing_type": self.default_enum_backing_type
                }
                updated = True
            else:
                # Ensure backing_type exists and is valid
                enum_config = config["types"]["enumerations"][enum_name]
                if "backing_type" not in enum_config:
                    enum_config["backing_type"] = self.default_enum_backing_type
                    updated = True
                elif enum_config["backing_type"] not in self.valid_enum_types:
                    print(f"Warning: Invalid backing type '{enum_config['backing_type']}' for enumeration {enum_name}. Using default.")
                    enum_config["backing_type"] = self.default_enum_backing_type
                    updated = True

        # Check arrays
        if "arrays" not in config["types"]:
            config["types"]["arrays"] = {}
            updated = True
        
        for array_name in aidl_parser.arrays:
            if array_name not in config["types"]["arrays"]:
                config["types"]["arrays"][array_name] = {
                    "min_length": 0,
                    "max_length": 0,
                    "length_width": self.default_array_length_width
                }
                updated = True
            else:
                # Ensure all fields exist
                array_config = config["types"]["arrays"][array_name]
                if "min_length" not in array_config:
                    array_config["min_length"] = 0
                    updated = True
                if "max_length" not in array_config:
                    array_config["max_length"] = 0
                    updated = True
                if "length_width" not in array_config:
                    array_config["length_width"] = self.default_array_length_width
                    updated = True

        # Check structs
        if "structs" not in config["types"]:
            config["types"]["structs"] = {}
            updated = True
        
        for struct_name in aidl_parser.structs:
            if struct_name not in config["types"]["structs"]:
                config["types"]["structs"][struct_name] = {
                    "length_width": self.default_struct_length_width
                }
                updated = True
            else:
                # Ensure length_width exists
                if "length_width" not in config["types"]["structs"][struct_name]:
                    config["types"]["structs"][struct_name]["length_width"] = self.default_struct_length_width
                    updated = True

        if updated:
            # Save updated configuration
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
            print(f"\nUpdated configuration file with missing fields: {self.config_path}")

        return config


    def save_template(self, aidl_parser: AIDLParser):
        """Generate and save a template configuration file"""
        config = self.generate_template(aidl_parser)
        
        # Add helpful comments at the top of the JSON file
        template_str = """{
"""
        # Convert the config to JSON string (without the first {)
        config_str = json.dumps(config, indent=4)[1:]
        
        # Combine the comment and config
        final_str = template_str + config_str

        with open(self.config_path, 'w') as f:
            f.write(final_str)
        
        print(f"\nGenerated SOMEIP configuration template: {self.config_path}")
        print("Please fill in the configuration values and run the generator again.")
        sys.exit(0)

    def load_config(self) -> Optional[Dict[str, Any]]:
        """Load configuration from file if it exists"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def validate_config(self, config: Dict[str, Any], aidl_parser: AIDLParser) -> bool:
        """Validate the configuration values"""
        try:
            # Validate configuration section
            if not isinstance(config["configuration"]["version"]["major"], int):
                print("Error: Version major must be an integer")
                return False
            if not isinstance(config["configuration"]["version"]["minor"], int):
                print("Error: Version minor must be an integer")
                return False
            if not isinstance(config["configuration"]["allow_fire_and_forget"], bool):
                print("Error: allow_fire_and_forget must be a boolean")
                return False
            if not isinstance(config["configuration"]["package"], str):
                print("Error: Package must be a string")
                return False
            
            # Track IDs for uniqueness
            method_ids = set()

            # Check interface IDs
            if not isinstance(config["interface"]["service_id"], int) or \
               not isinstance(config["interface"]["instance_id"], int):
                print("Error: Service ID and Instance ID must be integers")
                return False

            # Helper function to validate ID
            def validate_id(id_value: int, id_type: str) -> bool:
                if not 0 <= id_value < 65536:
                    print(f"Error: {id_type} must be between 0 and 65535")
                    return False
                base_id = id_value & ~0x8000
                if base_id in method_ids:
                    print(f"Error: Duplicate ID found: {id_value}")
                    return False
                method_ids.add(base_id)
                return True

            # Check attributes
            for attr_name, attr in config["attributes"].items():
                if attr_name not in aidl_parser.attributes:
                    print(f"Error: Unknown attribute {attr_name}")
                    return False
                
                if "getter" in attr:
                    if not validate_id(attr["getter"]["id"], "Getter ID"):
                        return False
                if "setter" in attr:
                    if not validate_id(attr["setter"]["id"], "Setter ID"):
                        return False
                if "notifier" in attr:
                    if not validate_id(attr["notifier"]["id"], "Notifier ID"):
                        return False
                    if not validate_id(attr["notifier"]["event_group"], "Event Group ID"):
                        return False

            # Check methods
            for method_name, method in config["methods"].items():
                if not validate_id(method["id"], "Method ID"):
                    return False
                if (method["endianess"] != "be" and method["endianess"] != "le"):
                    return False
                
            # Check broadcasts
            for bcast_name, bcast in config["broadcasts"].items():
                if not validate_id(bcast["id"], "Broadcast ID"):
                    return False
                if not validate_id(bcast["event_group"], "Event Group ID"):
                    return False

            # Validate array configurations
            if "types" in config and "arrays" in config["types"]:
                for array_name, array_config in config["types"]["arrays"].items():
                    if not isinstance(array_config["min_length"], int) or array_config["min_length"] < 0:
                        print(f"Error: Invalid min_length for array {array_name}")
                        return False
                    if not isinstance(array_config["max_length"], int) or array_config["max_length"] < 0:
                        print(f"Error: Invalid max_length for array {array_name}")
                        return False
                    if not isinstance(array_config["length_width"], int) or array_config["length_width"] < 0:
                        print(f"Error: Invalid length_width for array {array_name}")
                        return False

            # Validate struct configurations
            if "types" in config and "structs" in config["types"]:
                for struct_name, struct_config in config["types"]["structs"].items():
                    if not isinstance(struct_config["length_width"], int) or struct_config["length_width"] < 0:
                        print(f"Error: Invalid length_width for struct {struct_name}")
                        return False
                    
            # Validate enumeration configurations
            if "types" in config and "enumerations" in config["types"]:
                for enum_name, enum_config in config["types"]["enumerations"].items():
                    if enum_config["backing_type"] not in self.valid_enum_types:
                        print(f"Error: Invalid backing type for enumeration {enum_name}")
                        return False

            return True

        except KeyError as e:
            print(f"Error: Missing required configuration field: {e}")
            return False
        except TypeError as e:
            print(f"Error: Invalid configuration format: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='AIDL to FIDL/FDEPL converter')
    parser.add_argument('aidl_file', help='Path to the AIDL file')
    parser.add_argument('--output-dir', default='outputs',
                      help='Output directory for generated files (default: outputs)')
    
    args = parser.parse_args()

    try:
        # Read AIDL file
        with open(args.aidl_file, 'r') as file:
            aidl_content = file.read()
    except FileNotFoundError:
        print(f"Error: File '{args.aidl_file}' not found.")
        sys.exit(1)
    except IOError:
        print(f"Error: Unable to read file '{args.aidl_file}'.")
        sys.exit(1)

    try:
        # Parse AIDL file
        print("\nParsing AIDL file...")
        aidl_parser = AIDLParser(aidl_content, args.aidl_file)
        aidl_parser.parse()
        
        # Print parsed structure
        print("\nParsed AIDL Structure:")
        aidl_parser.print_tree()
        
        
        # FDEPL
        
        # Collect SOMEIP information for FDEPL
        print("\nCollecting SOMEIP deployment information for FDEPL generation:")
        
        # Setup SOMEIP configuration
        someip_config = SomeIpConfig(aidl_parser.interface_name, args.output_dir)
        
        # Try to load existing configuration
        config = someip_config.load_config()
        
        if config is None:
            # No configuration file exists, generate template
            someip_config.save_template(aidl_parser)
        else:
            # Update configuration if needed
            config = someip_config.update_config_if_needed(config, aidl_parser)
        
        # Validate configuration
        if not someip_config.validate_config(config, aidl_parser):
            print("\nPlease correct the configuration file and try again.")
            sys.exit(1)
        
        # Use configuration values
        aidl_parser.set_someip_interface_info(
            config["interface"]["service_id"],
            config["interface"]["instance_id"]
        )
        aidl_parser.someip_types = config["types"]
        
        # Set attribute information
        for attr_name, attr_config in config["attributes"].items():
            if attr_name in aidl_parser.attributes:
                getter_id = attr_config.get("getter", {}).get("id")
                getter_reliable = attr_config.get("getter", {}).get("reliable", True)
                setter_id = attr_config.get("setter", {}).get("id")
                setter_reliable = attr_config.get("setter", {}).get("reliable", True)
                notifier_id = attr_config.get("notifier", {}).get("id")
                notifier_reliable = attr_config.get("notifier", {}).get("reliable", True)
                notifier_event_group = attr_config.get("notifier", {}).get("event_group")
                
                aidl_parser.set_attribute_info(
                    attr_name, getter_id, getter_reliable,
                    setter_id, setter_reliable,
                    notifier_id, notifier_reliable,
                    notifier_event_group
                )
        
        # Set method information
        for method_name, method_config in config["methods"].items():
            aidl_parser.set_method_info(method_name, method_config["id"], method_config["reliable"], method_config["endianess"],
                                        method_config["request separation time (optional)"], method_config["response separation time (optional)"])
        
        # Set broadcast information
        for bcast_name, bcast_config in config["broadcasts"].items():
            aidl_parser.set_broadcast_info(
                bcast_name,
                bcast_config["id"],
                bcast_config["reliable"],
                bcast_config["event_group"]
            )
        
        # Get base filename without extension
        base_filename = os.path.basename(args.aidl_file)
        base_name = os.path.splitext(base_filename)[0]
        
        # Create output directory if it doesn't exist
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Setup output paths in the same directory
        fidl_output = os.path.join(args.output_dir, f"{base_name}.fidl")
        fdepl_output = os.path.join(args.output_dir, f"{base_name}.fdepl")
        
        # Generate FIDL file
        print("\nGenerating FIDL file...")
        fidl_generator = FIDLGenerator(
            aidl_parser,
            base_filename,
            fidl_output,
            config["configuration"]["package"],
            config["configuration"]["version"]["major"],
            config["configuration"]["version"]["minor"],
            config["configuration"]["allow_fire_and_forget"]
        )
        fidl_generator.generate_fidl()
        
        
        # Generate FDEPL file
        print("\nGenerating FDEPL file...")
        fdepl_generator = FDEPLGenerator(aidl_parser, base_filename, fdepl_output)
        fdepl_generator.generate_fdepl()
        
        print("\nGeneration completed successfully!")
        print(f"Generated files in directory: {args.output_dir}")
        print(f"FIDL file: {os.path.basename(fidl_output)}")
        print(f"FDEPL file: {os.path.basename(fdepl_output)}")
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in configuration file: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()