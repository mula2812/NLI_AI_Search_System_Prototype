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

# --- API Key Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyD_7sQUckaUMIzGCAWoxpoUhEDOFzXHuec")
if not GEMINI_API_KEY:
    st.error("GEMINI_API_KEY environment variable not set. Please set it in your environment.")
    st.stop()
genai.configure(api_key=GEMINI_API_KEY)

NLI_API_KEY = os.getenv("NLI_API_KEY", "OHOwpHbdR3Kt6p4S7qjBHddpUam0jHBMsvF5gXPz")
if not NLI_API_KEY:
    st.error("NLI_API_KEY environment variable not set. Please set it in your environment.")
    st.stop()

# --- Language Configuration ---
LANGUAGES = {
    "עברית": {
        "page_title": "מערכת חיפוש הספרייה הלאומית (AI)",
        "header": "📚 מערכת חיפוש הספרייה הלאומית (גרסת AI)",
        "subheader": "הקלד שאילתה בשפה טבעית והמערכת תנסה למצוא תוצאות.",
        "search_placeholder": "לדוגמה: ספרים של ביאליק שיצאו אחרי 1920",
        "search_button": "🔍 חפש",
        "analyzing_query": "מנתח את שאילתתך בעזרת AI...",
        "searching_nli": "מחפש מידע בספרייה הלאומית...",
        "results_header": "תוצאות חיפוש",
        "no_results": "לא נמצאו תוצאות עבור השאילתה שלך.",
        "no_relevant_items": "לא נמצאו פריטים רלוונטיים עבור השאילתה שלך.",
        "media_requested": "מדיה שביקשת",
        "item_page_link_text": "קישור לדף הפריט בספרייה הלאומית",
        "no_direct_image": "לא ניתן להציג תמונה ישירה עבור פריט זה.",
        "no_direct_media_streams": "לא אותרו קישורי מדיה (וידאו/אודיו) ישירים.",
        "ai_summary_header": "סיכום AI של התוצאות",
        "cannot_summarize": "לא ניתן היה ליצור סיכום AI.",
        "unexpected_error_summary": "אירעה שגיאה בלתי צפויה במהלך יצירת סיכום AI.",
        "show_raw_json": "הצג נתוני JSON גולמיים (פריט ראשון)",
        "sidebar_language_header": "Language / שפה",
        "sidebar_language_select": "בחר שפה / Select Language:",
        "sidebar_debug_mode": "מצב דיבאג (הצג מידע נוסף ו-JSON)",
        "sidebar_about_header": "אודות",
        "sidebar_about_info": "מערכת זו משתמשת ב-AI לחיפוש במאגרי הספרייה הלאומית. בפיתוח.",
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
        "search_placeholder": "e.g., books by Bialik published after 1920",
        "search_button": "🔍 Search",
        "analyzing_query": "Analyzing your query with AI...",
        "searching_nli": "Searching the National Library...",
        "results_header": "Search Results",
        "no_results": "No results found for your query.",
        "no_relevant_items": "No relevant items found for your query.",
        "media_requested": "Requested Media",
        "item_page_link_text": "Link to item page at the National Library",
        "no_direct_image": "No direct image available for this item.",
        "no_direct_media_streams": "No direct media stream links found.",
        "ai_summary_header": "AI Summary of Results",
        "cannot_summarize": "Could not generate AI summary.",
        "unexpected_error_summary": "An unexpected error occurred while generating AI summary.",
        "show_raw_json": "Show Raw JSON Data (first item)",
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

# --- Function to load OpenAPI schema and extract parameters ---
def load_and_return_openapi_params(lang_pack: dict):
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
                # {"name": "count_only", "description": "Return only total results count (true/false)."}
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

        critical_params_for_ai = {
            "q": (
                "Main search query. Format: 'field,operator,value'.\n"
                "Valid fields: **'any'**, **'title'**, **'desc'**, **'creator'**, **'subject'**, "
                "**'dr_s'**, **'dr_e'**.\n"
                "Valid operators: **'contains'**, **'exact'**.\n"
                "Examples: 'creator,contains,David Ben-Gurion', 'subject,exact,History'."
            ),
            "materialType": (
                "Material type. Only use: 'books', 'articles', 'images', 'audio', 'videos', 'maps', 'journals', 'manuscripts', 'rareBooks'."
            ),
            "request_type": "Special request type for media (e.g., 'image', 'video', 'audio')."
            # "count_only": "Set to 'true' if user asks for a count of items."
        }
        for cp, cd in critical_params_for_ai.items():
            extracted_params_set.add(cp)
            local_param_descriptions[cp] = cd
        
        local_allowed_params = sorted(list(extracted_params_set))

    except FileNotFoundError:
        st.error(f"{lang_pack['error_processing_openapi_schema']}: OpenAPI schema file not found at {OPENAPI_SCHEMA_PATH}. Using manual fallback.")
        local_allowed_params = [
            "q", "materialType", "availabilityType", "sortField", "sortOrder", "lang",
            "creator", "subject", "publisher", "publicationYearFrom", "publicationYearTo",
            "collection", "contributor", "isbn", "issn", "dateFrom", "dateTo",
            "request_type", "count_only"
        ]
        local_param_descriptions = {p: f"Default description for {p}" for p in local_allowed_params}
        local_param_descriptions.update(critical_params_for_ai)

    except json.JSONDecodeError as e:
        st.error(f"{lang_pack['error_processing_openapi_schema']}: Invalid JSON in OpenAPI schema. Using manual fallback. Error: {e}")
        local_allowed_params = [
            "q", "materialType", "availabilityType", "sortField", "sortOrder", "lang",
            "creator", "subject", "publisher", "publicationYearFrom", "publicationYearTo",
            "collection", "contributor", "isbn", "issn", "dateFrom", "dateTo",
            "request_type", "count_only"
        ]
        local_param_descriptions = {p: f"Default description for {p}" for p in local_allowed_params}
        local_param_descriptions.update(critical_params_for_ai)
    
    return local_allowed_params, local_param_descriptions

# --- Function 1: Parse user query and generate multiple queries ---
async def parse_user_query(user_query: str, allowed_params: list, param_descs: dict) -> list[dict]:
    param_list_for_prompt = []
    all_param_names_for_prompt = sorted(list(set(allowed_params + list(param_descs.keys()))))
    for param_name in all_param_names_for_prompt:
        if param_name in allowed_params:
            description = param_descs.get(param_name, f"Parameter for {param_name} (no specific description).")
            param_list_for_prompt.append(f"- **'{param_name}'**: {description}")
    
    params_str = "\n".join(param_list_for_prompt)

    prompt_for_ai = (
        "You are an expert system for converting natural language user queries into multiple structured JSON parameters for an API search endpoint.\n"
        "Your ONLY output MUST be a valid JSON array of objects, where each object represents a separate query. Do NOT include any introductory or concluding text, explanations, or markdown formatting (like ```json). Just the raw JSON array.\n"
        "\n"
        "**Process the user's query step-by-step to accurately extract multiple parameters for the API call:**\n"
        "1. **Understand User Intent:** Determine the primary goal (e.g., searching books by multiple Israeli authors with a specific theme).\n"
        "2. **Identify Relevant API Parameters:** Map the intent to the most appropriate API parameters:\n"
        f"{params_str}\n"
        "3. **Parameter Extraction Guidelines:**\n"
        "    * Extract ALL relevant parameters: 'creator', 'subject', 'materialType', etc., in addition to 'q'.\n"
        "    * **'q' (Main Query):** Use format: **'field,operator,value'**. Fields: 'any', 'title', 'desc', 'creator', 'subject', 'dr_s', 'dr_e'. Operators: 'contains', 'exact'.\n"
        "    * **Names & Entities:** Infer full names (e.g., 'Bialik' -> 'חיים נחמן ביאליק').\n"
        "    * **'materialType':** Use ONLY: 'books', 'articles', 'images', 'audio', 'videos', 'maps', 'journals', 'manuscripts', 'rareBooks'.\n"
        "4. **Deep Query Analysis for Complex Requests:**\n"
        "    * For queries like 'ספרים לילדים בסגנון כיפה אדומה אבל של סופרים ישראלים':\n"
        "        * Theme: From 'כיפה אדומה', infer 'מעשיות', 'ספרות ילדים קלאסית', 'סיפורי עם' for 'q' or 'subject'.\n"
        "        * Authors: Identify well-known Israeli children’s authors (e.g., לאה גולדברג, גלילה רון פדר) based on common knowledge (no external lookups). Create a separate query for each.\n"
        "        * Material: 'ספרים לילדים' implies `materialType: books`.\n"
        "    * Generate multiple JSON objects, one per author, combining theme and material type.\n"
        "5. **Construct Final JSON Array:** Each object MUST have 'q' correctly formatted. All values as strings.\n"
        "\n"
        "**Examples:**\n"
        "User query: 'ספרים לילדים בסגנון כיפה אדומה אבל של סופרים ישראלים'\n"
        "AI Response: [\n"
        "    {\"q\": \"subject,contains,מעשיות\", \"materialType\": \"books\", \"creator\": \"לאה גולדברג\", \"subject\": \"ספרות ילדים\"},\n"
        "    {\"q\": \"subject,contains,מעשיות\", \"materialType\": \"books\", \"creator\": \"גלילה רון פדר\", \"subject\": \"ספרות ילדים\"}\n"
        "]\n"
        f"User query: '{user_query}'"
    )
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        generation_config = genai.types.GenerationConfig(temperature=0.1)
        chat = model.start_chat(history=[])
        ai_resp = await chat.send_message_async(prompt_for_ai, generation_config=generation_config)
        ai_response_text = ai_resp.text.strip()
        
        if st.session_state.get("debug_mode", False):
            st.write("DEBUG: Raw AI response (for query parsing):")
            st.text(ai_response_text)

        # Clean response and extract JSON using regex
        json_match = re.search(r'\[\s*\{.*\}\s*\]', ai_response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            parsed_queries = json.loads(json_str)
        else:
            parsed_queries = [{"q": "any,contains,כללי"}]

        if not isinstance(parsed_queries, list):
            parsed_queries = [parsed_queries]

        sanitized_queries = []
        for query in parsed_queries:
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
            sanitized_queries.append(filtered_params)

        if st.session_state.get("debug_mode", False):
            st.write("DEBUG: Final parsed queries to be used for search:")
            st.json(sanitized_queries)
        return sanitized_queries

    except Exception as e:
        st.error(f"An unexpected error occurred during query parsing: {type(e).__name__} - {e}")
        return [{"q": "any,contains,כללי"}]

# --- Function 2: Performs NLI search for multiple queries ---
async def perform_nli_search(params_list: list[dict], current_allowed_params: list) -> list[dict]:
    results = []
    async with httpx.AsyncClient() as client:
        for params in params_list:
            search_params_to_send = {}
            for k, v_raw in params.items():
                v = str(v_raw).strip()
                if k in current_allowed_params and k != "request_type" and v:
                    if k == "count_only" and v.lower() == "true":
                        print("") #search_params_to_send[k] = True
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
            if st.session_state.get("debug_mode", False):
                st.write("DEBUG: Parameters sent to FastAPI /api/v1/search endpoint:")
                st.json(search_params_to_send)
            try:
                response = await client.get(f"{FASTAPI_BASE_URL}/api/v1/search", params=search_params_to_send, timeout=35.0)
                response.raise_for_status()
                results.append(response.json())
            except httpx.HTTPStatusError as e:
                st.error(f"Error searching NLI API (HTTP {e.response.status_code}): {e.response.text[:500]}...")
                results.append({"total_results": 0, "items": []})
            except Exception as e:
                st.error(f"An unexpected error occurred while performing NLI search: {type(e).__name__} - {e}")
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
    st.subheader(lang_pack["results_header"])

    all_items = []
    for search_results in search_results_list:
        if not search_results or "items" not in search_results or not search_results["items"]:
            continue
        items = search_results.get("items", [])
        all_items.extend(items)

    if not all_items:
        st.info(lang_pack["no_results"])
        return

    if st.session_state.get("debug_mode", False):
        st.write("### DEBUG: First Item Raw JSON (from your FastAPI server)")
        st.json(all_items[0], expanded=False)

    for item in all_items:
        item_title = get_simple_field(item, "http://purl.org/dc/elements/1.1/title", lang_pack, "default_title")
        item_creator = get_simple_field(item, "http://purl.org/dc/elements/1.1/creator", lang_pack, "default_creator")
        item_id = get_simple_field(item, "@id", lang_pack, "default_id")  # Use 'id' for links
        record_id = get_simple_field(item, "http://purl.org/dc/elements/1.1/recordid", lang_pack, "default_id")  # Use 'recordId' for manifest

        nli_public_link = f"{item}" if item_id != lang_pack["default_id"] else "#"
            
        with st.expander(f"**{item_title}** ({item_creator})"):

            if item_id != lang_pack["default_id"]:
                st.markdown(f"**{lang_pack['item_page_link_text']}:** [{item_id}]({nli_public_link})")
            else:
                st.markdown(f"*{lang_pack['default_id']}*")

            # Image handling - Try thumbnailUrl first
            thumbnail_info = get_simple_field(item, "http://purl.org/dc/elements/1.1/thumbnail", lang_pack, "default_value_not_found")

            if thumbnail_info and not thumbnail_info == lang_pack["default_value_not_found"]:
                #insure thumbnail_info is a link
                if thumbnail_info.startswith("http://") or thumbnail_info.startswith("https://"):
                    image_url = thumbnail_info

                    if st.session_state.get("debug_mode", False):
                        st.write(f"DEBUG: Using thumbnail URL: {thumbnail_info}")
                    st.image(image_url, caption=item_title , use_container_width=True)

            elif record_id != lang_pack["default_id"]:
                try:
                    async with httpx.AsyncClient() as client:
                        print(f"DEBUG: Attempting to fetch manifest for recordId: {FASTAPI_BASE_URL}/api/v1/manifest/{record_id}")
                        manifest_resp = await client.get(f"{FASTAPI_BASE_URL}/api/v1/manifest/{record_id}")
                        manifest_resp.raise_for_status()
                        manifest_data = manifest_resp.json()
                        if "sequences" in manifest_data and manifest_data["sequences"]:
                            canvases = manifest_data["sequences"][0].get("canvases", [])
                            for canvas in canvases:
                                images = canvas.get("images", [])
                                for image in images:
                                    resource = image.get("resource", {})
                                    image_url = resource.get("@id", "")
                                    if (image_url.lower().endswith(('.jpg', '.png')) and 
                                        "logo" not in image_url.lower()):
                                        if st.session_state.get("debug_mode", False):
                                            st.write(f"DEBUG: Using manifest image URL: {image_url}")
                                        st.image(image_url, caption=item_title, use_container_width=True)
                                        break
                                else:
                                    continue
                            else:
                                if st.session_state.get("debug_mode", False):
                                    st.write(f"DEBUG: No suitable image found in manifest for {record_id}")
                except Exception as e:
                    if st.session_state.get("debug_mode", False):
                        st.write(f"DEBUG: Failed to get manifest for {record_id}: {e}")

    # AI Summary Section
    st.subheader(lang_pack["ai_summary_header"])
    try:
        async with httpx.AsyncClient() as client:
            ai_sum_res = await client.post(
                f"{FASTAPI_BASE_URL}/api/v1/query-ai",
                json={"prompt": user_query, "context": {"results": search_results_list}},
                timeout=45.0
            )
            ai_sum_res.raise_for_status()
            st.markdown(ai_sum_res.json().get("response_text", lang_pack["cannot_summarize"]))
    except Exception as e:
        st.error(f"{lang_pack['unexpected_error_summary']}: {type(e).__name__} - {e}")
    
    st.markdown("---")
    if st.checkbox(lang_pack["show_raw_json"], key="show_raw_json_checkbox_main_key_v2"):
        if all_items:
            st.json(all_items[0])
        else:
            st.write("אין פריטים להצגת JSON.")

# --- Main function for the Streamlit App ---
async def main_streamlit_app():
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
        st.write("כיבוי האפליקציה...")
        os._exit(0)

if __name__ == "__main__":
    asyncio.run(main_streamlit_app())