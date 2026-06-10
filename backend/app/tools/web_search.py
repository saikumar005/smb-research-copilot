import logging
import httpx
from typing import List, Dict, Any
from duckduckgo_search import DDGS
from app.core.config import settings

logger = logging.getLogger(__name__)

def serper_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Queries Google via the Serper API.
    """
    if not settings.SERPER_API_KEY:
        raise ValueError("Serper API key is not configured")
        
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": settings.SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    payload = {
        "q": query,
        "num": max_results
    }
    
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        
        organic_results = data.get("organic", [])
        formatted_results = []
        for result in organic_results[:max_results]:
            formatted_results.append({
                "title": result.get("title", ""),
                "link": result.get("link", ""),
                "snippet": result.get("snippet", "")
            })
        return formatted_results
    except Exception as e:
        logger.error(f"Serper search failed: {e}")
        raise e

def ddg_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Queries DuckDuckGo search as a free, keyless fallback.
    """
    try:
        formatted_results = []
        with DDGS() as ddgs:
            ddg_results = ddgs.text(query, max_results=max_results)
            for result in ddg_results:
                formatted_results.append({
                    "title": result.get("title", ""),
                    "link": result.get("href", ""),  # DDG text search uses 'href'
                    "snippet": result.get("body", "") # DDG text search uses 'body'
                })
        return formatted_results
    except Exception as e:
        logger.error(f"DuckDuckGo search failed: {e}")
        return []

def search_web(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Orchestrated search utility that tries Serper Google search first, 
    and falls back to DuckDuckGo text search if Serper is unconfigured or fails.
    """
    if settings.SERPER_API_KEY:
        try:
            logger.info(f"Executing Serper Search for query: {query}")
            results = serper_search(query, max_results)
            if results:
                return results
        except Exception:
            logger.warning("Serper search failed. Falling back to DuckDuckGo.")
            
    # Fallback to DuckDuckGo search
    logger.info(f"Executing DuckDuckGo Fallback Search for query: {query}")
    return ddg_search(query, max_results)
