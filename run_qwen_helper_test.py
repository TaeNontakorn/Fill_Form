from back_end import extract_json_from_qwen_response

tests = [
    '```json {"Contract_id":"1"}```',
    '```{\n"Contract_id":"1"\n}```',
    '{"Contract_id":"1"}',
    'Here is the JSON:\n```json\n{"Contract_id":"1"}\n```',
    'Response:\n```\n{"Contract_id":"1", "Customer_company_name": "บริษัท"}\n```',
]

for t in tests:
    print('---')
    print('input:', repr(t))
    print('output:', repr(extract_json_from_qwen_response(t)))
