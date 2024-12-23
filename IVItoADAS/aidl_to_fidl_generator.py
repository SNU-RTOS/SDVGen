import sys
import os
import argparse
from aidl_parser import AIDLParser

class FIDLGenerator:
    def __init__(self, parser_data: AIDLParser, aidl_filename: str, output_path: str = None, 
                 custom_package: str = None, version_major: int = 0, version_minor: int = 0, 
                 allow_fire_and_forget: bool = False):
        self.data = parser_data
        self.aidl_filename = aidl_filename
        self.custom_package = custom_package
        self.version_major = version_major
        self.version_minor = version_minor
        self.allow_fire_and_forget = allow_fire_and_forget
        
        # Set up default output path if none provided
        base_name = os.path.basename(aidl_filename)
        if output_path is None:
            output_path = os.path.join("outputs", "fidl")
        
        self.output_path = output_path
        if self.output_path and not os.path.exists(self.output_path):
            os.makedirs(self.output_path)
            
        self.output_file = os.path.join(self.output_path, os.path.splitext(base_name)[0] + ".fidl")

    def generate_fidl(self):
        lines = []
        
        # Add auto-generated comment
        lines.append(f"//Auto generated FIDL from {self.aidl_filename}")
        lines.append("")
        
        # Add package
        package_name = self.custom_package if self.custom_package else self.data.package_name
        lines.append(f"package {package_name}")
        lines.append("")

        # Add interface block that contains everything
        lines.append(f"interface {self.data.interface_name} {{")
        
        # Add version first
        lines.append(f"    version {{ major {self.version_major} minor {self.version_minor} }}")
        lines.append("")
        
        # Add attributes
        self._add_attributes(lines)
        
        # Add methods
        self._add_methods(lines)
        
        # Add broadcasts
        self._add_broadcasts(lines)
        
        # Generate all type definitions inside interface block
        self._add_type_definitions(lines)
        
        # Close interface block
        lines.append("}")

        # Write to file
        with open(self.output_file, 'w') as f:
            f.write('\n'.join(lines))
        print(f"\nFIDL file generated successfully: {self.output_file}")

    def _add_type_definitions(self, lines):
        # Add structs
        for struct_name, elements in self.data.structs.items():
            lines.append(f"    struct {struct_name} {{")
            for elem in elements:
                lines.append(f"        {elem['type']} {elem['name']}")
            lines.append("    }")
            lines.append("")

        # Add enumerations
        for enum_name, values in self.data.enumerations.items():
            lines.append(f"    enumeration {enum_name} {{")
            for value in values:
                lines.append(f"        {value}")
            lines.append("    }")
            lines.append("")

        # Add arrays
        for array_name, array_type in self.data.arrays.items():
            lines.append(f"    array {array_name} of {array_type}")
            lines.append("")

        # Add maps
        for map_name, map_types in self.data.maps.items():
            lines.append(f"    map {map_name} {{")
            lines.append(f"        {map_types['key']} to {map_types['value']}")
            lines.append("    }")
            lines.append("")

    def _add_attributes(self, lines):
        for attr_name, attr in self.data.attributes.items():
            if attr["data_type"]:
                flags = []
                if not attr["getter"]:
                    flags.append("noRead")
                if not attr["setter"]:
                    flags.append("readonly")
                if not attr["notifier"]:
                    flags.append("noSubscription")
                
                # Construct the attribute line with flags if any
                attr_line = f"    attribute {attr_name} {attr['data_type']}"
                if flags:
                    attr_line += " " + " ".join(flags)
                lines.append(attr_line)
        if self.data.attributes:
            lines.append("")

    def _add_methods(self, lines):
        for method in self.data.methods:
            # Check if method should be fire-and-forget
            is_fire_and_forget = self.allow_fire_and_forget and method['return_type'] == 'void'
            
            # Add fire-and-forget flag if applicable
            method_line = "    "
            if is_fire_and_forget:
                method_line += "fire-and-forget "
            method_line += f"method {method['name']} {{"
            lines.append(method_line)
            
            # Add input arguments if they exist
            if method['arguments']:
                lines.append("        in {")
                for arg in method['arguments']:
                    parts = arg.split()
                    if len(parts) >= 2:
                        if parts[0] == 'in':
                            data_type = parts[1]
                            var_name = parts[2]
                        else:
                            data_type = parts[0]
                            var_name = parts[1]
                        lines.append(f"            {data_type} {var_name}")
                lines.append("        }")

            # Add return type if it's not void
            if method['return_type'] != 'void':
                lines.append("        out {")
                lines.append(f"            {method['return_type']} return_val")
                lines.append("        }")
            
            lines.append("    }")
            lines.append("")

    def _add_broadcasts(self, lines):
        for bcast_name, bcast in self.data.broadcasts.items():
            lines.append(f"    broadcast {bcast_name} {{")
            if bcast['data_type']:
                lines.append("        out {")
                lines.append(f"            {bcast['data_type']} value")
                lines.append("        }")
            lines.append("    }")
            lines.append("")

def main():
    print("FIDL GENERATOR")
    # parser = argparse.ArgumentParser(description='AIDL to FIDL converter')
    # parser.add_argument('aidl_file', help='Path to the AIDL file')
    # parser.add_argument('--output', help='Output path for the FIDL file')
    # parser.add_argument('--package', help='Custom package name for FIDL file')
    # parser.add_argument('--version-major', type=int, default=0, help='Major version number')
    # parser.add_argument('--version-minor', type=int, default=0, help='Minor version number')
    
    # args = parser.parse_args()

    # try:
    #     with open(args.aidl_file, 'r') as file:
    #         aidl_content = file.read()
    # except FileNotFoundError:
    #     print(f"Error: File '{args.aidl_file}' not found.")
    #     sys.exit(1)
    # except IOError:
    #     print(f"Error: Unable to read file '{args.aidl_file}'.")
    #     sys.exit(1)

    # try:
    #     # Parse AIDL file
    #     print("\nParsing AIDL file...")
    #     aidl_parser = AIDLParser(aidl_content, args.aidl_file)
    #     aidl_parser.parse()
        
    #     # Print parsed structure
    #     print("\nParsed AIDL Structure:")
    #     aidl_parser.print_tree()
        
    #     # Get base filename without extension
    #     base_filename = os.path.basename(args.aidl_file)
        
    #     print("\nGenerating FIDL file...")
    #     fidl_generator = FIDLGenerator(
    #         aidl_parser,
    #         base_filename,
    #         args.output,
    #         args.package,
    #         args.version_major,
    #         args.version_minor
    #     )
    #     fidl_generator.generate_fidl()
        
    # except ValueError as e:
    #     print(f"Error: {str(e)}")
    #     sys.exit(1)

if __name__ == "__main__":
    main()