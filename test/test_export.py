#!/usr/bin/env python3
"""
Comprehensive test suite for A2L export functionality.
"""

from a2lmodel import A2LParser, A2LModel,Characteristic, Measurement
import tempfile
import os
import pytest


def test_export_basic()->None:
    """Test basic export functionality with demo file."""
    parser = A2LParser()
    model = parser.parse_file("test/demo.a2l")
    
    # Test to_a2l() method
    a2l_content = model.to_a2l()
    
    # Basic validation
    assert "ASAP2_VERSION" in a2l_content
    assert "/begin PROJECT" in a2l_content
    assert "/begin MODULE" in a2l_content
    
    # Check that key elements are present
    if model.project_name:
        assert model.project_name in a2l_content
    if model.module_name:
        assert model.module_name in a2l_content
    
    # Check data structures are included
    for measurement in model.measurements:
        assert f"/begin MEASUREMENT {measurement.name}" in a2l_content
        assert measurement.description in a2l_content
    
    for characteristic in model.characteristics:
        assert f"/begin CHARACTERISTIC {characteristic.name}" in a2l_content
        assert characteristic.description in a2l_content
    
    for axis_pts in model.axis_pts:
        assert f"/begin AXIS_PTS {axis_pts.name}" in a2l_content


def test_export_file()->None:
    """Test exporting to a file with proper error handling."""
    parser = A2LParser()
    model = parser.parse_file("test/demo.a2l")
    
    # Create a temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.a2l', delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # Export to file
        model.to_file(tmp_path)
        
        # Verify file was created and has content
        assert os.path.exists(tmp_path)
        assert os.path.getsize(tmp_path) > 0
        
        # Read back and verify content
        with open(tmp_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert "ASAP2_VERSION" in content
        assert "/begin PROJECT" in content
        assert "/end PROJECT" in content
        
        # Test invalid file path
        with pytest.raises(IOError):
            model.to_file("/invalid/path/test.a2l")
            
    finally:
        # Clean up
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_export_empty_model()->None:
    """Test exporting an empty model generates valid structure."""
    model = A2LParser().parse_text("")
    
    a2l_content = model.to_a2l()
    
    # Should still generate valid A2L structure
    assert "ASAP2_VERSION" in a2l_content
    assert "/begin PROJECT" in a2l_content
    assert "Untitled" in a2l_content  # Default project name
    assert "/end PROJECT" in a2l_content


def test_export_custom_indentation()->None:
    """Test export with custom indentation."""
    parser = A2LParser()
    model = parser.parse_file("test/demo.a2l")
    
    # Test with spaces
    a2l_spaces = model.to_a2l(indent="    ")
    assert "    /begin MODULE" in a2l_spaces
    
    # Test with no indentation
    a2l_no_indent = model.to_a2l(indent="")
    assert "/begin MODULE" in a2l_no_indent
    assert "\t" not in a2l_no_indent


def test_export_modified_model()->None:
    """Test export of modified model data."""
    parser = A2LParser()
    model = parser.parse_file("test/demo.a2l")
    
    # Modify some data
    if model.measurements:
        model.measurements[0].description = "Modified description"
        
    # Add a new characteristic
    new_char = Characteristic(
        name="TEST_CALIBRATION",
        description="Test calibration parameter",
        char_type="VALUE",
        address=0x1000,
        record_layout="RL_1D",
        compu_method="CM_IDENTICAL",
        lower_limit=0.0,
        upper_limit=100.0,
        max_diff=0
    )
    model.characteristics.append(new_char)
    
    # Export and verify modifications
    a2l_content = model.to_a2l()
    assert "Modified description" in a2l_content
    assert "/begin CHARACTERISTIC TEST_CALIBRATION" in a2l_content
    assert "Test calibration parameter" in a2l_content


def test_export_complete_roundtrip()->None:
    """Test complete parse → modify → export roundtrip."""
    parser = A2LParser()
    
    # Parse original file
    original_model = parser.parse_file("test/demo.a2l")
    
    # Create a new model with modified data
    modified_model = A2LModel()
    modified_model.project_name = "ModifiedProject"
    modified_model.module_name = "ModifiedModule"
    
    # Add some test measurements
    test_measurement = Measurement(
        name="TEST_MEASUREMENT",
        description="Test measurement",
        datatype="UWORD",
        compu_method="CM_IDENTICAL",
        ecu_address=0x2000,
        lower_limit=0.0,
        upper_limit=100.0
    )
    modified_model.measurements.append(test_measurement)
    
    # Export modified model
    a2l_content = modified_model.to_a2l()
    
    # Verify modified content
    assert "ModifiedProject" in a2l_content
    assert "ModifiedModule" in a2l_content
    assert "/begin MEASUREMENT TEST_MEASUREMENT" in a2l_content
    assert "Test measurement" in a2l_content


def test_export_memory_segments()->None:
    """Test export of memory segments."""
    parser = A2LParser()
    model = parser.parse_file("test/demo.a2l")
    
    a2l_content = model.to_a2l()
    
    # Check if memory segments are included
    if model.memory_segments:
        for segment in model.memory_segments:
            assert f"/begin MEMORY_SEGMENT {segment.name}" in a2l_content


def test_export_daq_configuration()->None:
    """Test export of DAQ configuration."""
    parser = A2LParser()
    model = parser.parse_file("test/demo.a2l")
    
    a2l_content = model.to_a2l()
    
    # Check if DAQ configuration is included
    if model.daq:
        assert "/begin DAQ" in a2l_content
        for event in model.daq_events:
            assert f'"{event.name}"' in a2l_content


def test_export_compu_methods()->None:
    """Test export of computation methods."""
    parser = A2LParser()
    model = parser.parse_file("test/demo.a2l")
    
    a2l_content = model.to_a2l()
    
    # Check if compu methods are included
    for compu_method in model.compu_methods:
        assert f"/begin COMPU_METHOD {compu_method.name}" in a2l_content


def test_export_with_pytest()->None:
    """Test export functionality using pytest framework."""
    parser = A2LParser()
    model = parser.parse_file("test/demo.a2l")
    
    # Test to_dict() method
    model_dict = model.to_dict()
    assert isinstance(model_dict, dict)
    assert "project_name" in model_dict
    assert "measurements" in model_dict
    
    # Test to_a2l() returns string
    a2l_content = model.to_a2l()
    assert isinstance(a2l_content, str)
    assert len(a2l_content) > 0


if __name__ == "__main__":
    print("Running comprehensive A2L export tests...")
    
    # Run all test functions
    test_functions = [
        test_export_basic,
        test_export_file,
        test_export_empty_model,
        test_export_custom_indentation,
        test_export_modified_model,
        test_export_complete_roundtrip,
        test_export_memory_segments,
        test_export_daq_configuration,
        test_export_compu_methods,
        test_export_with_pytest
    ]
    
    for test_func in test_functions:
        try:
            test_func()
            print(f"✓ {test_func.__name__} passed")
        except Exception as e:
            print(f"✗ {test_func.__name__} failed: {e}")
            raise
    
    print("\n🎉 All export tests passed!")
    print("\nTo run tests with pytest, use:")
    print("pytest test/test_export.py -v")