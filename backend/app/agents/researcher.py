import logging
from typing import Dict, Any, List
from app.tools.web_search import search_web
from app.tools.page_fetch import fetch_page_content
from app.agents.state import AgentState

logger = logging.getLogger(__name__)

def researcher_node(state: AgentState) -> dict:
    """
    Researcher Agent Node:
    1. Executes search tool query.
    2. Fetches and sanitizes top organic result pages.
    3. Bundles links, titles, snippets, and clean parsed body content into state.
    """
    query = state.get("research_query")
    if not query:
        logger.warning("Researcher called but no query was formulated.")
        return {"next_step": "supervisor", "research_findings": []}
        
    logger.info(f"Researcher Node: Searching for query: {query}")
    
    # Run Serper / DuckDuckGo Search fallback
    search_results = search_web(query, max_results=3)
    
    findings = []
    for idx, result in enumerate(search_results):
        title = result.get("title", "")
        link = result.get("link", "")
        snippet = result.get("snippet", "")
        
        logger.info(f"Researcher fetching page {idx+1}/{len(search_results)}: {link}")
        # Scrape and extract text body from the link
        page_body = fetch_page_content(link)
        
        findings.append({
            "title": title,
            "link": link,
            "snippet": snippet,
            "raw_content": page_body
        })
        
    logger.info(f"Researcher compiled {len(findings)} page findings.")
    return {
        "research_findings": findings,
        "next_step": "supervisor"
    }
