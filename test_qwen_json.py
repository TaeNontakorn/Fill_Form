#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen JSON Response Handler
Test and validate Qwen API responses for JSON extraction
"""

import json
import re
from typing import Any, Dict, Optional

def extract_json_from_qwen_response(response_text: str) -> Dict[str, Any]:
    """
    Extract JSON from Qwen response which may include markdown code blocks or extra text.
    
    Args:
        response_text: Raw text response from Qwen API
        
    Returns:
        Parsed JSON as dictionary
        
    Raises:
        json.JSONDecodeError: If JSON parsing fails
        ValueError: If no JSON found in response
    """
    
    # Try 1: Extract from markdown JSON code block
    if '```json' in response_text:
        json_str = response_text.split('```json')[1].split('```')[0].strip()
        return json.loads(json_str)
    
    # Try 2: Extract from generic markdown code block
    if '```' in response_text:
        parts = response_text.split('```')
        if len(parts) >= 3:
            json_str = parts[1].strip()
            # Remove language specifier if present (e.g., "json\n{...")
            if '\n' in json_str:
                json_str = json_str.split('\n', 1)[1]
            return json.loads(json_str)
    
    # Try 3: Find JSON object directly using regex
    json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
    
    # Try 4: Try parsing entire response as JSON
    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        raise ValueError(f"Could not extract valid JSON from response: {response_text[:100]}...")


def validate_contract_response(data: Dict[str, Any], required_fields: list) -> bool:
    """
    Validate that response contains required contract fields.
    
    Args:
        data: Parsed JSON response
        required_fields: List of required field names
        
    Returns:
        True if valid, False otherwise
    """
    missing_fields = [f for f in required_fields if f not in data]
    if missing_fields:
        print(f"⚠️  Missing fields: {missing_fields}")
        return False
    return True


def normalize_missing_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize empty strings or None values to "ไม่พบข้อมูล".
    
    Args:
        data: Parsed JSON response
        
    Returns:
        Normalized dictionary
    """
    for key, value in data.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            data[key] = "ไม่พบข้อมูล"
    return data


# Example usage and test cases
if __name__ == "__main__":
    # Test 1: Response with markdown JSON block
    test_response_1 = """
    Here is the contract data:
    ```json
    {
        "Contract_id": "CNT-2024-001",
        "Contract_date": "1 มกราคม 2567",
        "Customer_company_name": "บริษัท ทดสอบ จำกัด",
        "Customer_tax_id": "1234567890123"
    }
    ```
    """
    
    print("Test 1: Markdown JSON block")
    try:
        result = extract_json_from_qwen_response(test_response_1)
        print(f"✅ Success: {json.dumps(result, ensure_ascii=False, indent=2)}\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
    
    # Test 2: Direct JSON response
    test_response_2 = '{"Contract_id": "CNT-2024-002", "Customer_company_name": "บริษัท มัง โก"}'
    
    print("Test 2: Direct JSON")
    try:
        result = extract_json_from_qwen_response(test_response_2)
        print(f"✅ Success: {json.dumps(result, ensure_ascii=False, indent=2)}\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
    
    # Test 3: Response with empty fields
    test_response_3 = '{"Contract_id": "CNT-2024-003", "Customer_tax_id": "", "Customer_director_name": null}'
    
    print("Test 3: Empty fields normalization")
    try:
        result = extract_json_from_qwen_response(test_response_3)
        normalized = normalize_missing_data(result)
        print(f"✅ Success: {json.dumps(normalized, ensure_ascii=False, indent=2)}\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
    
    # Test 4: Generic code block
    test_response_4 = """
    The extracted data is:
    ```
    {
        "Contract_id": "CNT-2024-004",
        "Customer_company_name": "บริษัท ทดสอบ 2"
    }
    ```
    """
    
    print("Test 4: Generic code block")
    try:
        result = extract_json_from_qwen_response(test_response_4)
        print(f"✅ Success: {json.dumps(result, ensure_ascii=False, indent=2)}\n")
    except Exception as e:
        print(f"❌ Error: {e}\n")
