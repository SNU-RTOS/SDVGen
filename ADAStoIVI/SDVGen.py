#!/usr/bin/env python
################################################################
#                        SDVGen GUI Tool                       #
################################################################
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import io
import re
import argparse
import arxml_converter as arxml
import fidl_module_converter as fidl

class TextRedirector(io.StringIO):
    def __init__(self, text_widget, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.text_widget = text_widget

    def write(self, string):
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", string)
        self.text_widget.configure(state="disabled")

class GUIApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Code Converter ver0.3 (240719)")
        self.geometry("1200x800")  # Increased size to accommodate all buttons

        # Left frame for monitor
        self.monitor_frame = tk.Frame(self)
        self.monitor_frame.pack(side=tk.LEFT, fill=tk.Y)

        # Monitor
        self.monitor = tk.Text(self.monitor_frame, height=50, state="disabled")
        self.monitor.pack(fill="both", padx=10, pady=10)

        # Right frame for other widgets
        self.widget_frame = tk.Frame(self)
        self.widget_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Variables
        self.selected_files = []
        self.selected_arxml_files = []
        self.package_name = tk.StringVar()
        self.package_name.set("Write your Java package name")
        self.arxml_package_name = tk.StringVar()
        self.arxml_package_name.set("Write your FIDL package name")
        self.committed_package = tk.StringVar()  # Variable to store committed package name
        self.committed_arxml_package = tk.StringVar()
        self.output_dir = "outputs"
        self.version = tk.StringVar()
        self.version.set("JNI_VERSION_1_6")


        # New Package Name Entry for ARXML
        self.arxml_package_name_entry = tk.Entry(self.widget_frame, textvariable=self.arxml_package_name, fg="grey")
        self.arxml_package_name_entry.bind("<FocusIn>", self.clear_arxml_entry)
        self.arxml_package_name_entry.bind("<FocusOut>", self.restore_arxml_placeholder)
        self.arxml_package_name_entry.pack(pady=10)

        # New Commit Button for ARXML
        self.arxml_commit_button = tk.Button(self.widget_frame, text="Commit FIDL Package", command=self.print_arxml_package_name_and_save)
        self.arxml_commit_button.pack()

        # Committed ARXML Package Name Display
        self.committed_arxml_package_label = tk.Label(self.widget_frame, text="Committed FIDL Package Name:")
        self.committed_arxml_package_label.pack()
        self.committed_arxml_package_display = tk.Label(self.widget_frame, textvariable=self.committed_arxml_package)
        self.committed_arxml_package_display.pack()

        # Selected ARXML Files
        self.selected_arxml_files_label = tk.Label(self.widget_frame, text="Selected ARXML Files:")
        self.selected_arxml_files_label.pack()
        self.selected_arxml_files_text = tk.Text(self.widget_frame, height=3, width=50)
        self.selected_arxml_files_text.pack()
        self.select_arxml_files_button = tk.Button(self.widget_frame, text="Select ARXML Files", command=self.select_arxml_files)
        self.select_arxml_files_button.pack(pady=5)

        # Output Directory Selection
        self.output_dir_label = tk.Label(self.widget_frame, text="Output Directory:")
        self.output_dir_label.pack()
        self.output_dir_text = tk.Text(self.widget_frame, height=1, width=50)
        self.output_dir_text.insert(tk.END, self.output_dir)
        self.output_dir_text.pack()
        self.select_output_dir_button = tk.Button(self.widget_frame, text="Select Output Dir", command=self.select_output_dir)
        self.select_output_dir_button.pack()
        
        # ARXML Converter Button
        self.convert3_button = tk.Button(self.widget_frame, text="ARXML to FIDL and FDEPL", command=self.convert3)
        self.convert3_button.pack(padx=10, pady=5) #side="left",
        
        # Separator
        self.separator1 = ttk.Separator(self.widget_frame, orient='horizontal')
        self.separator1.pack()
        
        # Version Selection
        self.version_label = tk.Label(self.widget_frame, text="Select JNI Version:")
        self.version_label.pack()
        self.version_option_menu = tk.OptionMenu(self.widget_frame, self.version, "JNI_VERSION_1_1", "JNI_VERSION_1_2", "JNI_VERSION_1_4", "JNI_VERSION_1_6", "JNI_VERSION_1_8", "JNI_VERSION_9", "JNI_VERSION_10", "JNI_VERSION_19", "JNI_VERSION_20", "JNI_VERSION_21")
        self.version_option_menu.pack()

        # Package Name Entry
        self.package_name_entry = tk.Entry(self.widget_frame, textvariable=self.package_name, fg="grey")
        self.package_name_entry.bind("<FocusIn>", self.clear_entry)
        self.package_name_entry.bind("<FocusOut>", self.restore_placeholder)
        self.package_name_entry.pack()

        # Commit Button
        self.commit_button = tk.Button(self.widget_frame, text="Commit", command=self.print_package_name_and_save)
        self.commit_button.pack()
        
        # Committed Package Name Display
        self.committed_package_label = tk.Label(self.widget_frame, text="Committed Package Name:")
        self.committed_package_label.pack()
        self.committed_package_display = tk.Label(self.widget_frame, textvariable=self.committed_package)
        self.committed_package_display.pack()

        # Selected Files
        self.selected_files_label = tk.Label(self.widget_frame, text="Selected FIDL Files:")
        self.selected_files_label.pack()
        self.selected_files_text = tk.Text(self.widget_frame, height=3, width=50)
        self.selected_files_text.pack()
        self.select_files_button = tk.Button(self.widget_frame, text="Select FIDL Files", command=self.select_files)
        self.select_files_button.pack(pady=5)

        # Convert Buttons
        self.convert1_button = tk.Button(self.widget_frame, text="FIDL to AIDL", command=self.convert1)
        self.convert1_button.pack(padx=10, pady=5)
        self.convert2_button = tk.Button(self.widget_frame, text="FIDL to Communication Module Code", command=self.convert2)
        self.convert2_button.pack(padx=10, pady=5) #side="left",

        self.stdout_redirector = TextRedirector(self.monitor)

    def clear_entry(self, event):
        if self.package_name_entry.get() == "Write your Java package name":
            self.package_name_entry.delete(0, tk.END)
            self.package_name_entry.config(fg="black")

    def restore_placeholder(self, event):
        if not self.package_name_entry.get():
            self.package_name_entry.config(fg="grey")
            self.package_name_entry.insert(0, "Write your Java package name")

    def clear_arxml_entry(self, event):
        if self.arxml_package_name_entry.get() == "Write your FIDL package name":
            self.arxml_package_name_entry.delete(0, tk.END)
            self.arxml_package_name_entry.config(fg="black")

    def restore_arxml_placeholder(self, event):
        if not self.arxml_package_name_entry.get():
            self.arxml_package_name_entry.config(fg="grey")
            self.arxml_package_name_entry.insert(0, "Write your FIDL package name")

    def print_arxml_package_name_and_save(self):
        package_name = self.arxml_package_name.get()
        # Validate the package name format
        if self.validate_package_name(package_name):
            self.committed_arxml_package.set(package_name)  # Save the committed ARXML package name
        else:
            messagebox.showerror("Error", "Invalid ARXML package name format")

    def print_package_name_and_save(self):
        package_name = self.package_name.get()
        # Validate the package name format
        if self.validate_package_name(package_name):
            self.committed_package.set(package_name)  # Save the committed package name
        else:
            messagebox.showerror("Error", "Invalid package name format")

    def validate_package_name(self, package_name):
        # Validate package name format
        if not package_name:
            return False
        # if not package_name.replace(".", "").isalpha():
        #     return False
        if not re.match(r'^[A-Za-z0-9.]+$', package_name):
            return False
        if package_name.endswith("."):
            return False
        return True

    def select_output_dir(self):
        self.output_dir = filedialog.askdirectory()
        self.output_dir_text.delete(1.0, tk.END)
        self.output_dir_text.insert(tk.END, self.output_dir)

    def select_files(self):
        self.selected_files = filedialog.askopenfilenames(filetypes=[("FIDL Files", "*.fidl")])
        self.selected_files_text.delete(1.0, tk.END)
        for file in self.selected_files:
            self.selected_files_text.insert(tk.END, f"{file}\n")

    def select_arxml_files(self):
        self.selected_arxml_files = filedialog.askopenfilenames(filetypes=[("ARXML Files", "*.arxml")])
        self.selected_arxml_files_text.delete(1.0, tk.END)
        for file in self.selected_arxml_files:
            self.selected_arxml_files_text.insert(tk.END, f"{file}\n")

    # FIDL to AIDL conversion
    def convert1(self):
        if not self.selected_files or not self.committed_package.get():
            messagebox.showerror("Error", "File not selected or package name not given")
        else:
            # Call Convert1 function with required parameters
            self.monitor.configure(state="normal")
            self.monitor.insert(tk.END, "Converting FIDL to AIDL.\n")
            self.monitor.configure(state="disabled")
            sys.stdout = self.stdout_redirector
            parser = argparse.ArgumentParser(description="Covert FIDL to AIDL")
            parser.add_argument(
                "-V", "--jni_version", dest="jniversion", action="store", help="Version of the JNI.", required=False
            )
            parser.add_argument(
                "-J", "--packagejava", dest="packagejava", action = "store", help="Package name of Java", required=False
            )
            parser.add_argument(
                "-O", "--output", dest="output_dir", action="store", help="Output directory.", required=False, default='outputs'
            )
            parser.add_argument(
            "-I", "--import", dest="import_dirs", metavar="import_dir", action="append", help="Model import directories."
            )
            parser.add_argument(
            "fidl", nargs="+", help="Input FIDL file."
            )
            
            parser.jniversion = self.version.get()
            parser.packagejava = self.package_name.get()
            parser.output_dir = self.output_dir
            parser.fidl = self.selected_files
            parser.import_dirs = None
            
            fidl.main(parser,0)
            self.monitor.configure(state="normal")
            self.monitor.configure(state="disabled")

    # FIDL to Communication Module Code generation
    def convert2(self):
        if not self.selected_files or not self.committed_package.get():
            messagebox.showerror("Error", "File not selected or package name not given")
        else:
            # Call Convert2 function with required parameters
            self.monitor.configure(state="normal")
            self.monitor.insert(tk.END, "Converting FIDL to Communication Module Codes.\n")
            #self.monitor.insert(tk.END, self.version.get() + "\n") #, self.package_name.get(), self.output_dir
            self.monitor.configure(state="disabled")
            sys.stdout = self.stdout_redirector
            
            parser = argparse.ArgumentParser(description="Covert FIDL to Module Codes")
            parser.add_argument(
                "-V", "--jni_version", dest="jniversion", action="store", help="Version of the JNI.", required=False
            )
            parser.add_argument(
                "-J", "--packagejava", dest="packagejava", action = "store", help="Package name of Java", required=False
            )
            parser.add_argument(
                "-O", "--output", dest="output_dir", action="store", help="Output directory.", required=False, default='outputs'
            )
            parser.add_argument(
            "-I", "--import", dest="import_dirs", metavar="import_dir", action="append", help="Model import directories."
            )
            parser.add_argument(
            "fidl", nargs="+", help="Input FIDL file."
            )
            
            parser.jniversion = self.version.get()
            parser.packagejava = self.package_name.get()
            parser.output_dir = self.output_dir
            parser.fidl = self.selected_files
            parser.import_dirs = None
            
            fidl.main(parser,1)
            self.monitor.configure(state="normal")
            self.monitor.configure(state="disabled")
    
    # ARXML to FIDL conversion
    def convert3(self):
        if not self.selected_arxml_files or not self.committed_arxml_package.get():
            messagebox.showerror("Error", "File not selected or package name not given")
        else:
            # Call Convert2 function with required parameters
            self.monitor.configure(state="normal")
            self.monitor.insert(tk.END, "Converting ARXML to FIDL and FDEPL.\n")
            #self.monitor.insert(tk.END, self.version.get() + "\n") #, self.package_name.get(), self.output_dir
            self.monitor.configure(state="disabled")
            sys.stdout = self.stdout_redirector
            
            parser = argparse.ArgumentParser(description="Covert ARXML to FIDL and FDEPL")
            parser.add_argument(
                "-P", "--package", dest="package", action="store", help = "Use this option if you want to specify package of the FIDLs and FDEPLs", required=False
            )
            parser.add_argument(
                "-O", "--output", dest="output_dir", action="store", help="Output directory.", required=False, default='outputs'
            )
            parser.add_argument(
                "arxml", nargs="+", help="Input ARXML file(s)"
            )
            
            parser.package = self.arxml_package_name.get()
            parser.output_dir = self.output_dir
            parser.arxml = self.selected_arxml_files
            
            arxml.main(parser)
            self.monitor.configure(state="normal")
            self.monitor.configure(state="disabled")
            
def parse_command_line():
    parser = argparse.ArgumentParser(
        description="Behavioral cloning model trainer.")
    parser.add_argument(
        "-C", "--CLI",dest="cli", action="store_true", help="Use this option to run the tool as CLI"
    )
        
    return parser


def main():
    args = parse_command_line
    # if not args.cli:
    app = GUIApp()    
    app.mainloop()

if __name__ == "__main__":
    main()
