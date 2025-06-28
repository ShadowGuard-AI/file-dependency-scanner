import argparse
import logging
import pathlib
import subprocess
import re
import sys


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_argparse():
    """
    Sets up the argument parser for the command-line interface.

    Returns:
        argparse.ArgumentParser: The configured argument parser.
    """
    parser = argparse.ArgumentParser(description="Scans files for dependencies and reports missing or outdated ones.")
    parser.add_argument("file_path", type=str, help="Path to the file to scan.")
    parser.add_argument("-r", "--resolver", type=str, default="pip", choices=["pip", "apt"],
                        help="Dependency resolution strategy (pip or apt). Defaults to pip.")
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
    import_regex = r"(?:from\s+(\w+)\s+import\s+\w+|import\s+(\w+))"
    matches = re.findall(import_regex, content)
    dependencies = []
    for match in matches:
        # The regex captures both "from ... import ..." and "import ..." styles.
        # We iterate and add the non-empty groups to the list of dependencies.
        for group in match:
            if group:  # Avoid adding empty strings
                dependencies.append(group)

    return dependencies


def find_executable_dependencies(file_path):
    """
    Scans a file for executable dependencies using regular expressions.
    This function searches for calls to subprocess or os.system that
    execute other programs.

    Args:
        file_path (str): The path to the file.

    Returns:
        list: A list of executable dependencies found in the file.
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

    executable_regex = r"(?:subprocess\.run|subprocess\.Popen|os\.system)\((.+?)\)"
    matches = re.findall(executable_regex, content)
    executables = []
    for match in matches:
        # Try to clean up the matched string to extract the command.
        cleaned_match = match.strip().strip("'\"").split()[0]
        executables.append(cleaned_match)

    return executables


def check_dependencies(dependencies, resolver):
    """
    Checks if the given dependencies are installed using the specified resolver.

    Args:
        dependencies (list): A list of dependency names.
        resolver (str): The dependency resolver to use (e.g., "pip" or "apt").

    Returns:
        dict: A dictionary where keys are dependency names and values are booleans
              indicating whether the dependency is installed (True) or not (False).
    """
    results = {}
    for dep in dependencies:
        try:
            if resolver == "pip":
                # Use pip show to check if the package is installed
                result = subprocess.run(["pip", "show", dep], capture_output=True, text=True)
                results[dep] = result.returncode == 0  # pip show returns 0 if the package is installed
            elif resolver == "apt":
                # Use dpkg -s to check if the package is installed
                result = subprocess.run(["dpkg", "-s", dep], capture_output=True, text=True)
                results[dep] = result.returncode == 0
            else:
                logging.error(f"Invalid resolver: {resolver}")
                return None  # Or raise an exception
        except FileNotFoundError:
            logging.error(f"{resolver} command not found. Make sure it's installed and in your PATH.")
            return None
        except Exception as e:
            logging.error(f"Error checking dependency {dep}: {e}")
            results[dep] = False  # Assume not installed if there's an error

    return results


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

    # Determine file type and extract dependencies accordingly.
    try:
        file_extension = pathlib.Path(file_path).suffix.lower()
    except Exception as e:
        logging.error(f"Error determining file extension: {e}")
        sys.exit(1)

    if file_extension == ".py":
        dependencies = find_python_dependencies(file_path)
        executable_dependencies = find_executable_dependencies(file_path)
        if dependencies is None or executable_dependencies is None:
             sys.exit(1)  # Exit if there was an error finding dependencies
        all_dependencies = dependencies + executable_dependencies

    else:
        logging.warning("Unsupported file type.  Scanning for executable dependencies only.")
        all_dependencies = find_executable_dependencies(file_path)
        if all_dependencies is None:
            sys.exit(1)


    if all_dependencies:
        results = check_dependencies(all_dependencies, args.resolver)
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
# python main.py my_script.py -r apt
# python main.py my_script.py -v -o report.txt
# python main.py config.txt -l scan.log