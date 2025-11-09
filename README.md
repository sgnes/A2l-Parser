# PyA2lModel
A comprehensive Python library for parsing and modeling ASAP2 (.a2l) files with bidirectional conversion capabilities. This library extracts A2L content into structured Python data models and supports exporting models back to A2L format.

## Features

### Parsing Capabilities
- **Project and Module** information extraction
- **XCPplus Protocol Layer** configuration parsing
- **DAQ (Data Acquisition)** configuration with event handling
- **XCP_ON_CAN** transport layer parameters (including CAN FD)
- **Memory segments** with page information
- **AXIS_PTS** (calibration axes) parsing
- **MEASUREMENTS** data extraction
- **CHARACTERISTICS** for calibration parameters
- **RECORD_LAYOUTs** for data structure definitions
- **COMPU_METHODs and COMPU_VTABs** for conversion methods
- **GROUPs and FUNCTIONs** with local measurements and references

### Export Capabilities  
- **Bidirectional Conversion**: Parse A2L files to Python objects and export back to A2L format
- **Programmatic Modification**: Edit parsed data and regenerate A2L files
- **Customizable Output**: Control indentation and formatting
- **Complete Round-trip**: Parse → Modify → Export workflow

## Installation

Ensure Python 3.7+ is installed.

```bash
pip install pya2lmodel
```

## Basic Usage

### Parsing A2L Files

```python
from a2lparser import A2LParser, A2LModel

# Parse an A2L file
parser = A2LParser()
model = parser.parse_file("your_file.a2l")

# Access parsed data
print(f"Project: {model.project_name}")
print(f"Module: {model.module_name}")
print(f"Measurements: {len(model.measurements)}")
print(f"Characteristics: {len(model.characteristics)}")
print(f"DAQ events: {len(model.daq_events)}")

# Export to JSON-like dict
model_dict = model.to_dict()
import json
print(json.dumps(model_dict, indent=2))
```

### Exporting to A2L Format

```python
# Export model to A2L string
a2l_content = model.to_a2l()
print("Generated A2L content:")
print(a2l_content[:500])  # Show first 500 characters

# Export directly to file
model.to_file("exported_file.a2l")

# Customize indentation
model.to_file("exported_file_spaces.a2l", indent="    ")
```

### Advanced Usage: Modify and Re-export

```python
# Parse existing file
model = parser.parse_file("original.a2l")

# Modify data
if model.measurements:
    model.measurements[0].description = "Modified measurement description"

# Add new characteristics
from a2lparser.a2l_model import Characteristic
new_char = Characteristic(
    name="NEW_CALIBRATION",
    description="New calibration parameter",
    char_type="VALUE",
    address=0x1000,
    record_layout="RL_1D",
    compu_method="CM_IDENTICAL",
    lower_limit=0.0,
    upper_limit=100.0
)
model.characteristics.append(new_char)

# Export modified model
model.to_file("modified.a2l")
```

## API Reference

### A2LParser Class
- `parse_file(path: str | Path) -> A2LModel`: Parse A2L file from path
- `parse_text(text: str) -> A2LModel`: Parse A2L content from string

### A2LModel Class
- `to_dict() -> Dict[str, Any]`: Convert model to JSON-like dictionary
- `to_a2l(indent: str = "\t") -> str`: Export to A2L format string
- `to_file(filepath: str, indent: str = "\t") -> None`: Export to A2L file

### Data Classes
- `ProtocolLayer`, `DaqConfig`, `DaqEvent`
- `XcpOnCanConfig`, `XcpOnCanFdConfig`
- `MemorySegment`, `SegmentInfo`, `PageInfo`
- `AxisPts`, `Measurement`, `Characteristic`
- `CompuMethod`, `CompuVTab`
- `RecordLayout`, `Group`, `Function`

## Export Features

### Supported Blocks in Export
- Complete PROJECT and MODULE structure
- XCPplus protocol layer configuration
- DAQ configuration with events
- Memory segments and pages
- AXIS_PTS, MEASUREMENT, and CHARACTERISTIC blocks
- COMPU_METHODs and COMPU_VTABs
- RECORD_LAYOUTs, GROUPs, and FUNCTIONs

### File Format Control
- **Line endings**: Uses CRLF (

) for Windows compatibility
- **Indentation**: Configurable (default: tab)
- **Encoding**: UTF-8 with proper error handling
- **Structure**: Maintains ASAP2 version compatibility

## Example Output

```
Project: MyECUProject
Module: ECU_Module
Protocol Layer parsed: True
DAQ events: 3
XCP on CAN parsed: True
Memory segments: 5
AXIS_PTS: 12
Measurements: 150
Characteristics: 80
Record layouts: 8

Generated A2L preview:
ASAP2_VERSION 1 70

/begin PROJECT "MyECUProject" ""
	/begin HEADER ""
		VERSION "1"
		PROJECT_NO No
	/end HEADER
	/begin MODULE "ECU_Module" ""
	/begin A2ML
	/end A2ML
...
```

## Limitations
- This is a minimal parser and does not support full ASAP2 grammar
- Tailored to specific A2L dialects - may require adjustments for variants
- Large or complex A2L files may need optimization

## License
MIT

## Contact
For issues or improvements, please raise an issue or contribute via pull requests.
