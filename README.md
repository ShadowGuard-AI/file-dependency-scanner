![Banner](banner.png)

# file-dependency-scanner
Scans a Python file for its imported dependencies and reports the ones that are missing. Standard library modules are checked against the Python standard library name set first, and other names are checked with pip. - Focused on File operations and analysis

## Install
`git clone https://github.com/ShadowGuardAI/file-dependency-scanner`

## Usage
`./file-dependency-scanner [params]`

## Parameters
- `-h`: Show help message and exit
- `file_path`: Path to the Python file to scan.
- `-v`: Enable verbose logging.
- `-o`: Path to output file for the report (optional). It must not be the scanned file; a run whose output path resolves to the scanned file is refused at exit 1.
- `-l`: Path to log file (optional).

## Notes
- This tool checks Python imports only. It does not scan for required executables, and it does not use apt or any system package manager.
- A `from` import is reported as its top level package, the name the import system resolves (for example, `from xml.etree import ElementTree` is reported as `xml`).
- No version is read or compared, so the report says nothing about whether a package is outdated. It reports missing packages only.

## License
Copyright (c) ShadowGuardAI
