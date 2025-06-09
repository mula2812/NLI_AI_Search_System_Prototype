import os
import re
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Path, Body, Response
from pydantic import BaseModel, Field
import httpx
import google.generativeai as genai

# Configuration
NLI_API_KEY = os.getenv("NLI_API_KEY", "OHOwpHbdR3Kt6p4S7qjBHddpUam0jHBMsvF5gXPz")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyD_7sQUckaUMIzGCAWoxpoUhEDOFzXHuec")

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

@app.get("/api/v1/search")
async def search_nli(
    q: str = Query(..., alias="q", description="Search query, e.g. 'creator,contains,דוד בן גוריון'"),
    output_format: str = Query("json", alias="format", description="Response format: json or xml"),
    count_only: bool = Query(False, description="Return only total_results count"),
    limit: int = Query(100, alias="limit", ge=1, le=500, description="Max records per page"),
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
            return {"total_results": total}
        return {"total_results": total, "items": items[offset:offset+limit]}

    total = data.get("total_results", 0)
    if count_only:
        return {"total_results": total}
    items = data.get("items", [])
    return {"total_results": total, "items": items[offset:offset+limit]}

@app.get("/api/v1/image/{identifier}")
async def get_image(
    identifier: str = Path(...), region: str = Query("full"), size: str = Query("max"),
    rotation: float = Query(0.0), quality: str = Query("default"), fmt: str = Query("jpg", alias="format")
):
    url = f"{BASE_IIIF_IMAGE}/{identifier}/{region}/{size}/{rotation}/{quality}.{fmt}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return Response(content=resp.content, media_type=f"image/{fmt}")

@app.get("/api/v1/manifest/{recordId}")
async def get_manifest(recordId: str = Path(...)):
    url = BASE_IIIF_MANIFEST.format(recordId=recordId)
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

@app.get("/api/v1/stream/{itemId}")
async def get_stream(itemId: str = Path(...), fmt: str = Query("all", alias="format")):
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
        "Your goal is to take a user's natural-language question and a set of JSON-formatted search results (context) "
        "and deliver a precise, well-structured answer in Hebrew, or in English if the user's question is in English. "
        "The context contains multiple search results under 'results'. "
        "Analyze each relevant result, extract pertinent items, and combine them into a cohesive response directly addressing the user's question. "
        "Format answers in complete sentences, using clear and user-friendly language in the appropriate language (Hebrew or English). "
        "If no matching data is available, explicitly state that no results were found. "
        "For images, do not include image URLs in the response text; images are displayed directly by the application UI using the 'thumbnailUrl' field from the context if available, or via manifest links otherwise. "
        "Always include links to item pages whenever possible, using the 'id' field from the context to form URLs in the format 'https://www.nli.org.il/en/articles/NNL_ALEPH990020376560205171' for example (like the url inside simply ('@id': 'https://www.nli.org.il/en/articles/NNL_ALEPH990020376560205171')). "
        f"Context JSON: {request.context}\n"
        f"Question: {request.prompt}"
    )
    model = genai.GenerativeModel("gemini-2.0-flash")
    ai_resp = model.generate_content(system_msg)
    clean_ai_resp = re.sub(r'[\"“”‘’\r\n]+', ' ', ai_resp.text)
    return {"response_text": clean_ai_resp}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)