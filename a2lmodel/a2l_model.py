#!/usr/bin/env python3
"""
A minimal A2L parser tailored for the provided file.
Parses and holds:
- Project and Module
- XCPplus → PROTOCOL_LAYER
- DAQ (including events)
- XCP_ON_CAN (transport layer parameters, including CAN FD)
- Memory segments
- AXIS_PTS (calibration axes)
- MEASUREMENTs
- CHARACTERISTICs  <-- NEW
- RECORD_LAYOUTs
- COMPU_METHODs and COMPU_VTABs
- GROUPs and FUNCTIONs (loc/refs)

Note: This is not a full ASAP2 grammar parser. It is designed to parse the specific structure
in the user-provided A2L. You may need to adjust handlers to your dialect/variants.

Usage:
    model = A2LParser().parse_file("your.a2l")
    print(model.project_name, model.module_name)
    print(f"Characteristics: {len(model.characteristics)}")
    print(f"DAQ events: {len(model.daq_events)}")
    print(f"AXIS_PTS: {len(model.axis_pts)}")
    print(f"Measurements: {len(model.measurements)}")
    # Export to JSON-like dict
    import json
    print(json.dumps(model.to_dict(), indent=2))
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, Tuple
import re
import shlex
import sys
from pathlib import Path


# --------------------------
# Utilities
# --------------------------

def strip_block_comments(text: str) -> str:
    """
    Remove C-style block comments from A2L text.
    
    Args:
        text: A2L file content as a string
        
    Returns:
        Text with C-style /* ... */ comments removed
        
    Example:
        >>> strip_block_comments('text /* comment */ text')
        'text  text'
    """
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)

def to_int(token: str) -> int | None:
    """
    Convert a string token to an integer, handling hexadecimal format.
    
    Args:
        token: String token to convert to integer
        
    Returns:
        Integer value if conversion succeeds, None otherwise
        
    Example:
        >>> to_int("123")
        123
        >>> to_int("0x7B")
        123
        >>> to_int("abc")
        None
    """
    try:
        if token.lower().startswith("0x"):
            return int(token, 16)
        return int(token)
    except Exception:
        return None

def to_float(token: str) -> float | None:
    """
    Convert a string token to a float.
    
    Args:
        token: String token to convert to float
        
    Returns:
        Float value if conversion succeeds, None otherwise
        
    Example:
        >>> to_float("123.45")
        123.45
        >>> to_float("abc")
        None
    """
    try:
        return float(token)
    except Exception:
        return None

def tokenize_line(line: str) -> list[str]:
    """
    Tokenize a line of A2L text, handling quoted strings properly.
    
    Args:
        line: A single line of A2L text
        
    Returns:
        List of tokens with quoted strings preserved as single tokens
        
    Example:
        >>> tokenize_line('NAME "Long Description" VALUE')
        ['NAME', 'Long Description', 'VALUE']
    """
    return shlex.split(line, posix=True)

def unquote(s: str) -> str:
    """
    Remove surrounding quotes from a string if present.
    
    Args:
        s: String that may be surrounded by single or double quotes
        
    Returns:
        String without surrounding quotes, or original string if no quotes are present
        
    Example:
        >>> unquote('"quoted"')
        'quoted'
        >>> unquote("'single'")
        'single'
        >>> unquote('no_quotes')
        'no_quotes'
    """
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    return s


# --------------------------
# Block tree representation
# --------------------------

@dataclass
class A2LBlock:
    """
    Represents a single A2L block with hierarchical structure.
    
    Attributes:
        name: The name of the A2L block (e.g., "PROJECT", "MODULE", "MEASUREMENT")
        args: List of arguments passed to the block in the /begin statement
        lines: Raw text lines contained within this block
        children: Child blocks nested within this block
    """
    name: str
    args: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)  # raw lines inside this block (including children)
    children: list["A2LBlock"] = field(default_factory=list)

    def get_children(self, name: str) -> list[A2LBlock]:
        """
        Get all child blocks with the specified name.
        
        Args:
            name: Name of the child blocks to retrieve (case-insensitive)
            
        Returns:
            List of matching child blocks
        """
        return [c for c in self.children if c.name.upper() == name.upper()]

    def get_first_child(self, name: str) -> A2LBlock | None:
        """
        Get the first child block with the specified name.
        
        Args:
            name: Name of the child block to retrieve (case-insensitive)
            
        Returns:
            First matching child block, or None if not found
        """
        kids = self.get_children(name)
        return kids[0] if kids else None


# --------------------------
# Dataclasses for structured model
# --------------------------

@dataclass
class ProtocolLayer:
    """
    XCP protocol layer configuration parameters.
    
    Attributes:
        version: Protocol version number
        timing_values: List of timing parameters (T1-T7)
        max_cto: Maximum Command Transfer Object size
        max_dto: Maximum Data Transfer Object size
        byte_order: Byte order (e.g., "MSB_LAST", "MSB_FIRST")
        address_granularity: Address granularity (BYTE/WORD/DWORD)
        optional_cmds: List of optional XCP commands
        communication_mode: Communication mode supported
        master_max_bs: Master maximum block size
        master_min_st: Master minimum separation time
        raw: Raw A2L text lines for this block
    """
    version: int | None = None
    timing_values: list[int] = field(default_factory=list)  # T1..T7 etc
    max_cto: int | None = None
    max_dto: int | None = None
    byte_order: str | None = None
    address_granularity: str | None = None
    optional_cmds: list[str] = field(default_factory=list)
    communication_mode: str | None = None
    master_max_bs: int | None = None
    master_min_st: int | None = None
    raw: list[str] = field(default_factory=list)

@dataclass
class DaqEvent:
    """
    Represents a DAQ event configuration.
    
    Attributes:
        name: Event name
        short_name: Short event name
        event_channel_number: Event channel number
        type: Event type (DAQ/STIM/DAQ_STIM)
        max_daq_list: Maximum DAQ list size
        cycle: Cycle time
        time_unit: Time unit (e.g., 1 = 1ms, 2 = 10ms)
        priority: Event priority
        raw: Raw A2L text lines for this block
    """
    name: str
    short_name: str | None
    event_channel_number: int | None
    type: str | None  # DAQ/STIM/DAQ_STIM
    max_daq_list: int | None
    cycle: int | None
    time_unit: int | None
    priority: int | None
    raw: list[str] = field(default_factory=list)

@dataclass
class DaqConfig:
    """
    DAQ (Data Acquisition) configuration parameters.
    
    Attributes:
        mode: DAQ mode (DYNAMIC/STATIC)
        max_daq: Maximum number of DAQ lists
        max_event_channel: Maximum number of event channels
        min_daq: Minimum number of DAQ lists
        identification_field_type: Identifier field type
        odt_entry_granularity_daq: Granularity of ODT entries for DAQ
        max_odt_entry_size_daq: Maximum ODT entry size for DAQ
        overload_indication: Overload indication method
        stim_granularity: Stimulation granularity
        max_odt_entry_size_stim: Maximum ODT entry size for stimulation
        bit_stim_supported: Whether bit stimulation is supported
        events: List of DAQ events
        raw: Raw A2L text lines for this block
    """
    mode: str | None = None  # DYNAMIC/STATIC
    max_daq: int | None = None
    max_event_channel: int | None = None
    min_daq: int | None = None
    identification_field_type: str | None = None
    odt_entry_granularity_daq: str | None = None
    max_odt_entry_size_daq: int | None = None
    overload_indication: str | None = None
    stim_granularity: str | None = None
    max_odt_entry_size_stim: int | None = None
    bit_stim_supported: bool = False
    events: list[DaqEvent] = field(default_factory=list)
    raw: list[str] = field(default_factory=list)

@dataclass
class XcpOnCanFdConfig:
    """
    XCP over CAN FD configuration parameters.
    
    Attributes:
        max_dlc: Maximum Data Length Code
        data_transfer_baudrate: Data transfer baudrate
        sample_point: Sample point percentage
        btl_cycles: Bit timing cycles
        sjw: Synchronization jump width
        sync_edge: Synchronization edge
        max_dlc_required: Whether maximum DLC is required
        secondary_sample_point: Secondary sample point
        tdc: Transceiver delay compensation
        raw: Raw A2L text lines for this block
    """
    max_dlc: int | None = None
    data_transfer_baudrate: int | None = None
    sample_point: int | None = None
    btl_cycles: int | None = None
    sjw: int | None = None
    sync_edge: str | None = None
    max_dlc_required: bool = False
    secondary_sample_point: int | None = None
    tdc: str | None = None
    raw: list[str] = field(default_factory=list)

@dataclass
class XcpOnCanConfig:
    """
    XCP over CAN configuration parameters.
    
    Attributes:
        version: Protocol version
        can_id_broadcast: CAN ID for broadcast messages
        can_id_master: CAN ID for master messages
        can_id_slave: CAN ID for slave messages
        can_id_get_daq_clock_multicast: CAN ID for DAQ clock multicast
        baudrate: Communication baudrate
        sample_point: Sample point percentage
        sample_rate: Sample rate setting
        btl_cycles: Bit timing cycles
        sjw: Synchronization jump width
        sync_edge: Synchronization edge
        max_dlc_required: Whether maximum DLC is required
        max_bus_load: Maximum bus load percentage
        can_fd: CAN FD specific configuration
        raw: Raw A2L text lines for this block
    """
    version: int | None = None
    can_id_broadcast: int | None = None
    can_id_master: int | None = None
    can_id_slave: int | None = None
    can_id_get_daq_clock_multicast: int | None = None
    baudrate: int | None = None
    sample_point: int | None = None
    sample_rate: str | None = None
    btl_cycles: int | None = None
    sjw: int | None = None
    sync_edge: str | None = None
    max_dlc_required: bool = False
    max_bus_load: int | None = None
    can_fd: XcpOnCanFdConfig | None = None
    raw: list[str] = field(default_factory=list)

@dataclass
class PageInfo:
    """
    Memory page information for segmented memory.
    
    Attributes:
        page_number: Page number identifier
        ecu_access: ECU access method
        xcp_read_access: XCP read access permission
        xcp_write_access: XCP write access permission
    """
    page_number: int | None
    ecu_access: str | None
    xcp_read_access: str | None
    xcp_write_access: str | None

@dataclass
class SegmentInfo:
    """
    Memory segment information including pages and protection parameters.
    
    Attributes:
        segment_number: Segment identifier number
        num_pages: Number of pages in this segment
        address_extension: Address extension value
        compression_method: Compression method identifier
        encryption_method: Encryption method identifier
        checksum_type: Type of checksum used for this segment
        pages: List of page information objects within this segment
        raw: Raw A2L text lines for this block
    """
    segment_number: int | None = None
    num_pages: int | None = None
    address_extension: int | None = None
    compression_method: int | None = None
    encryption_method: int | None = None
    checksum_type: str | None = None
    pages: list[PageInfo] = field(default_factory=list)
    raw: list[str] = field(default_factory=list)

@dataclass
class MemorySegment:
    """
    Represents a memory segment with address, size, and protection attributes.
    
    Attributes:
        name: Segment name identifier
        long_identifier: Descriptive name for the segment
        class_type: Memory class type (CODE/DATA/RESERVED/OFFLINE_DATA/CALIBRATION_VARIABLES)
        memory_type: Physical memory type (FLASH/ROM/RAM)
        address: Starting address of the segment
        size: Size of the segment in bytes
        attributes: List of additional segment attributes
        segment_info: Detailed segment information including pages
        raw: Raw A2L text lines for this block
    """
    name: str
    long_identifier: str | None
    class_type: str | None  # CODE/DATA/RESERVED/OFFLINE_DATA/CALIBRATION_VARIABLES etc
    memory_type: str | None  # FLASH/ROM/RAM
    address: int | None
    size: int | None
    attributes: list[str] = field(default_factory=list)  # trailing -1s etc as raw
    segment_info: SegmentInfo | None = None
    raw: list[str] = field(default_factory=list)

@dataclass
class AxisPts:
    """
    Represents axis points data structure for calibration curves.
    
    Attributes:
        name: Axis points name identifier
        description: Descriptive name for the axis points
        address: Memory address of the axis points data
        input_quantity: Input quantity reference
        record_layout: Record layout reference
        deposit: Deposit value for axis points
        compu_method: Computation method reference
        max_axis_points: Maximum number of axis points
        lower_limit: Lower limit of axis values
        upper_limit: Upper limit of axis values
        byte_order: Byte order specification
        format_str: Format string for display
        symbol_link: Symbol link reference with index
        raw: Raw A2L text lines for this block
    """
    name: str
    description: str
    address: int | None
    input_quantity: str | None
    record_layout: str | None
    deposit: int | None
    compu_method: str | None
    max_axis_points: int | None
    lower_limit: float | None
    upper_limit: float | None
    byte_order: str | None = None
    format_str: str | None = None
    symbol_link: tuple[str | None, int | None] | None = None
    raw: list[str] = field(default_factory=list)

@dataclass
class Measurement:
    """
    Represents a measurement (MEASUREMENT) element in the A2L file.
    
    Attributes:
        name: Measurement name identifier
        description: Descriptive name for the measurement
        datatype: Data type of the measurement
        compu_method: Computation method reference
        params: List of additional parameters
        ecu_address: ECU address of the measurement
        address: Memory address of the measurement
        lower_limit: Lower limit for the measurement value
        upper_limit: Upper limit for the measurement value
        symbol_link: Symbol link reference with index
        raw: Raw A2L text lines for this block
    """
    name: str
    description: str
    datatype: str
    compu_method: str
    params: list[str] = field(default_factory=list)
    ecu_address: int | None = None
    address: int | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    symbol_link: tuple[str | None, int | None] | None = None
    raw: list[str] = field(default_factory=list)

# NEW: Characteristic dataclass
@dataclass
class Characteristic:
    name: str
    description: str
    char_type: str
    address: int | None
    record_layout: str | None
    max_diff: float | None
    compu_method: str | None
    lower_limit: float | None
    upper_limit: float | None
    symbol_link: tuple[str | None, int | None] | None = None
    raw: list[str] = field(default_factory=list)

@dataclass
class CompuMethod:
    name: str
    description: str
    method_type: str  # e.g., RAT_FUNC
    format_str: str | None
    unit: str | None
    coeffs: list[float] = field(default_factory=list)
    raw: list[str] = field(default_factory=list)

@dataclass
class CompuVTab:
    name: str
    description: str
    tab_type: str  # TAB_VERB etc
    entries: list[tuple[int, str]] = field(default_factory=list)
    raw: list[str] = field(default_factory=list)

@dataclass
class RecordLayout:
    name: str
    entries: list[str] = field(default_factory=list)
    raw: list[str] = field(default_factory=list)

@dataclass
class Group:
    name: str
    description: str
    ref_measurements: list[str] = field(default_factory=list)
    raw: list[str] = field(default_factory=list)

@dataclass
class Function:
    name: str
    description: str
    loc_measurements: list[str] = field(default_factory=list)
    raw: list[str] = field(default_factory=list)

@dataclass
class A2LModel:
    """
    Complete A2L data model containing all parsed elements from an A2L file.
    
    This class represents the structured data extracted from an A2L file,
    including project information, module configuration, measurement data,
    characteristics, and various calibration parameters.
    """
    project_name: str | None = None
    module_name: str | None = None

    protocol_layer: ProtocolLayer | None = None
    daq: DaqConfig | None = None
    daq_events: list[DaqEvent] = field(default_factory=list)
    xcp_on_can: XcpOnCanConfig | None = None

    memory_segments: list[MemorySegment] = field(default_factory=list)
    axis_pts: list[AxisPts] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)
    characteristics: list[Characteristic] = field(default_factory=list)  # NEW
    compu_methods: list[CompuMethod] = field(default_factory=list)
    compu_vtabs: list[CompuVTab] = field(default_factory=list)
    record_layouts: list[RecordLayout] = field(default_factory=list)
    groups: list[Group] = field(default_factory=list)
    functions: list[Function] = field(default_factory=list)

    raw_blocks: list[A2LBlock] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def conv(obj: Any) -> Any:
            if hasattr(obj, "__dict__"):
                return asdict(obj)
            if isinstance(obj, list):
                return [conv(x) for x in obj]
            return obj
        result = conv(self)
        # Ensure we return a dict, not a list or other type
        if isinstance(result, dict):
            return result
        # If the result is not a dict (e.g., from incorrect structure), return empty dict
        return {}

    def to_a2l(self, indent: str = "\t") -> str:
        """Export the model to A2L file format.
        
        Args:
            indent: String to use for indentation (default is tab)
            
        Returns:
            A2L file content as a string
        """
        lines: list[str] = []
        
        # Add ASAP2 version header
        lines.append("ASAP2_VERSION 1 70")
        lines.append("")
        
        # Start PROJECT block
        project_name = self.project_name or "Untitled"
        lines.append(f"/begin PROJECT {project_name}\"\"")
        
        # Add HEADER block
        lines.append(f"{indent}/begin HEADER \"\"")
        lines.append(f"{indent}{indent}VERSION \"1\"")
        lines.append(f"{indent}{indent}PROJECT_NO No")
        lines.append(f"{indent}/end HEADER")
        
        # Start MODULE block
        module_name = self.module_name or project_name
        lines.append(f"{indent}/begin MODULE {module_name}\"\"")
        
        # Add A2ML block (simplified)
        lines.append(f"{indent}/begin A2ML")
        lines.append(f"{indent}/end A2ML")
        
        # Add protocol layer if available
        if self.protocol_layer:
            lines.append(f"{indent}/begin IF_DATA XCPplus")
            lines.append(f"{indent}{indent}/begin PROTOCOL_LAYER")
            if self.protocol_layer.version:
                lines.append(f"{indent}{indent}{indent}{self.protocol_layer.version}")
            for timing in self.protocol_layer.timing_values:
                lines.append(f"{indent}{indent}{indent}{timing}")
            if self.protocol_layer.max_cto:
                lines.append(f"{indent}{indent}{indent}{self.protocol_layer.max_cto}")
            if self.protocol_layer.max_dto:
                lines.append(f"{indent}{indent}{indent}{self.protocol_layer.max_dto}")
            if self.protocol_layer.byte_order:
                lines.append(f"{indent}{indent}{indent}{self.protocol_layer.byte_order}")
            if self.protocol_layer.address_granularity:
                lines.append(f"{indent}{indent}{indent}{self.protocol_layer.address_granularity}")
            lines.append(f"{indent}{indent}/end PROTOCOL_LAYER")
            lines.append(f"{indent}/end IF_DATA")
        
        # Add DAQ configuration
        if self.daq:
            lines.append(f"{indent}/begin IF_DATA XCPplus")
            lines.append(f"{indent}{indent}/begin DAQ")
            if self.daq.mode:
                lines.append(f"{indent}{indent}{indent}{self.daq.mode}")
            if self.daq.max_daq:
                lines.append(f"{indent}{indent}{indent}{self.daq.max_daq}")
            if self.daq.max_event_channel:
                lines.append(f"{indent}{indent}{indent}{self.daq.max_event_channel}")
            if self.daq.min_daq:
                lines.append(f"{indent}{indent}{indent}{self.daq.min_daq}")
            
            # Add DAQ events
            for event in self.daq_events:
                lines.append(f"{indent}{indent}{indent}/begin EVENT")
                lines.append(f"{indent}{indent}{indent}{indent}\"{event.name}\"")
                if event.short_name:
                    lines.append(f"{indent}{indent}{indent}{indent}\"{event.short_name}\"")
                if event.event_channel_number:
                    lines.append(f"{indent}{indent}{indent}{indent}{event.event_channel_number}")
                if event.type:
                    lines.append(f"{indent}{indent}{indent}{indent}{event.type}")
                if event.max_daq_list:
                    lines.append(f"{indent}{indent}{indent}{indent}{event.max_daq_list}")
                if event.cycle:
                    lines.append(f"{indent}{indent}{indent}{indent}{event.cycle}")
                if event.time_unit:
                    lines.append(f"{indent}{indent}{indent}{indent}{event.time_unit}")
                if event.priority:
                    lines.append(f"{indent}{indent}{indent}{indent}{event.priority}")
                lines.append(f"{indent}{indent}{indent}/end EVENT")
            
            lines.append(f"{indent}{indent}/end DAQ")
            lines.append(f"{indent}/end IF_DATA")
        
        # Add memory segments
        if self.memory_segments:
            lines.append(f"{indent}/begin MOD_PAR")
            for segment in self.memory_segments:
                lines.append(f"{indent}{indent}/begin MEMORY_SEGMENT {segment.name}")
                if segment.long_identifier:
                    lines.append(f"{indent}{indent}{indent}\"{segment.long_identifier}\"")
                if segment.class_type and segment.memory_type:
                    lines.append(f"{indent}{indent}{indent}{segment.class_type} {segment.memory_type}")
                if segment.address is not None and segment.size is not None:
                    lines.append(f"{indent}{indent}{indent}INTERN {hex(segment.address)} {hex(segment.size)}")
                lines.append(f"{indent}{indent}/end MEMORY_SEGMENT")
            lines.append(f"{indent}/end MOD_PAR")
        
        # Add AXIS_PTS
        for axis_pts in self.axis_pts:
            lines.append(f"{indent}/begin AXIS_PTS {axis_pts.name}")
            lines.append(f"{indent}{indent}\"{axis_pts.description}\"")
            if axis_pts.address is not None:
                lines.append(f"{indent}{indent}{hex(axis_pts.address)}")
            if axis_pts.input_quantity:
                lines.append(f"{indent}{indent}{axis_pts.input_quantity}")
            if axis_pts.record_layout:
                lines.append(f"{indent}{indent}{axis_pts.record_layout}")
            if axis_pts.deposit is not None:
                lines.append(f"{indent}{indent}{axis_pts.deposit}")
            if axis_pts.compu_method:
                lines.append(f"{indent}{indent}{axis_pts.compu_method}")
            if axis_pts.max_axis_points is not None:
                lines.append(f"{indent}{indent}{axis_pts.max_axis_points}")
            if axis_pts.lower_limit is not None:
                lines.append(f"{indent}{indent}{axis_pts.lower_limit}")
            if axis_pts.upper_limit is not None:
                lines.append(f"{indent}{indent}{axis_pts.upper_limit}")
            lines.append(f"{indent}/end AXIS_PTS")
        
        # Add MEASUREMENTs
        for measurement in self.measurements:
            lines.append(f"{indent}/begin MEASUREMENT {measurement.name}")
            lines.append(f"{indent}{indent}\"{measurement.description}\"")
            lines.append(f"{indent}{indent}{measurement.datatype}")
            lines.append(f"{indent}{indent}{measurement.compu_method}")
            if measurement.ecu_address is not None:
                lines.append(f"{indent}{indent}ECU_ADDRESS {hex(measurement.ecu_address)}")
            if measurement.lower_limit is not None and measurement.upper_limit is not None:
                lines.append(f"{indent}{indent}{measurement.lower_limit} {measurement.upper_limit}")
            lines.append(f"{indent}/end MEASUREMENT")
        
        # Add CHARACTERISTICs
        for characteristic in self.characteristics:
            lines.append(f"{indent}/begin CHARACTERISTIC {characteristic.name}")
            lines.append(f"{indent}{indent}\"{characteristic.description}\"")
            lines.append(f"{indent}{indent}{characteristic.char_type}")
            if characteristic.address is not None:
                lines.append(f"{indent}{indent}{hex(characteristic.address)}")
            if characteristic.record_layout:
                lines.append(f"{indent}{indent}{characteristic.record_layout}")
            if characteristic.max_diff is not None:
                lines.append(f"{indent}{indent}{characteristic.max_diff}")
            if characteristic.compu_method:
                lines.append(f"{indent}{indent}{characteristic.compu_method}")
            if characteristic.lower_limit is not None and characteristic.upper_limit is not None:
                lines.append(f"{indent}{indent}{characteristic.lower_limit} {characteristic.upper_limit}")
            lines.append(f"{indent}/end CHARACTERISTIC")
        
        # Add COMPU_METHODs
        for compu_method in self.compu_methods:
            lines.append(f"{indent}/begin COMPU_METHOD {compu_method.name}")
            lines.append(f"{indent}{indent}\"{compu_method.description}\"")
            lines.append(f"{indent}{indent}{compu_method.method_type}")
            if compu_method.format_str:
                lines.append(f"{indent}{indent}\"{compu_method.format_str}\"")
            if compu_method.unit:
                lines.append(f"{indent}{indent}\"{compu_method.unit}\"")
            if compu_method.coeffs:
                lines.append(f"{indent}{indent}COEFFS {' '.join(map(str, compu_method.coeffs))}")
            lines.append(f"{indent}/end COMPU_METHOD")
        
        # Add COMPU_VTABs
        for compu_vtab in self.compu_vtabs:
            lines.append(f"{indent}/begin COMPU_VTAB {compu_vtab.name}")
            lines.append(f"{indent}{indent}\"{compu_vtab.description}\"")
            lines.append(f"{indent}{indent}{compu_vtab.tab_type}")
            lines.append(f"{indent}{indent}{len(compu_vtab.entries)}")
            for value, verb in compu_vtab.entries:
                lines.append(f"{indent}{indent}{value} \"{verb}\"")
            lines.append(f"{indent}/end COMPU_VTAB")
        
        # Add RECORD_LAYOUTs
        for record_layout in self.record_layouts:
            lines.append(f"{indent}/begin RECORD_LAYOUT {record_layout.name}")
            for entry in record_layout.entries:
                lines.append(f"{indent}{indent}{entry}")
            lines.append(f"{indent}/end RECORD_LAYOUT")
        
        # Add GROUPs
        for group in self.groups:
            lines.append(f"{indent}/begin GROUP {group.name}")
            lines.append(f"{indent}{indent}\"{group.description}\"")
            if group.ref_measurements:
                lines.append(f"{indent}{indent}/begin REF_MEASUREMENT")
                for ref in group.ref_measurements:
                    lines.append(f"{indent}{indent}{indent}{ref}")
                lines.append(f"{indent}{indent}/end REF_MEASUREMENT")
            lines.append(f"{indent}/end GROUP")
        
        # Add FUNCTIONs
        for function in self.functions:
            lines.append(f"{indent}/begin FUNCTION {function.name}")
            lines.append(f"{indent}{indent}\"{function.description}\"")
            if function.loc_measurements:
                lines.append(f"{indent}{indent}/begin LOC_MEASUREMENT")
                for loc in function.loc_measurements:
                    lines.append(f"{indent}{indent}{indent}{loc}")
                lines.append(f"{indent}{indent}/end LOC_MEASUREMENT")
            lines.append(f"{indent}/end FUNCTION")
        
        # End MODULE block
        lines.append(f"{indent}/end MODULE")
        
        # End PROJECT block
        lines.append(f"/end PROJECT")
        
        return "\r".join(lines)
    

    
    def to_file(self, filepath: str, indent: str = "\t") -> None:
        """Export the model to an A2L file.
        
        Args:
            filepath: Path to save the A2L file
            indent: String to use for indentation (default is tab)
            
        Raises:
            IOError: If file cannot be written
        """
        a2l_content = self.to_a2l(indent)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(a2l_content)
        except IOError as e:
            raise IOError(f"Failed to write A2L file to {filepath}: {e}")


# --------------------------
# Parsing helpers for known blocks
# --------------------------

def parse_protocol_layer(block: A2LBlock) -> ProtocolLayer:
    """
    Parse PROTOCOL_LAYER block from A2L file.
    
    Args:
        block: A2LBlock containing PROTOCOL_LAYER data
        
    Returns:
        ProtocolLayer object with parsed configuration parameters
        
    Example:
        >>> protocol_layer = parse_protocol_layer(protocol_block)
    """
    pl = ProtocolLayer(raw=block.lines[:])
    tokens: list[list[str]] = []
    for ln in block.lines:
        t = tokenize_line(ln)
        if not t:
            continue
        tokens.append(t)

    flat: list[str] = [tok for line in tokens for tok in line]

    idx: int = 0
    if idx < len(flat):
        v = to_int(flat[idx])
        if v is not None:
            pl.version = v
            idx += 1

    while idx < len(flat):
        tok = flat[idx]
        if tok.startswith("BYTE_ORDER") or tok.startswith("ADDRESS_GRANULARITY") or tok == "OPTIONAL_CMD" or tok == "COMMUNICATION_MODE_SUPPORTED":
            break
        val = to_int(tok)
        if val is not None:
            pl.timing_values.append(val)
            idx += 1
            continue
        else:
            idx += 1
            break

    for i, tok in enumerate(flat):
        if tok.startswith("BYTE_ORDER"):
            pl.byte_order = tok
        elif tok.startswith("ADDRESS_GRANULARITY"):
            pl.address_granularity = tok
        elif tok == "OPTIONAL_CMD" and i + 1 < len(flat):
            pl.optional_cmds.append(flat[i + 1])
        elif tok == "COMMUNICATION_MODE_SUPPORTED" and i + 1 < len(flat):
            pl.communication_mode = flat[i + 1]
        elif tok == "MASTER":
            if i + 2 < len(flat):
                pl.master_max_bs = to_int(flat[i + 1])
                pl.master_min_st = to_int(flat[i + 2])

    before_enum: list[int] = []
    for tok in flat:
        if tok.startswith("BYTE_ORDER") or tok.startswith("ADDRESS_GRANULARITY"):
            break
        v = to_int(tok)
        if v is not None:
            before_enum.append(v)
    if len(before_enum) >= 3:
        pl.max_cto = before_enum[-3]
        pl.max_dto = before_enum[-2]

    return pl

def parse_daq(block: A2LBlock) -> DaqConfig:
    dq = DaqConfig(raw=block.lines[:])
    lines: list[str] = block.lines[:]

    toks: list[list[str]] = []
    for ln in lines:
        t = tokenize_line(ln)
        if t:
            toks.append(t)

    flat: list[str] = [x for line in toks for x in line]

    if flat:
        dq.mode = flat[0] if flat[0] in ("STATIC", "DYNAMIC") else None

    nums: list[int | None] = [to_int(x) for x in flat[1:1 + 3]]
    if len(nums) >= 3:
        dq.max_daq, dq.max_event_channel, dq.min_daq = nums[:3]

    for i, tok in enumerate(flat):
        if tok.startswith("IDENTIFICATION_FIELD_TYPE_"):
            dq.identification_field_type = tok
        elif tok.startswith("GRANULARITY_ODT_ENTRY_SIZE_DAQ_") or tok.startswith("GRANULARITY_ODT_ENTRY_SIZE_DAQ"):
            dq.odt_entry_granularity_daq = tok
        elif tok == "OVERLOAD_INDICATION_EVENT":
            dq.overload_indication = "EVENT"
        elif tok.startswith("GRANULARITY_ODT_ENTRY_SIZE_STIM_"):
            dq.stim_granularity = tok
        elif tok == "BIT_STIM_SUPPORTED":
            dq.bit_stim_supported = True

    for i, tok in enumerate(flat):
        if tok.startswith("GRANULARITY_ODT_ENTRY_SIZE_DAQ"):
            if i + 1 < len(flat):
                dq.max_odt_entry_size_daq = to_int(flat[i + 1])
        if tok.startswith("GRANULARITY_ODT_ENTRY_SIZE_STIM"):
            if i + 1 < len(flat):
                dq.max_odt_entry_size_stim = to_int(flat[i + 1])

    for evb in block.get_children("EVENT"):
        dq.events.append(parse_daq_event(evb))

    return dq

def parse_daq_event(block: A2LBlock) -> DaqEvent:
    lines: list[str] = [ln for ln in block.lines if ln.strip()]
    toks: list[list[str]] = [tokenize_line(ln) for ln in lines]
    flat: list[str] = [x for line in toks for x in line]

    quoted: list[str] = [unquote(x) for x in flat if (x.startswith('"') and x.endswith('"'))]
    name: str = quoted[0] if quoted else ""
    short: str | None = quoted[1] if len(quoted) > 1 else None

    nums: list[int] = [x for x in [to_int(x) for x in flat] if x is not None]
    evt_num: int | None = nums[0] if nums else None

    type_tok: str | None = None
    for x in flat:
        if x in ("DAQ", "STIM", "DAQ_STIM"):
            type_tok = x
            break

    cycle: int | None = None
    time_unit: int | None = None
    priority: int | None = None
    max_daq_list: int | None = None
    try:
        ti: int = flat.index(type_tok)
        seq: list[int] = []
        for x in flat[ti+1:]:
            val = to_int(x)
            if val is not None:
                seq.append(val)
        if len(seq) >= 4:
            max_daq_list, cycle, time_unit, priority = seq[:4]
    except Exception:
        pass

    return DaqEvent(
        name=name,
        short_name=short,
        event_channel_number=evt_num,
        type=type_tok,
        max_daq_list=max_daq_list,
        cycle=cycle,
        time_unit=time_unit,
        priority=priority,
        raw=block.lines[:]
    )

def parse_xcp_on_can(block: A2LBlock) -> XcpOnCanConfig:
    xcp = XcpOnCanConfig(raw=block.lines[:])
    lines: list[str] = block.lines[:]

    toks: list[list[str]] = [tokenize_line(ln) for ln in lines if ln.strip()]
    flat: list[str] = [x for line in toks for x in line]
    if flat and to_int(flat[0]) is not None:
        xcp.version = to_int(flat[0])

    kv_re: re.Pattern = re.compile(r"^([A-Z0-9_]+)\s+(\S+)$")
    for ln in lines:
        s = ln.strip()
        m = kv_re.match(s)
        if not m:
            continue
        key: str = m.group(1)
        value: str = m.group(2)
        key_u: str = key.upper()
        if key_u == "CAN_ID_BROADCAST":
            xcp.can_id_broadcast = to_int(value)
        elif key_u == "CAN_ID_MASTER":
            xcp.can_id_master = to_int(value)
        elif key_u == "CAN_ID_SLAVE":
            xcp.can_id_slave = to_int(value)
        elif key_u == "CAN_ID_GET_DAQ_CLOCK_MULTICAST":
            xcp.can_id_get_daq_clock_multicast = to_int(value)
        elif key_u == "BAUDRATE":
            xcp.baudrate = to_int(value)
        elif key_u == "SAMPLE_POINT":
            xcp.sample_point = to_int(value)
        elif key_u == "SAMPLE_RATE":
            xcp.sample_rate = value
        elif key_u == "BTL_CYCLES":
            xcp.btl_cycles = to_int(value)
        elif key_u == "SJW":
            xcp.sjw = to_int(value)
        elif key_u == "SYNC_EDGE":
            xcp.sync_edge = value
        elif key_u == "MAX_DLC_REQUIRED":
            xcp.max_dlc_required = True
        elif key_u == "MAX_BUS_LOAD":
            xcp.max_bus_load = to_int(value)

    fd_block: A2LBlock | None = block.get_first_child("CAN_FD")
    if fd_block:
        xcp.can_fd = parse_can_fd(fd_block)
    return xcp

def parse_can_fd(block: A2LBlock) -> XcpOnCanFdConfig:
    fd = XcpOnCanFdConfig(raw=block.lines[:])
    kv_re: re.Pattern = re.compile(r"^([A-Z0-9_]+)\s+(\S+)$")
    for ln in block.lines:
        s = ln.strip()
        m = kv_re.match(s)
        if not m:
            continue
        key: str = m.group(1)
        value: str = m.group(2)
        ku: str = key.upper()
        if ku == "MAX_DLC":
            fd.max_dlc = to_int(value)
        elif ku == "CAN_FD_DATA_TRANSFER_BAUDRATE":
            fd.data_transfer_baudrate = to_int(value)
        elif ku == "SAMPLE_POINT":
            fd.sample_point = to_int(value)
        elif ku == "BTL_CYCLES":
            fd.btl_cycles = to_int(value)
        elif ku == "SJW":
            fd.sjw = to_int(value)
        elif ku == "SYNC_EDGE":
            fd.sync_edge = value
        elif ku == "MAX_DLC_REQUIRED":
            fd.max_dlc_required = True
        elif ku == "SECONDARY_SAMPLE_POINT":
            fd.secondary_sample_point = to_int(value)
        elif ku == "TRANSCEIVER_DELAY_COMPENSATION":
            fd.tdc = value
    return fd

def parse_segment_info(seg_block: A2LBlock) -> SegmentInfo:
    si = SegmentInfo(raw=seg_block.lines[:])
    toks: list[list[str]] = [tokenize_line(ln) for ln in seg_block.lines if ln.strip()]
    flat: list[str] = [x for line in toks for x in line]
    nums: list[int] = [x for x in [to_int(x) for x in flat] if x is not None]
    if len(nums) >= 5:
        si.segment_number, si.num_pages, si.address_extension, si.compression_method, si.encryption_method = nums[:5]
    cs: A2LBlock | None = seg_block.get_first_child("CHECKSUM")
    if cs:
        for ln in cs.lines:
            t = tokenize_line(ln)
            if t:
                si.checksum_type = t[0]
                break
    for pg in seg_block.get_children("PAGE"):
        page_tokens: list[list[str]] = [tokenize_line(ln) for ln in pg.lines if ln.strip()]
        flatp: list[str] = [x for ln in page_tokens for x in ln]
        pn: int | None = to_int(flatp[0]) if flatp else None
        ecu_acc: str | None = flatp[1] if len(flatp) > 1 else None
        xcp_rd: str | None = flatp[2] if len(flatp) > 2 else None
        xcp_wr: str | None = flatp[3] if len(flatp) > 3 else None
        si.pages.append(PageInfo(page_number=pn, ecu_access=ecu_acc, xcp_read_access=xcp_rd, xcp_write_access=xcp_wr))
    return si

def parse_memory_segment(block: A2LBlock) -> MemorySegment:
    name: str = block.args[0] if block.args else ""
    long_id: str | None = None
    if len(block.args) > 1:
        long_id = unquote(" ".join(block.args[1:])) if block.args[1:] else None

    class_type: str | None = None
    memory_type: str | None = None
    address: int | None = None
    size: int | None = None
    attrs: list[str] = []

    for ln in block.lines:
        s = ln.strip()
        if not s:
            continue
        if class_type is None and memory_type is None:
            tt: list[str] = tokenize_line(s)
            if len(tt) == 2 and tt[0].isalpha() and tt[1].isalpha():
                class_type, memory_type = tt[0], tt[1]
                continue
        parts: list[str] = tokenize_line(s)
        if parts and (parts[0] in ("INTERN", "EXTERN")) and address is None:
            if len(parts) >= 3:
                address = to_int(parts[1])
                size = to_int(parts[2])
                if len(parts) > 3:
                    attrs = parts[3:]
                continue

    seg_info: SegmentInfo | None = None
    if_data: A2LBlock | None = block.get_first_child("IF_DATA")
    if if_data:
        xcpp: A2LBlock | None = if_data.get_first_child("XCPplus")
        if xcpp:
            segblk: A2LBlock | None = xcpp.get_first_child("SEGMENT")
            if segblk:
                seg_info = parse_segment_info(segblk)

    return MemorySegment(
        name=name,
        long_identifier=long_id,
        class_type=class_type,
        memory_type=memory_type,
        address=address,
        size=size,
        attributes=attrs,
        segment_info=seg_info,
        raw=block.lines[:]
    )
def parse_axis_pts(block: A2LBlock) -> AxisPts:
    # Name can be in /begin line args or as the first line inside the block
    lines: list[str] = [ln for ln in block.lines if ln.strip()]
    i: int = 0

    if block.args and len(block.args) > 0:
        name: str = block.args[0]
    else:
        # First non-empty line is the name
        first: list[str] = tokenize_line(lines[i]) if i < len(lines) else []
        name: str = first[0] if first else ""
        i += 1

    def next_token_line() -> list[str]:
        nonlocal i
        while i < len(lines):
            t: list[str] = tokenize_line(lines[i])
            i += 1
            if t:
                return t
        return []

    # Description
    desc_tokens: list[str] = next_token_line()
    description: str = unquote(" ".join(desc_tokens)) if desc_tokens else ""

    # Address
    addr: int | None = None
    t: list[str] = next_token_line()
    if t:
        addr = to_int(t[0])

    input_qty: str | None = None
    t = next_token_line()
    if t:
        input_qty = t[0]

    record_layout: str | None = None
    t = next_token_line()
    if t:
        record_layout = t[0]

    deposit: int | None = None
    t = next_token_line()
    if t:
        deposit = to_int(t[0])

    compu_method: str | None = None
    t = next_token_line()
    if t:
        compu_method = t[0]

    max_points: int | None = None
    t = next_token_line()
    if t:
        max_points = to_int(t[0])

    lower: float | int | None = None
    upper: float | int | None = None
    t = next_token_line()
    if t:
        lower = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])
    t = next_token_line()
    if t:
        upper = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])

    # Optional: BYTE_ORDER, FORMAT, IF_DATA, SYMBOL_LINK, etc.
    byte_order: str | None = None
    fmt: str | None = None
    symbol_link: tuple[str | None, int | None] | None = None

    for ln in lines[i:]:
        tt: list[str] = tokenize_line(ln)
        if not tt:
            continue
        if tt[0].upper() == "BYTE_ORDER":
            if len(tt) > 1:
                byte_order = tt[1]
        elif tt[0].upper() == "FORMAT":
            if len(tt) > 1:
                fmt = tt[1]
        elif tt[0].upper() == "SYMBOL_LINK":
            # SYMBOL_LINK "name" index
            if len(tt) >= 3:
                symbol_link = (unquote(tt[1]), to_int(tt[2]) or 0)

    return AxisPts(
        name=name,
        description=description,
        address=addr,
        input_quantity=input_qty,
        record_layout=record_layout,
        deposit=deposit,
        compu_method=compu_method,
        max_axis_points=max_points,
        lower_limit=lower,
        upper_limit=upper,
        byte_order=byte_order,
        format_str=fmt,
        symbol_link=symbol_link,
        raw=block.lines[:]
    )


def parse_measurement(block: A2LBlock) -> Measurement:
    # Name can be in /begin args or first line inside the block
    lines = [ln for ln in block.lines if ln.strip()]
    i = 0

    if block.args and len(block.args) > 0:
        name = block.args[0]
    else:
        t0 = tokenize_line(lines[i]) if i < len(lines) else []
        name = t0[0] if t0 else ""
        i += 1  # advance past the name line

    def next_tokens()->list[Any]:
        nonlocal i
        while i < len(lines):
            t = tokenize_line(lines[i])
            i += 1
            if t:
                return t
        return []

    desc = unquote(" ".join(next_tokens())) if i < len(lines) else ""
    datatype = next_tokens()[0] if i < len(lines) else ""
    compu_method = next_tokens()[0] if i < len(lines) else ""

    params: list[str] = []
    ecu_address = None
    address = None
    lower = None
    upper = None
    symbol_link = None

    while i < len(lines):
        t = tokenize_line(lines[i])
        i += 1
        if not t:
            continue
        key = t[0].upper()
        if key in ("ECU_ADDRESS", "ADDRESS"):
            if len(t) > 1:
                val = to_int(t[1])
                if key == "ECU_ADDRESS":
                    ecu_address = val
                else:
                    address = val
        elif key == "SYMBOL_LINK":
            if len(t) >= 3:
                symbol_link = (unquote(t[1]), to_int(t[2]) or 0)
        else:
            # numeric params, limits, or other tokens
            if len(t) == 1 and (to_int(t[0]) is not None or to_float(t[0]) is not None):
                params.append(t[0])
            elif len(t) == 2 and all([(to_float(x) is not None or to_int(x) is not None) for x in t]):
                lower = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])
                upper = to_float(t[1]) if to_float(t[1]) is not None else to_int(t[1])
            else:
                params.extend(t)

    return Measurement(
        name=name,
        description=desc,
        datatype=datatype,
        compu_method=compu_method,
        params=params,
        ecu_address=ecu_address,
        address=address,
        lower_limit=lower,
        upper_limit=upper,
        symbol_link=symbol_link,
        raw=block.lines[:]
    )


def parse_characteristic(block: A2LBlock) -> Characteristic:
    """
    CHARACTERISTIC name on first content line when absent from /begin.
    Then:
      "<desc>"
      <type>
      <address>
      <record_layout>
      <max_diff>
      <compu_method>
      <lower>
      <upper>
    Optional SYMBOL_LINK lines may follow.
    """
    lines: list[str] = [ln for ln in block.lines if ln.strip()]
    i: int = 0

    if block.args and len(block.args) > 0:
        name: str = block.args[0]
    else:
        t0: list[str] = tokenize_line(lines[i]) if i < len(lines) else []
        name: str = t0[0] if t0 else ""
        i += 1  # advance past name

    def next_tokens() -> list[str]:
        nonlocal i
        while i < len(lines):
            t: list[str] = tokenize_line(lines[i])
            i += 1
            if t:
                return t
        return []

    desc: str = unquote(" ".join(next_tokens())) if i < len(lines) else ""
    char_type: str = next_tokens()[0] if i < len(lines) else ""

    addr: int | None = None
    t: list[str] = next_tokens()
    if t:
        addr = to_int(t[0])

    record_layout: str | None = None
    t = next_tokens()
    if t:
        record_layout = t[0]

    max_diff: float | int | None = None
    t = next_tokens()
    if t:
        max_diff = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])

    compu_method: str | None = None
    t = next_tokens()
    if t:
        compu_method = t[0]

    lower: float | int | None = None
    upper: float | int | None = None
    t = next_tokens()
    if t:
        lower = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])
    t = next_tokens()
    if t:
        upper = to_float(t[0]) if to_float(t[0]) is not None else to_int(t[0])

    symbol_link: tuple[str | None, int | None] | None = None
    for ln in lines[i:]:
        tt: list[str] = tokenize_line(ln)
        if not tt:
            continue
        if tt[0].upper() == "SYMBOL_LINK" and len(tt) >= 3:
            symbol_link = (unquote(tt[1]), to_int(tt[2]) or 0)

    return Characteristic(
        name=name,
        description=desc,
        char_type=char_type,
        address=addr,
        record_layout=record_layout,
        max_diff=max_diff,
        compu_method=compu_method,
        lower_limit=lower,
        upper_limit=upper,
        symbol_link=symbol_link,
        raw=block.lines[:]
    )

def parse_compu_method(block: A2LBlock) -> CompuMethod:
    name: str = block.args[0] if block.args else ""
    lines: list[str] = [ln for ln in block.lines if ln.strip()]
    i: int = 0
    def next_tokens() -> list[str]:
        nonlocal i
        while i < len(lines):
            t: list[str] = tokenize_line(lines[i])
            i += 1
            if t:
                return t
        return []

    desc: str = unquote(" ".join(next_tokens())) if lines else ""
    method_type: str = next_tokens()[0] if lines else ""
    fmt: str | None = unquote(" ".join(next_tokens())) if lines else None
    unit: str | None = unquote(" ".join(next_tokens())) if lines else None
    coeffs: list[float] = []
    for ln in lines[i:]:
        tt: list[str] = tokenize_line(ln)
        if not tt:
            continue
        if tt[0].upper() == "COEFFS":
            for v in tt[1:]:
                if to_float(v) is not None:
                    coeffs.append(float(v))
    return CompuMethod(name=name, description=desc, method_type=method_type, format_str=fmt, unit=unit, coeffs=coeffs, raw=block.lines[:])

def parse_compu_vtab(block: A2LBlock) -> CompuVTab:
    name: str = block.args[0] if block.args else ""
    lines: list[str] = [ln for ln in block.lines if ln.strip()]
    i: int = 0
    def next_tokens() -> list[str]:
        nonlocal i
        while i < len(lines):
            t: list[str] = tokenize_line(lines[i])
            i += 1
            if t:
                return t
        return []

    desc: str = unquote(" ".join(next_tokens())) if lines else ""
    tab_type: str = next_tokens()[0] if lines else ""
    entries: list[Tuple[int, str]] = []
    count: int | None = None
    t: list[str] = next_tokens()
    if t and to_int(t[0]) is not None:
        count = to_int(t[0])
        for _ in range(count or 0):
            tt: list[str] = next_tokens()
            if not tt:
                continue
            val: int | None = to_int(tt[0])
            verb: str = unquote(" ".join(tt[1:])) if len(tt) > 1 else ""
            if val is not None:
                entries.append((val, verb.strip('"')))
    else:
        while True:
            tt: list[str] = next_tokens()
            if not tt:
                break
            try:
                val: int | None = to_int(tt[0])
                verb: str = unquote(" ".join(tt[1:]))
                if val is not None:
                    entries.append((val, verb))
            except Exception:
                break

    return CompuVTab(name=name, description=desc, tab_type=tab_type, entries=entries, raw=block.lines[:])

def parse_record_layout(block: A2LBlock) -> RecordLayout:
    name: str = block.args[0] if block.args else ""
    entries: list[str] = [ln.strip() for ln in block.lines if ln.strip()]
    return RecordLayout(name=name, entries=entries, raw=block.lines[:])

def parse_group(block: A2LBlock) -> Group:
    name = block.args[0] if block.args else ""
    lines = [ln for ln in block.lines if ln.strip()]
    desc = ""
    refs: list[str] = []
    if lines:
        t = tokenize_line(lines[0])
        if t:
            desc = unquote(" ".join(t))
    for rb in block.get_children("REF_MEASUREMENT"):
        for ln in rb.lines:
            t = tokenize_line(ln)
            for tok in t:
                if tok not in ("/begin", "/end"):
                    refs.append(tok)
    return Group(name=name, description=desc, ref_measurements=refs, raw=block.lines[:])

def parse_function(block: A2LBlock) -> Function:
    name = block.args[0] if block.args else ""
    lines = [ln for ln in block.lines if ln.strip()]
    desc = ""
    loc: list[str] = []
    if lines:
        t = tokenize_line(lines[0])
        if t:
            desc = unquote(" ".join(t))
    for lb in block.get_children("LOC_MEASUREMENT"):
        for ln in lb.lines:
            t = tokenize_line(ln)
            for tok in t:
                loc.append(tok)
    loc = [x for x in loc if x not in ("/begin", "/end")]
    return Function(name=name, description=desc, loc_measurements=loc, raw=block.lines[:])


# --------------------------
# A2L file block parser (generic tree)
# --------------------------

class BlockBuilder:
    """
    Builds A2L block hierarchy from raw text lines.
    
    This class processes A2L text line by line and builds a hierarchical
    block structure that represents the A2L file's organization.
    """
    def __init__(self) -> None:
        """Initialize the BlockBuilder with an empty root block."""
        self.root = A2LBlock(name="ROOT", args=[])
        self.stack = [self.root]

    def feed_line(self, line: str) -> None:
        s = line.strip()
        if not s:
            return
        if s.lower().startswith("/begin"):
            m = re.match(r"/begin\s+(\S+)\s*(.*)$", s, flags=re.I)
            if not m:
                self.stack[-1].lines.append(line.rstrip("\n"))
                return
            name = m.group(1)
            if name == "MEASUREMENT":
                pass
            args_str = m.group(2).strip()
            args = []
            if args_str:
                try:
                    args = shlex.split(args_str, posix=True)
                except Exception:
                    args = args_str.split()
            blk = A2LBlock(name=name, args=args, lines=[], children=[])
            self.stack[-1].children.append(blk)
            self.stack.append(blk)
        elif s.lower().startswith("/end"):
            if len(self.stack) > 1:
                self.stack.pop()
        else:
            self.stack[-1].lines.append(line.rstrip("\n"))

    def get_root(self) -> A2LBlock:
        return self.root


# --------------------------
# Top-level parser
# --------------------------

class A2LParser:
    """
    Main A2L parser class that converts A2L text into structured data model.
    
    This class handles the complete parsing process from raw A2L text to
    a structured A2LModel object containing all parsed elements.
    """
    def parse_file(self, path: str | Path) -> A2LModel:
        """
        Parse an A2L file from disk.
        
        Args:
            path: Path to the A2L file to parse
            
        Returns:
            A2LModel object containing parsed data
            
        Raises:
            IOError: If the file cannot be read
        """
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        return self.parse_text(text)

    def parse_text(self, text: str) -> A2LModel:
        cleaned = strip_block_comments(text)
        bb = BlockBuilder()
        for ln in cleaned.splitlines():
            bb.feed_line(ln)
        root = bb.get_root()

        model = A2LModel(raw_blocks=[root])

        proj = root.get_first_child("PROJECT")
        if proj:
            if proj.args:
                model.project_name = proj.args[0]
            mod = proj.get_first_child("MODULE")
            if mod and mod.args:
                model.module_name = mod.args[0]

            if mod:
                for ifd in mod.get_children("IF_DATA"):
                    if ifd.args and ifd.args[0] == "XCPplus":
                        pl = ifd.get_first_child("PROTOCOL_LAYER")
                        if pl:
                            model.protocol_layer = parse_protocol_layer(pl)

                        dq = ifd.get_first_child("DAQ")
                        if dq:
                            model.daq = parse_daq(dq)
                            model.daq_events = list(model.daq.events)

                        xcp_can = ifd.get_first_child("XCP_ON_CAN")
                        if xcp_can:
                            model.xcp_on_can = parse_xcp_on_can(xcp_can)

                mod_par = mod.get_first_child("MOD_PAR")
                if mod_par:
                    for ms in mod_par.get_children("MEMORY_SEGMENT"):
                        model.memory_segments.append(parse_memory_segment(ms))

                for ax in mod.get_children("AXIS_PTS"):
                    model.axis_pts.append(parse_axis_pts(ax))

                for meas in mod.get_children("MEASUREMENT"):
                    model.measurements.append(parse_measurement(meas))

                # NEW: CHARACTERISTIC
                for ch in mod.get_children("CHARACTERISTIC"):
                    model.characteristics.append(parse_characteristic(ch))

                for cm in mod.get_children("COMPU_METHOD"):
                    model.compu_methods.append(parse_compu_method(cm))

                for cv in mod.get_children("COMPU_VTAB"):
                    model.compu_vtabs.append(parse_compu_vtab(cv))

                for rl in mod.get_children("RECORD_LAYOUT"):
                    model.record_layouts.append(parse_record_layout(rl))

                for grp in mod.get_children("GROUP"):
                    model.groups.append(parse_group(grp))

                for fn in mod.get_children("FUNCTION"):
                    model.functions.append(parse_function(fn))

        return model


