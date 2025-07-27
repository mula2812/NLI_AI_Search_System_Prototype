import httpx
import json
import os
import re
import asyncio
import google.generativeai as genai
import streamlit as st

# --- Configuration ---
FASTAPI_BASE_URL = "http://localhost:8000"
OPENAPI_SCHEMA_PATH = "openapi_schema.json"
DEBUG_MODE = False

# --- API Key Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("GEMINI_API_KEY environment variable not set. Please set it in your environment.")
    st.stop()
genai.configure(api_key=GEMINI_API_KEY)

NLI_API_KEY = os.getenv("NLI_API_KEY")
if not NLI_API_KEY:
    st.error("NLI_API_KEY environment variable not set. Please set it in your environment.")
    st.stop()

# --- Language Configuration ---
LANGUAGES = {
    "עברית": {
        "page_title": "מערכת חיפוש הספרייה הלאומית (באמצעות בינה מלאכותית)",
        "header": "📚 מערכת חיפוש הספרייה הלאומית (גרסת הבינה המלאכותית)",
        "subheader": "הקלד שאילתה בשפה טבעית והמערכת תנסה למצוא תוצאות.",
        "search_placeholder": "לדוגמה: ספרים של ביאליק שיצאו לאור אחרי 1920",
        "search_button": "🔍 חפש",
        "analyzing_query": "מנתח את שאילתתך בעזרת בינה מלאכותית...",
        "searching_nli": "מחפש מידע בספרייה הלאומית...",
        "search_in_progress": "חיפוש מתבצע",
        "no_results": "לא נמצאו תוצאות עבור השאילתה שלך.",
        "no_relevant_items": "לא נמצאו פריטים רלוונטיים עבור השאילתה שלך.",
        "media_requested": "מדיה שביקשת",
        "item_page_link_text": "קישור לדף הפריט בספרייה הלאומית",
        "no_direct_image": "לא ניתן להציג תמונה ישירה עבור פריט זה.",
        "no_direct_media_streams": "לא אותרו קישורי מדיה (וידאו/אודיו) ישירים.",
        "ai_summary_header": "סיכום של התוצאות",
        "cannot_summarize": "לא ניתן היה ליצור סיכום.",
        "unexpected_error_summary": "אירעה שגיאה בלתי צפויה במהלך יצירת סיכום.",
        "sidebar_language_header": "Language / שפה",
        "sidebar_language_select": "בחר שפה / Select Language:",
        "sidebar_debug_mode": "מצב דיבאג (הצג מידע נוסף ו-JSON)",
        "sidebar_about_header": "אודות",
        "sidebar_about_info": "מערכת זו משתמשת בבינה מלאכותית לחיפוש במאגרי הספרייה הלאומית. בפיתוח.",
        "sidebar_reset_button": "איפוס והתחלה מחדש",
        "sidebar_shutdown_button": "כיבוי האפליקציה",
        "critical_error_params_not_loaded": "שגיאה קריטית: רשימת פרמטרים מותרים לא נטענה. לא ניתן לבצע חיפוש.",
        "type_query_to_start": "אנא הקלד שאילתה בשדה החיפוש כדי להתחיל.",
        "default_title": "כותרת לא ידועה",
        "default_creator": "יוצר לא ידוע",
        "default_id": "מזהה לא ידוע",
        "default_value_not_found": "לא ידוע",
        "error_processing_openapi_schema": "שגיאה בעיבוד סכימת OpenAPI. משתמש בפרמטרי ברירת מחדל.",
        "error_openapi_path_not_found": "הנתיב '/api/v1/search' לא נמצא בסכימת OpenAPI. משתמש בברירות מחדל.",
        "warning_no_parameters_in_schema": "לא הוגדרו פרמטרים עבור '/api/v1/search' בסכימת OpenAPI."
    },
    "English": {
        "page_title": "National Library Search System (AI)",
        "header": "📚 National Library Search System (AI Version)",
        "subheader": "Type a query in natural language and the system will try to find results.",
        "search_placeholder": "e.g., Books that wrote by Ben-Gurion",
        "search_button": "🔍 Search",
        "analyzing_query": "Analyzing your query with AI...",
        "searching_nli": "Searching the National Library...",
        "search_in_progress": "Search in progress",
        "no_results": "No results found for your query.",
        "no_relevant_items": "No relevant items found for your query.",
        "media_requested": "Requested Media",
        "item_page_link_text": "Link to item page at the National Library",
        "no_direct_image": "No direct image available for this item.",
        "no_direct_media_streams": "No direct media stream links found.",
        "ai_summary_header": "AI Summary of Results",
        "cannot_summarize": "Could not generate AI summary.",
        "unexpected_error_summary": "An unexpected error occurred while generating AI summary.",
        "sidebar_language_header": "Language / שפה",
        "sidebar_language_select": "Select Language / בחר שפה:",
        "sidebar_debug_mode": "Debug Mode (Show more info and JSON)",
        "sidebar_about_header": "About",
        "sidebar_about_info": "This system uses AI to search the National Library of Israel. Under development.",
        "sidebar_reset_button": "Reset & Start Over",
        "sidebar_shutdown_button": "Shutdown Application",
        "critical_error_params_not_loaded": "Critical Error: Allowed parameters list not loaded. Cannot perform search.",
        "type_query_to_start": "Please type a query in the search box to start.",
        "default_title": "Unknown Title",
        "default_creator": "Unknown Creator",
        "default_id": "Unknown ID",
        "default_value_not_found": "Unknown",
        "error_processing_openapi_schema": "Error processing OpenAPI schema. Using default parameters.",
        "error_openapi_path_not_found": "'/api/v1/search' path not found in OpenAPI schema. Using defaults.",
        "warning_no_parameters_in_schema": "No parameters defined for '/api/v1/search' in OpenAPI schema."
    }
}

# --- constants ---
JSON_ARRAY_RE = re.compile(r'\[\s*\{.*\}\s*\]', re.DOTALL)
SHARED_CLIENT = httpx.AsyncClient()
SEARCH_PROMPT_TEMPLATE = """
You are an expert system for converting natural language user queries into multiple structured JSON parameters for an API search endpoint.\n
Your ONLY output MUST be a valid JSON array of objects, where each object represents a separate query. Do NOT include any introductory or concluding text, explanations, or markdown formatting (like ```json). Just the raw JSON array.\n

**Process the user's query step-by-step to accurately extract multiple parameters for the API call:**\n
1. **Understand User Intent:** Determine the primary goal (e.g., searching books by multiple Israeli authors with a specific theme).\n
2. **Identify Relevant API Parameters:** Map the intent to the most appropriate API parameters:\n
{params_str}\n
3. **Parameter Extraction Guidelines:**\n
    * Extract ALL relevant parameters: 'creator', 'subject', 'materialType', etc., in addition to 'q'.\n
    * **'q' (Main Query):** Use format: **'field,operator,value'**. Fields: 'any', 'title', 'desc', 'creator', 'subject', 'dr_s', 'dr_e'. Operators: 'contains', 'exact'.\n
    * **Names & Entities:** Infer full names (e.g., 'Bialik' -> 'חיים נחמן ביאליק').\n
    * **'materialType':** Use ONLY: 'books', 'articles', 'images', 'audio', 'videos', 'maps', 'journals', 'manuscripts', 'rareBooks'.\n
4. **Deep Query Analysis for Complex Requests:**\n
    * For queries like 'ספרים לילדים בסגנון כיפה אדומה אבל של סופרים ישראלים':\n
        * Theme: From 'כיפה אדומה', infer 'מעשיות', 'ספרות ילדים קלאסית', 'סיפורי עם' for 'q' or 'subject'.\n
        * Authors: Identify well‑known Israeli children’s authors (e.g., לאה גולדברג, גלילה רון פדר) based on common knowledge (no external lookups). Create a separate query for each.\n
        * Material: 'ספרים לילדים' implies `materialType: books`.\n
    * Generate multiple JSON objects, one per author, combining theme and material type.\n
    * For query like 'תמצא לי ספרים מהמאה השמינית שנכתבו על ידי סופרים יהודיים בני אותה התקופה, generate:\n
      you MUST look for in the web for the authors that wrote in the 8th century and are Jewish, and then create a query for each author with the materialType books.\n
      Note: that publicationYearFrom and publicationYearTo are not neccarily needed, because the user asked for books that wrote in spesific time period, but not for books that published in that time period.\n
5. **Construct Final JSON Array:** Each object MUST have 'q' correctly formatted. All values as strings.\n

**Examples:**\n
User query: 'ספרים לילדים בסגנון כיפה אדומה אבל של סופרים ישראלים'\n
AI Response: [\n
    {{ "q": "subject,contains,מעשיות", "materialType": "books", "creator": "לאה גולדברג", "subject": "ספרות ילדים" }},\n
    {{ "q": "subject,contains,מעשיות", "materialType": "books", "creator": "גלילה רון פדר", "subject": "ספרות ילדים" }}\n
]\n

**Limit Parameter Guidelines:**\n
    * Use the 'limit' parameter ONLY to restrict the number of search results returned by the API, not to specify a desired number of final items.\n
    * Valid usage: When the user explicitly requests a limited number of search results, e.g., 'Give me only the first 10 search results for books by Bialik' → include 'limit': '10'.\n
    * Invalid usage:\n
        - Requests for 'the last N results' (e.g., 'Give me the last 10 books') are NOT valid.\n
        - Requests for a specific number of final items (e.g., 'Give me 20 books by Bialik') are NOT valid.\n
    * If the user’s request for 'limit' is invalid, omit the 'limit' parameter in the JSON output.\n

User query: 'Give me only the first 10 search results for books by Bialik'\n
AI Response: [\n
    {{ "q": "creator,exact,חיים נחמן ביאליק", "materialType": "books", "limit": "10" }}\n
]\n

User query: 'Give me the last 10 books by Bialik' or 'Give me 20 books by Bialik'\n
AI Response: [\n
    {{ "q": "creator,exact,חיים נחמן ביאליק", "materialType": "books" }}\n
]\n

User query: '{user_query}'
""".strip()


# --- Function to load OpenAPI schema and extract parameters ---
def load_and_return_openapi_params(lang_pack: dict):
    global OPENAPI_SCHEMA_PATH
    local_allowed_params = []
    local_param_descriptions = {}
    try:
        with open(OPENAPI_SCHEMA_PATH, 'r', encoding='utf-8') as f: 
            schema = json.load(f)
        search_params_schema = schema.get("paths", {}).get("/api/v1/search", {}).get("get", {}).get("parameters", [])
        if not search_params_schema: 
            st.warning(lang_pack["warning_no_parameters_in_schema"] + " Using manual fallback for parameters.")
            manual_params = [
                {"name": "q", "description": "Search query, e.g. 'creator,contains,דוד בן גוריון'"},
                {"name": "materialType", "description": "Type of material (e.g., books, articles)."},
                {"name": "availabilityType", "description": "Availability (e.g., online, physical)."},
                {"name": "sortField", "description": "Field to sort by (e.g., title, creator)."},
                {"name": "sortOrder", "description": "Sort order (asc, desc)."},
                {"name": "lang", "description": "Language of materials (e.g., heb, eng)."},
                {"name": "creator", "description": "Creator of the item."},
                {"name": "subject", "description": "Subject of the item."},
                {"name": "publisher", "description": "Publisher of the item."},
                {"name": "publicationYearFrom", "description": "Start year of publication."},
                {"name": "publicationYearTo", "description": "End year of publication."},
                {"name": "collection", "description": "Collection name."},
                {"name": "contributor", "description": "Contributor to the item."},
                {"name": "isbn", "description": "ISBN value."},
                {"name": "issn", "description": "ISSN value."},
                {"name": "dateFrom", "description": "Start date (YYYY-MM-DD or YYYY)."},
                {"name": "dateTo", "description": "End date (YYYY-MM-DD or YYYY)."},
                {"name": "request_type", "description": "Internal type for media requests (image, video, audio)."}
            ]
            search_params_schema.extend(manual_params)
            seen_names = set()
            unique_schema = []
            for p_schema in search_params_schema:
                if p_schema.get("name") not in seen_names:
                    unique_schema.append(p_schema)
                    seen_names.add(p_schema.get("name"))
            search_params_schema = unique_schema

        extracted_params_set = set()
        for param_schema in search_params_schema:
            name = param_schema.get("name")
            if name:
                extracted_params_set.add(name)
                desc = param_schema.get("description", "").replace("Filter by ", "").strip()
                local_param_descriptions[name] = desc if desc else f"Parameter for {name}"

        local_allowed_params = sorted(list(extracted_params_set))

    except FileNotFoundError:
        st.error(f"{lang_pack['error_processing_openapi_schema']}: OpenAPI schema file not found at {OPENAPI_SCHEMA_PATH}. Using manual fallback.")
        local_allowed_params = [
            "q", "materialType", "availabilityType", "sortField", "sortOrder", "lang",
            "creator", "subject", "publisher", "publicationYearFrom", "publicationYearTo",
            "collection", "contributor", "isbn", "issn", "dateFrom", "dateTo",
            "request_type"
        ]
        local_param_descriptions = {p: f"Default description for {p}" for p in local_allowed_params}

    except json.JSONDecodeError as e:
        st.error(f"{lang_pack['error_processing_openapi_schema']}: Invalid JSON in OpenAPI schema. Using manual fallback. Error: {e}")
        local_allowed_params = [
            "q", "materialType", "availabilityType", "sortField", "sortOrder", "lang",
            "creator", "subject", "publisher", "publicationYearFrom", "publicationYearTo",
            "collection", "contributor", "isbn", "issn", "dateFrom", "dateTo",
            "request_type"
        ]
        local_param_descriptions = {p: f"Default description for {p}" for p in local_allowed_params}
    
    return local_allowed_params, local_param_descriptions

# --- Function 1: Parse user query and generate multiple queries ---
async def parse_user_query(user_query: str, allowed_params: list, param_descs: dict) -> list[dict]:
    global DEBUG_MODE, JSON_ARRAY_RE, SEARCH_PROMPT_TEMPLATE

    param_list_for_prompt = []
    all_param_names_for_prompt = sorted(list(set(allowed_params + list(param_descs.keys()))))
    for param_name in all_param_names_for_prompt:
        if param_name in allowed_params:
            description = param_descs.get(param_name, f"Parameter for {param_name} (no specific description).")
            param_list_for_prompt.append(f"- **'{param_name}'**: {description}")
    
    params_str = "\n".join(param_list_for_prompt)

    prompt_for_ai = SEARCH_PROMPT_TEMPLATE.format(
        params_str=params_str,
        user_query=user_query.replace('"', '\\"')
    )
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        generation_config = genai.types.GenerationConfig(temperature=0.1)
        chat = model.start_chat(history=[])
        ai_resp = await chat.send_message_async(prompt_for_ai, generation_config=generation_config)
        ai_response_text = ai_resp.text.strip()
        
        if DEBUG_MODE:
            st.write("DEBUG: Raw AI response (for query parsing):")
            st.text(ai_response_text)

        # search for a valid JSON array in the AI response
        json_match = JSON_ARRAY_RE.search(ai_response_text)
        if json_match:
            json_str = json_match.group(0)
            try:
                parsed_queries = json.loads(json_str)
            except json.JSONDecodeError:
                if DEBUG_MODE:
                    st.write("DEBUG: לJSON לא תקין מתקבל מתגובת הבינה המלאכותית")
                st.warning("התקבלה תגובה לא תקינה מהבינה המלאכותית")
                return [{"q": "any,contains,כללי"}]
        else:
            if DEBUG_MODE:
                st.write("DEBUG: JSON בדוגמת מערך לא נמצא בתגובה של הבינה המלאכותית")
            st.warning("אין תוצאות - לא נמצאה שאילתה תקינה")
            return [{"q": "any,contains,כללי"}]

        # insure parsed_queries is a list
        if not isinstance(parsed_queries, list):
            parsed_queries = [parsed_queries]

        sanitized_queries = []
        for query in parsed_queries:
            # filter out only allowed parameters
            filtered_params = {k: str(v).strip() for k, v in query.items() if k in allowed_params}
            q_candidate = filtered_params.get("q")
            q_is_valid = False
            if q_candidate and isinstance(q_candidate, str) and q_candidate.strip():
                parts = q_candidate.strip().split(',', 2)
                if len(parts) == 3 and all(p.strip() for p in parts):
                    filtered_params["q"] = f"{parts[0].strip()},{parts[1].strip()},{parts[2].strip()}"
                    q_is_valid = True
            if not q_is_valid:
                filtered_params["q"] = "any,contains,כללי"
                if DEBUG_MODE:
                    st.write("DEBUG: השתמשתי ב-q ברירת מחדל כי המקור לא תקין")
            
            sanitized_queries.append(filtered_params)

        if DEBUG_MODE:
            st.write("DEBUG: השאילתות הסופיות לשימוש בחיפוש:")
            st.json(sanitized_queries)
        return sanitized_queries

    except Exception as e:
        st.error(f"שגיאה לא צפויה במהלך עיבוד השאילתה: {type(e).__name__} - {e}")
        st.warning("אין תוצאות - התרחשה שגיאה")
        return [{"q": "any,contains,כללי"}]

# --- Function 2: Performs NLI search for multiple queries ---
async def perform_nli_search(params_list: list[dict], current_allowed_params: list) -> list[dict]:
    global DEBUG_MODE, FASTAPI_BASE_URL, NLI_API_KEY, SHARED_CLIENT

    results = []
    tasks = []

    # --- Create one task per set of search parameters ---
    for params in params_list:
        search_params_to_send = {}
        for k, v_raw in params.items():
            v = str(v_raw).strip()
            if k in current_allowed_params and k != "request_type" and v:
                if k == "count_only" and v.lower() == "true":
                    pass # Skip count_only parameter because it's deleting results and save only count - so not really needed
                    search_params_to_send[k] = True
                else:
                    search_params_to_send[k] = v

        q_value_for_api = search_params_to_send.get("q")
        q_is_critically_valid = False
        if isinstance(q_value_for_api, str) and q_value_for_api:
            parts = q_value_for_api.split(',', 2)
            if len(parts) == 3 and all(p.strip() for p in parts):
                q_is_critically_valid = True
                search_params_to_send["q"] = f"{parts[0].strip()},{parts[1].strip()},{parts[2].strip()}"

        if not q_is_critically_valid:
            search_params_to_send["q"] = "any,contains,כללי"

        search_params_to_send["api_key"] = NLI_API_KEY

        if DEBUG_MODE:
            st.write("DEBUG: Parameters sent to FastAPI /api/v1/search endpoint:")
            st.json(search_params_to_send)

        # Build the coroutine, but do not await yet
        task = SHARED_CLIENT.get(
            f"{FASTAPI_BASE_URL}/api/v1/search",
            params=search_params_to_send,
            timeout=35.0
        )
        tasks.append(task)

    # --- Execute all requests concurrently (once!) ---
    try:
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for response in responses:
            if isinstance(response, Exception):
                results.append({"total_results": 0, "items": []})
            else:
                try:
                    response.raise_for_status()
                    results.append(response.json())
                except Exception as e:
                    if DEBUG_MODE:
                        st.error(f"An unexpected error occurred while processing response: {type(e).__name__} - {e}")
                    results.append({"total_results": 0, "items": []})
    except Exception as e:
        st.error(f"An unexpected error occurred while performing NLI search: {type(e).__name__} - {e}")
        for _ in tasks:
            results.append({"total_results": 0, "items": []})

    return results


# --- Helper function to extract simple values ---
def extract_value_from_json(value: str, default_value: str) -> str:
    try:
        parsed = json.loads(value.replace("'", '"'))
        if isinstance(parsed, dict) and '@value' in parsed:
            return str(parsed['@value']).strip() or default_value
    except json.JSONDecodeError:
        pass
    if isinstance(value, list):
        return str(value[0]).strip() or default_value if value else default_value
    else:
        return value.strip() or default_value

def get_simple_field(item: dict, key_name: str, lang_pack: dict, default_lang_key: str) -> str:
    default_value = lang_pack.get(default_lang_key, "")
    value = item.get(key_name)
    
    if isinstance(value, str):
        if "@value" in value:
            return extract_value_from_json(str(value), default_value)
    
    if isinstance(value, list):
        if "@value" in value[0]:
            return extract_value_from_json(str(value[0]), default_value)
    return str(value).strip() or default_value if value is not None else default_value

# --- Function 3: Processes and displays results ---
async def process_and_display_results(user_query: str, search_results_list: list[dict], lang_pack: dict):
    global DEBUG_MODE, FASTAPI_BASE_URL, SHARED_CLIENT
    
    items_images = []

    st.subheader(lang_pack["search_in_progress"])

    # Flatten all_items
    all_items = [item for result in search_results_list if result and result.get("items") for item in result["items"]]

    if not all_items:
        st.info(lang_pack["no_results"])
        return

    if DEBUG_MODE:
        st.write("### DEBUG: First Item Raw JSON (from your FastAPI server)")
        st.json(all_items[0], expanded=False)

    needs_manifest = []
    metadata = {}  # record_id → (title, record_id)
    for item in all_items:
        item_id = get_simple_field(item, "@id", lang_pack, "default_id")  # Use 'id' for links
        record_id = get_simple_field(item, "http://purl.org/dc/elements/1.1/recordid", lang_pack, "default_id")  # Use 'recordId' for manifest
            
        thumb = get_simple_field(
            item, "http://purl.org/dc/elements/1.1/thumbnail",
            lang_pack, "default_value_not_found"
        )

        if (not thumb.startswith(("http://", "https://")) and record_id != lang_pack["default_id"]):
            needs_manifest.append(record_id)
            metadata[record_id] = (
                get_simple_field(item, "http://purl.org/dc/elements/1.1/title", lang_pack, "default_title"),
                record_id
            )

    # Get all manifest fetches at once
    async def fetch_manifest(rid):
        url = f"{FASTAPI_BASE_URL}/api/v1/manifest/{rid}"
        try:
            resp = await SHARED_CLIENT.get(url, timeout=10.0)
            resp.raise_for_status()
            return rid, resp.json()
        except Exception as e:
            if DEBUG_MODE:
                st.write(f"DEBUG: manifest fetch failed for {rid}: {e}")
            return rid, None

    manifest_tasks = [fetch_manifest(rid) for rid in needs_manifest]
    for rid, manifest_data in await asyncio.gather(*manifest_tasks):
        if not manifest_data:
            continue

        seqs = manifest_data.get("sequences", [])
        if not seqs:
            if DEBUG_MODE:
                st.write(f"DEBUG: no sequences in manifest {rid}")
            continue

        # Get the first valid image and store it
        found = False
        for canvas in seqs[0].get("canvases", []):
            for img in canvas.get("images", []):
                url = img.get("resource", {}).get("@id", "")
                if (url.lower().endswith((".jpg", ".png"))
                    and "logo" not in url.lower()):
                    title, record_id = metadata[rid]
                    items_images.append({
                        "recordId": record_id,
                        "title": title,
                        "thumbnailUrl": url
                    })
                    if DEBUG_MODE:
                        st.write(f"DEBUG: using manifest image {url} for {rid}")
                    found = True
                    break
            if found:
                break

    # Render the items and images
    for item in all_items:
        title = get_simple_field(item, "http://purl.org/dc/elements/1.1/title", lang_pack, "default_title")
        creator = get_simple_field(item, "http://purl.org/dc/elements/1.1/creator", lang_pack, "default_creator")
        item_id = get_simple_field(item, "@id", lang_pack, "default_id")
        record_id = get_simple_field(item, "http://purl.org/dc/elements/1.1/recordid", lang_pack, "default_id")

        with st.expander(f"**{title}** ({creator})"):
            if item_id != lang_pack["default_id"]:
                st.markdown(f"**{lang_pack['item_page_link_text']}:** [{item_id}]({item_id})")
            else:
                st.markdown(f"*{lang_pack['default_id']}*")

            # try to get thumbnail
            thumb = get_simple_field(item, "http://purl.org/dc/elements/1.1/thumbnail",
                                    lang_pack, "default_value_not_found")
            if thumb.startswith(("http://", "https://")):
                st.image(thumb, caption=title, use_container_width=True)
            else:
                # try to get from manifest images
                img_info = next(
                    (img for img in items_images if img["recordId"] == record_id), None
                )
                if img_info:
                    st.image(img_info["thumbnailUrl"], caption=title, use_container_width=True)    

    # AI Summary Section
    st.subheader(lang_pack["ai_summary_header"])
    try:
        ai_sum_res = await SHARED_CLIENT.post(
            f"{FASTAPI_BASE_URL}/api/v1/query-ai",
            json={"prompt": user_query, "context": {"results": search_results_list}, "items_images": items_images},
            timeout=45.0
        )
        ai_sum_res.raise_for_status()
        ai_response = ai_sum_res.json()
        response_text = ai_response.get("response_text", lang_pack["cannot_summarize"])
        
        st.write(response_text, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"{lang_pack['unexpected_error_summary']}: {type(e).__name__} - {e}")
    

# --- Main function for the Streamlit App ---
async def main_streamlit_app():
    global DEBUG_MODE, LANGUAGES
    # Initialize session state attributes
    if 'language' not in st.session_state:
        st.session_state.language = "עברית"
    if 'debug_mode' not in st.session_state:
        st.session_state.debug_mode = False
    if 'user_query_value_holder' not in st.session_state:
        st.session_state.user_query_value_holder = ""

    lang_pack = LANGUAGES[st.session_state.language]

    st.set_page_config(page_title=lang_pack["page_title"], page_icon="📚", layout="wide", initial_sidebar_state="expanded")

    # --- Sidebar ---
    st.sidebar.header(lang_pack["sidebar_language_header"])
    selected_language = st.sidebar.radio(
        lang_pack["sidebar_language_select"],
        list(LANGUAGES.keys()),
        index=list(LANGUAGES.keys()).index(st.session_state.language),
        key="language_radio_selector_key_v2"
    )
    if selected_language != st.session_state.language:
        st.session_state.language = selected_language
        if 'params_lang_loaded_for' in st.session_state:
            del st.session_state['params_lang_loaded_for']
        st.rerun()

    st.session_state.debug_mode = st.sidebar.checkbox(
        lang_pack["sidebar_debug_mode"],
        value=st.session_state.debug_mode,
        key="debug_mode_checkbox_selector_key_v2"
    )

    # Load OpenAPI parameters
    if 'allowed_nli_params_session' not in st.session_state or \
       'nli_param_descriptions_session' not in st.session_state or \
       st.session_state.get('params_lang_loaded_for') != st.session_state.language:
        
        loaded_params, loaded_descs = load_and_return_openapi_params(lang_pack)
        st.session_state['allowed_nli_params_session'] = loaded_params
        st.session_state['nli_param_descriptions_session'] = loaded_descs
        st.session_state['params_lang_loaded_for'] = st.session_state.language
    
    current_allowed_params = st.session_state.get('allowed_nli_params_session', [])
    current_param_descs = st.session_state.get('nli_param_descriptions_session', {})

    # --- Main Page ---
    st.title(lang_pack["header"])
    st.write(lang_pack["subheader"])
    st.markdown("---")

    user_input_from_field = st.text_input(
        lang_pack["search_placeholder"],
        value=st.session_state.user_query_value_holder,
        key="search_text_input_widget_key"
    )
    st.session_state.user_query_value_holder = user_input_from_field
    
    DEBUG_MODE = st.session_state.get("debug_mode", False)
    if st.button(lang_pack["search_button"], key="search_button_main_trigger_key", type="primary"):
        query_to_process = st.session_state.user_query_value_holder

        if query_to_process.strip():
            if not current_allowed_params:
                st.error(lang_pack["critical_error_params_not_loaded"])
                return
            
            with st.spinner(lang_pack["analyzing_query"]):
                parsed_queries = await parse_user_query(query_to_process, current_allowed_params, current_param_descs)
            
            with st.spinner(lang_pack["searching_nli"]):
                search_results_list = await perform_nli_search(parsed_queries, current_allowed_params)
        
            if search_results_list and any("items" in res and res["items"] for res in search_results_list):
                await process_and_display_results(query_to_process, search_results_list, lang_pack)
            else:
                st.info(lang_pack["no_results"])
        else:
            st.info(lang_pack["type_query_to_start"])
    
    st.sidebar.header(lang_pack["sidebar_about_header"])
    st.sidebar.info(lang_pack["sidebar_about_info"])
    st.sidebar.markdown("---")

    if st.sidebar.button(lang_pack["sidebar_reset_button"], key="reset_button_main_trigger_key"):
        keys_to_clear_on_reset = [
            'allowed_nli_params_session',
            'nli_param_descriptions_session',
            'params_lang_loaded_for',
        ]
        for key in keys_to_clear_on_reset:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.user_query_value_holder = ""
        st.rerun()

    if st.sidebar.button(lang_pack["sidebar_shutdown_button"], key="shutdown_button_main_trigger_key"):
        try:
            async with SHARED_CLIENT as client:
                response = await client.post(f"{FASTAPI_BASE_URL}/api/v1/shutdown")
                response.raise_for_status()
                st.success("האפליקציה נכבית...")
        except Exception as e:
            st.error(f"שגיאה בכיבוי האפליקציה: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main_streamlit_app())