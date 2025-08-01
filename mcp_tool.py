import json
import os
import re
import threading
import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Path, Body, Response
from pydantic import BaseModel, Field
from typing import List, Dict
import httpx
import google.generativeai as genai

# Configuration
NLI_API_KEY = os.getenv("NLI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Google Gemini client
genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(
    title="NLI AI Integration API",
    version="1.10",
    description="Integrates NLI OpenLibrary APIs with Google Gemini AI"
)

BASE_SEARCH_URL = "https://api.nli.org.il/openlibrary/search"
BASE_IIIF_IMAGE = "https://iiif.nli.org.il/IIIFv21"
BASE_IIIF_MANIFEST = f"{BASE_IIIF_IMAGE}/{{recordId}}/manifest"

class AIRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    context: dict | None = None
    items_images: List[Dict[str, str]]  # List of dictionaries with recordId and image URL

@app.get("/api/v1/search")
async def search_nli(
    q: str = Query(..., alias="q", description="Search query, e.g. 'creator,contains,דוד בן גוריון'"),
    output_format: str = Query("json", alias="output_format", description="Response format: json or xml"),
    count_only: bool = Query(False, description="Return only total_results count"),
    limit: int = Query(100, alias="limit", ge=1, le=500, description="Max records per page, need to be used only if the user want to limit the number of results search itselfs not the final results, e.g not if he ask for 10 books, but if he ask for 10 search results"),
    offset: int = Query(0, alias="offset", ge=0, description="Pagination offset"),
    materialType: str | None = Query(None),
    availabilityType: str | None = Query(None),
    sortField: str | None = Query(None),
    sortOrder: str | None = Query(None),
    facet_field: list[str] = Query([], alias="facet.field"),
    facet_limit: int | None = Query(None, alias="facet.limit"),
    facet_offset: int | None = Query(None, alias="facet.offset"),
    facet_sort: str | None = Query(None, alias="facet.sort"),
    fields: list[str] = Query([], description="Fields to include"),
    lang: str | None = Query(None),
    creator: str | None = Query(None),
    subject: str | None = Query(None),
    publisher: str | None = Query(None),
    publicationYearFrom: int | None = Query(None),
    publicationYearTo: int | None = Query(None),
    collection: str | None = Query(None),
    contributor: str | None = Query(None),
    isbn: str | None = Query(None),
    issn: str | None = Query(None),
    dateFrom: str | None = Query(None),
    dateTo: str | None = Query(None)
):
    global NLI_API_KEY, BASE_SEARCH_URL

    params = {
        "api_key": NLI_API_KEY,
        "query": q,
        "output_format": output_format,
        "rows": limit,
        "start": offset
    }
    optional = {
        "material_type": materialType,
        "availability_type": availabilityType,
        "sortField": sortField,
        "sort_order": sortOrder,
        "language": lang,
        "creator": creator,
        "subject": subject,
        "publisher": publisher,
        "publication_year_from": publicationYearFrom,
        "publication_year_to": publicationYearTo,
        "collection": collection,
        "contributor": contributor,
        "isbn": isbn,
        "issn": issn,
        "start_date": dateFrom,
        "end_date": dateTo
    }
    for key, val in optional.items():
        if val is not None:
            params[key] = val
    if facet_field:
        params["facet.field"] = facet_field
    if facet_limit is not None:
        params["facet.limit"] = facet_limit
    if facet_offset is not None:
        params["facet.offset"] = facet_offset
    if facet_sort:
        params["facet.sort"] = facet_sort
    if fields:
        params["fields"] = ",".join(fields)

    async with httpx.AsyncClient() as client:
        resp = await client.get(BASE_SEARCH_URL, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    
    data = resp.json()
    
    if isinstance(data, list):
        total = len(data)
        items = data
        if count_only:
            pass 
        return {"total_results": total, "items": items[offset:offset+limit]}

    total = data.get("total_results", 0)
    if count_only:
        pass
    items = data.get("items", [])
    return {"total_results": total, "items": items[offset:offset+limit]}

@app.get("/api/v1/image/{identifier}")
async def get_image(
    identifier: str = Path(...), region: str = Query("full"), size: str = Query("max"),
    rotation: float = Query(0.0), quality: str = Query("default"), fmt: str = Query("jpg", alias="format")
):
    global BASE_IIIF_IMAGE

    url = f"{BASE_IIIF_IMAGE}/{identifier}/{region}/{size}/{rotation}/{quality}.{fmt}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return Response(content=resp.content, media_type=f"image/{fmt}")

@app.get("/api/v1/manifest/{recordId}")
async def get_manifest(recordId: str = Path(...)):
    global NLI_API_KEY, BASE_IIIF_MANIFEST

    url = BASE_IIIF_MANIFEST.format(recordId=recordId)
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

@app.get("/api/v1/stream/{itemId}")
async def get_stream(itemId: str = Path(...), fmt: str = Query("all", alias="format")):
    global NLI_API_KEY, BASE_SEARCH_URL

    params = {"api_key": NLI_API_KEY, "query": f"RecordId,exact,{itemId}", "format": "json", "rows": 1, "start": 0}
    async with httpx.AsyncClient() as client:
        resp = await client.get(BASE_SEARCH_URL, params=params)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    data = resp.json()
    items = data.get("items", [])
    if not items:
        raise HTTPException(status_code=404, detail="Item not found")
    doc = items[0]
    streams = {}
    if fmt in ("mp4","all") and doc.get("stream_url_mp4"):
        streams["mp4"] = doc["stream_url_mp4"]
    if fmt in ("hls","all") and doc.get("stream_url_hls"):
        streams["hls"] = doc["stream_url_hls"]
    if fmt in ("audio","all") and doc.get("audio_url"):
        streams["audio"] = doc["audio_url"]
    return streams

@app.post("/api/v1/query-ai")
async def query_ai(request: AIRequest = Body(...)):
    if not request.context:
        raise HTTPException(status_code=400, detail="Missing context: provide search results in 'context' field to summarize")
    system_msg = (
        "You are an advanced AI assistant for the National Library of Israel. "
        "Your goal is to take a user's natural-language question and a set of JSON-formatted search results (context) and list of all the items that have image url's, the list contains dictionaries that contain recoredid and thier image link,"
        "and deliver a precise, well-structured answer in Hebrew, or in English if the user's question is in English. "
        "The context contains multiple search results under 'results'. "
        "Analyze each relevant result, extract pertinent items, and combine them into a cohesive response directly addressing the user's question. "
        "Format answers in complete sentences, using clear and user-friendly language in the appropriate language (Hebrew or English) in keep the revently to the user question and simple for understanding. "
        "If no matching data is available, explicitly state that no results were found. "
        "include photos of the items in the answer, but only if they are relevant to the question and if they are available in the items_images (if the relevent choosen item from the content have the same recordid the exist in the items_images)." \
        "do it by using the image url from the items_images list that you get in the request, and if there is no image url for the item you can use the image url from the context, but only if it is relevant to the question. "
        "If the item has no image, do not include it in the response. "
        "If the item has an image, include it in the response text as an HTML <img> tag with the image URL from the items_images list, and if there is no image url in the items_images list you can use the image url from the context, but only if it is relevant to the question. "
        "keep the image size to a maximum of 200px width and height but try to do them proporstional to the real image (if needed minimize thier size a little bit for this), and use the 'alt' attribute to describe the image content if not described alredy in the text. "
        "place the image at logocal way in the text, that also dont break the text flow including its view in the UI. "
        "Please ensure that when multiple images are included in an answer, they are arranged in a logical and visually appealing way that maintains the flow of the text. Avoid overwhelming the user by placing too many images in the middle of the content or disrupting the reading experience, maybe put all of them in the end of the answer for example if it logiocal."
        "Always include links to item pages whenever possible, using the 'id' field from the context to form URLs in the format 'https://www.nli.org.il/en/articles/NNL_ALEPH990020376560205171' for example (like the url inside simply ('@id': 'https://www.nli.org.il/en/articles/NNL_ALEPH990020376560205171')). "
        "dont put the link seperate from the text like this: 'https://www.nli.org.il/en/articles/NNL_ALEPH990020376560205171', but do it that if the answer is the book 'around the world' the link will be activate when you prees on the name."
        "If the user ask spesificly for amount of the search results itselfs that send to you calculate them and answer him"
        "Return your answer in a valid JSON object with 'response_text' (the summary) and 'record_ids' (a list of recordId values for items mentioned in the response). "
        "the answer text must to be in HTML format and must to be in a right or in left derection according to the languhe request and answer (hebrew or english) but without the recordid that need to be like it is"
        "valid JSON example: {\"response_text\": \"Your answer here.\", \"record_ids\": [\"990032394200205171\", \"990032394210205171\"]}. and this is the only format\n"
        f"Context: {request.context}\n"
        f"items_images: {request.items_images}\n"
        f"Question: {request.prompt}"
    )
    model = genai.GenerativeModel("gemini-2.0-flash")
    chat = model.start_chat(history=[])
    ai_resp = await chat.send_message_async(
        system_msg
    )

    raw = ai_resp.text.strip()
    print("AI Response:", raw)
    # 2) Strip markdown fences
    if raw.startswith("```"):
        raw = raw.strip("`").strip()

    # 3) Find first JSON brace and cut there
    m = re.compile(r'[\{\[]').search(raw)
    if not m:
        # No JSON start token
        return {
            "response_text": "מצטערים, לא נמצאנו תשובה תקינה מהספרייה הלאומית.",
            "record_ids": []
        }

    json_payload = raw[m.start():]  # start from first { or [

    # 4) Parse JSON
    try:
        data = json.loads(json_payload)
    except json.JSONDecodeError:
        print("Failed to parse JSON payload:", json_payload)
        return {
            "response_text": "מצטערים, הייתה שגיאה בפענוח ה־JSON מהתגובה של ה‑AI.",
            "record_ids": []
        }

    # 5) Extract fields
    response_text = data.get("response_text", "")
    record_ids   = data.get("record_ids", [])

    return {
        "response_text": response_text,
        "record_ids": record_ids
    }
   
# This assumes the JSON structure is otherwise perfect.
def escape_response_text_quotes(json_string):
    # Find the response_text value
    match = re.search(r'"response_text":\s*"(.*?)"(,|\n|\s*$)', json_string, re.DOTALL)
    if match:
        original_content = match.group(1)
        # Escape only unescaped double quotes that are NOT part of \"
        # This regex is simplified and might need refinement for complex cases.
        # It targets double quotes that are not preceded by an odd number of backslashes
        escaped_content = re.sub(r'(?<!\\)(?<!\\\\)"', r'\"', original_content)
        # Reconstruct the string
        return json_string.replace(original_content, escaped_content, 1)
    return json_string

def delayed_shutdown():
    import time
    time.sleep(1)
    os._exit(0)

@app.post("/api/v1/shutdown")
async def shutdown(background_tasks: BackgroundTasks):
    try:
        threading.Thread(target=delayed_shutdown).start()
        return {"message": "Shutdown initiated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Shutdown failed: {str(e)}")
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
