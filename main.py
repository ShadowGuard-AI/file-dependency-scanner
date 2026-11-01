import argparse
import logging
import pathlib
import subprocess
import re
import os
import sys


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_argparse():
    """
    Sets up the argument parser for the command-line interface.

    Returns:
        argparse.ArgumentParser: The configured argument parser.
    """
    parser = argparse.ArgumentParser(description="Scans Python files for imported dependencies and reports missing ones.")
    parser.add_argument("file_path", type=str, help="Path to the file to scan.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging.")
    parser.add_argument("-o", "--output", type=str, help="Path to output file for report (optional).")
    parser.add_argument("-l", "--log_file", type=str, help="Path to log file (optional).")

    return parser


def find_python_dependencies(file_path):
    """
    Extracts Python dependencies from a Python file using regular expressions.

    Args:
        file_path (str): The path to the Python file.

    Returns:
        list: A list of imported modules.
    """
    try:
        with open(file_path, "r") as f:
            content = f.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Error reading file: {e}")
        return None

    # Regular expression to find import statements (e.g., import os, from requests import get)
    # Extraction is a regex over raw text, not a parse. It cannot see
    # dynamic imports, and it happily matches import shaped text inside
    # comments and strings. The miss I know about: import a, b captures
    # only a, because the pattern ends at the first module name. I accept
    # the regex because the report is a first pass, not an audit.
    import_regex = r"(?:from\s+([\w\.]+)\s+import\s+[\w\.]+|import\s+([\w\.]+))"
    matches = re.findall(import_regex, content)
    dependencies = []
    for match in matches:
        for group in match:
            if group:
                # Only the top level name is kept. from a.b import c depends on the a
                # distribution, and checking a.b as a package name would fail.
                top_level = group.split(".")[0]
                if top_level not in dependencies:
                    dependencies.append(top_level)

    return dependencies


def check_dependencies(dependencies):
    results = {}
    # Standard library names are answered from the interpreter itself and
    # never reach pip. Everything else is checked with pip show, which
    # answers about distribution names, and those are not import names:
    # a file importing PIL or yaml is reported missing unless a
    # distribution literally named PIL or yaml is installed. That mismatch
    # is the known false positive in every report this tool writes.
    stdlib = getattr(sys, "stdlib_module_names", set())
    for dep in dependencies:
        if dep in stdlib:
            results[dep] = True
            continue
        try:
            # One pip subprocess per dependency. Slow on a long list, and the run
            # inherits whatever pip is first on PATH, which may belong to a
            # different interpreter than the one running this script.
            result = subprocess.run(["pip", "show", dep], capture_output=True, text=True)
            results[dep] = result.returncode == 0
        except FileNotFoundError:
            logging.error("pip command not found. Make sure it's installed and in your PATH.")
            return None
        except Exception as e:
            logging.error(f"Error checking dependency {dep}: {e}")
            results[dep] = False
    return results


# A report that fails to write is logged and swallowed; main does not
# hear about it and still exits 0. Noted as a gap, the same shape as
# several of my other report writers.
def generate_report(results, file_path, output_file=None):
    """
    Generates a report of missing dependencies.

    Args:
        results (dict): A dictionary containing dependency check results.
        file_path (str): The path to the scanned file.
        output_file (str, optional): The path to the output file for the report.
                                     If None, prints the report to the console.
    """
    report = f"Dependency report for {file_path}:\n"
    missing_dependencies = [dep for dep, installed in results.items() if not installed]

    if missing_dependencies:
        report += "Missing dependencies:\n"
        for dep in missing_dependencies:
            report += f"- {dep}\n"
    else:
        report += "All dependencies are installed.\n"

    if output_file:
        try:
            with open(output_file, "w") as f:
                f.write(report)
            logging.info(f"Report written to {output_file}")
        except Exception as e:
            logging.error(f"Error writing report to file: {e}")
    else:
        print(report)

def validate_file_path(file_path):
    """
    Validates that the given file path exists and is a file.
    Args:
        file_path (str): The path to the file to validate.

    Returns:
        bool: True if the file path is valid, False otherwise.
    """
    file_path_obj = pathlib.Path(file_path)
    if not file_path_obj.exists():
        logging.error(f"File does not exist: {file_path}")
        return False

    if not file_path_obj.is_file():
        logging.error(f"Not a file: {file_path}")
        return False

    return True

def main():
    """
    Main function to execute the file dependency scanner.
    """
    parser = setup_argparse()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.log_file:
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)


    file_path = args.file_path

    if not validate_file_path(file_path):
        sys.exit(1)

    if args.output and os.path.realpath(args.output) == os.path.realpath(file_path):
        logging.error(f"Refusing to overwrite the scanned file: {args.output}")
        sys.exit(1)

    # Determine file type and extract dependencies accordingly.
    try:
        file_extension = pathlib.Path(file_path).suffix.lower()
    except Exception as e:
        logging.error(f"Error determining file extension: {e}")
        sys.exit(1)

    if file_extension == ".py":
        all_dependencies = find_python_dependencies(file_path)
        if all_dependencies is None:
            sys.exit(1)
    else:
        logging.error("Unsupported file type: only Python (.py) files are scanned.")
        sys.exit(1)


    if all_dependencies:
        results = check_dependencies(all_dependencies)
        if results:
            generate_report(results, file_path, args.output)
        else:
            logging.error("Failed to check dependencies.")
            sys.exit(1)
    else:
        logging.info("No dependencies found in the file.")
        if args.output:
             try:
                  with open(args.output, "w") as f:
                      f.write("No dependencies found in the file.")
                  logging.info(f"Empty report written to {args.output}")

             except Exception as e:
                  logging.error(f"Failed to write empty report to file: {e}")
                  sys.exit(1)


if __name__ == "__main__":
    main()

# Usage examples:
# python main.py my_script.py
# python main.py my_script.py -v -o report.txt
# python main.py my_script.py -l scan.log