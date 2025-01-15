# a friendly utility script to grab all the code into single text file.

import os

# Define the output file name
OUTPUT_FILE = "combined_code.txt"

# List of folders and files to include
TARGETS = [
    "my_digital_being/framework",
    "my_digital_being/skills",
    "my_digital_being/tools",
    "my_digital_being/activities",
    "my_digital_being/static",
    "my_digital_being/config",
    "my_digital_being/server.py",
]


def combine_code():
    with open(OUTPUT_FILE, "w") as output_file:
        for target in TARGETS:
            if os.path.isdir(target):
                for filename in sorted(os.listdir(target)):
                    filepath = os.path.join(target, filename)
                    # Skip non-Python files and files starting with '__'
                    if filename.endswith(".py") and not filename.startswith("__"):
                        add_file_to_output(filepath, output_file)
            elif os.path.isfile(target):  # If it's a single file
                add_file_to_output(target, output_file)
            else:
                print(f"Warning: {target} is neither a directory nor a file.")
    print(f"Combined code saved to {OUTPUT_FILE}")


def add_file_to_output(filepath, output_file):
    with open(filepath, "r") as f:
        content = f.read()
    relative_path = os.path.relpath(filepath)
    header = f"\n##### {relative_path} #####\n"
    output_file.write(header + content + "\n")


if __name__ == "__main__":
    combine_code()
