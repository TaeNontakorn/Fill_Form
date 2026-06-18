# Qwen Migration Notes - From Gemini to Qwen2.5-7b

## Changes Made

### 1. **Import Statement**
- **Before:** `from google import genai`
- **After:** `from openai import OpenAI`

### 2. **Client Initialization**
- **Before:** 
  ```python
  API_KEY = os.environ.get("API_KEY") or os.environ.get("GEMINI_API_KEY")
  client = genai.Client(api_key=API_KEY)
  ```
- **After:**
  ```python
  QWEN_API_KEY = os.environ.get("QWEN_API_KEY")
  QWEN_API_BASE_URL = os.environ.get("QWEN_API_BASE_URL")
  client = OpenAI(
      base_url=QWEN_API_BASE_URL,
      api_key=QWEN_API_KEY
  )
  ```

### 3. **Analysis Function**
- Renamed from `analyze_with_gemini()` to `analyze_with_qwen()`
- Changed model from `gemini-2.5-pro` to `qwen2.5-7b`
- Updated API call from Gemini SDK to OpenAI SDK format

### 4. **API Call Format**
- **Gemini (Before):**
  ```python
  response = client.models.generate_content(
      model="gemini-2.5-pro", 
      contents=[prompt],
      config={
          "response_mime_type": "application/json",
          "response_schema": ContractResponse,
      }
  )
  ```

- **Qwen (After):**
  ```python
  response = client.chat.completions.create(
      model="qwen2.5-7b",
      messages=[{"role": "user", "content": prompt}],
      temperature=0.7,
      max_tokens=4096
  )
  ```

### 5. **Updated Function Calls**
- Line changed: `gemini_analysis = analyze_with_gemini(parsed_json)` → `qwen_analysis = analyze_with_qwen(parsed_json)`
- Line changed: `data_from_gemini = json.loads(gemini_analysis)` → `data_from_qwen = json.loads(qwen_analysis)`

---

## ⚠️ Important Notes on Qwen's JSON Response Format

### Key Differences from Gemini:

1. **Response Structure**
   - Qwen returns raw text containing JSON in `response.choices[0].message.content`
   - Unlike Gemini's structured output, Qwen may include additional text before/after JSON

2. **JSON Extraction Best Practice**
   ```python
   # Qwen's response.choices[0].message.content might contain:
   # "Here is the extracted data: {json_object}"
   # OR just the JSON object directly
   
   response_text = response.choices[0].message.content
   # Extract JSON from the response (handle potential markdown code blocks)
   if '```json' in response_text:
       json_str = response_text.split('```json')[1].split('```')[0]
   elif '```' in response_text:
       json_str = response_text.split('```')[1].split('```')[0]
   else:
       json_str = response_text
   
   data = json.loads(json_str.strip())
   ```

3. **Validation Requirement**
   - Always validate Qwen's JSON response matches expected fields
   - Use try-catch blocks to handle malformed JSON responses
   - Consider adding response validation before parsing

4. **Temperature & Max Tokens**
   - Current settings: `temperature=0.7, max_tokens=4096`
   - Adjust temperature lower (0.0-0.5) for more consistent JSON output
   - Adjust higher (0.7-1.0) for more creative responses

---

## Environment Variables Required

Update your `.env` file or system environment with:

```env
QWEN_API_KEY=your_qwen_api_key
QWEN_API_BASE_URL=https://api.qwen.com/v1
```

---

## Testing Recommendations

1. **Test JSON Parsing**
   ```python
   # Run test with sample data
   test_data = {"key": "value", ...}
   result = analyze_with_qwen(test_data)
   print(result)  # Check raw response format
   ```

2. **Validate Response Fields**
   - Ensure all required fields from `ContractResponse` are present
   - Check for "ไม่พบข้อมูล" (Not Found) placeholders
   - Verify UTF-8 encoding is preserved

3. **Monitor Performance**
   - Compare processing time: Qwen vs Gemini
   - Track success/failure rates of JSON parsing
   - Log response samples for debugging

---

## Known Issues to Watch For

1. **Prompt Sensitivity**
   - Qwen may be more sensitive to prompt format
   - The strict JSON-only rule in the prompt is critical
   - Test with different prompt variations if needed

2. **Field Completeness**
   - Qwen might return empty strings instead of "ไม่พบข้อมูล"
   - Add post-processing to normalize missing data values

3. **Unicode Handling**
   - Ensure database/storage handles Thai characters correctly
   - Test with actual Thai contract data

---

## Rollback Instructions

If you need to revert to Gemini:
1. Change import: `from google import genai`
2. Restore client: `client = genai.Client(api_key=API_KEY)`
3. Restore function: Use `analyze_with_gemini()` from git history
4. Update API call format back to Gemini SDK

---

## Additional References

- Qwen API Docs: https://dashscope.aliyun.com/api-details/qwen
- OpenAI Python SDK: https://github.com/openai/openai-python
- Compare JSON handling: See test_qwen_json.py (if created)

