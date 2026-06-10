import logging
import asyncio
from typing import Dict, Any, List
from app.tools.web_search import search_web
from app.tools.page_fetch import fetch_page_content
from app.agents.state import AgentState
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

async def researcher_node(state: AgentState, config: RunnableConfig = None) -> dict:
    """
    Researcher Agent Node:
    1. Executes search tool query.
    2. Fetches and sanitizes top organic result pages.
    3. Bundles links, titles, snippets, and clean parsed body content into state.
    """
    query = state.get("research_query")
    event_queue = config.get("configurable", {}).get("event_queue") if config else None
    
    if not query:
        logger.warning("Researcher called but no query was formulated.")
        if event_queue:
            await event_queue.put({"type": "status", "agent": "researcher", "message": "No query formulated; skipping search."})
        return {"next_step": "supervisor", "research_findings": []}
        
    logger.info(f"Researcher Node: Searching for query: {query}")
    if event_queue:
        await event_queue.put({"type": "status", "agent": "researcher", "message": f"Querying search engine for: '{query}'..."})
    
    loop = asyncio.get_event_loop()
    
    # Run Serper / DuckDuckGo Search fallback in executor to prevent blocking
    search_results = await loop.run_in_executor(None, lambda: search_web(query, max_results=3))
    
    findings = []
    for idx, result in enumerate(search_results):
        title = result.get("title", "")
        link = result.get("link", "")
        snippet = result.get("snippet", "")
        
        logger.info(f"Researcher fetching page {idx+1}/{len(search_results)}: {link}")
        if event_queue:
            await event_queue.put({"type": "status", "agent": "researcher", "message": f"Fetching page {idx+1}/{len(search_results)}: {title}..."})
            
        # Scrape and extract text body in executor
        page_body = await loop.run_in_executor(None, lambda: fetch_page_content(link))
        
        findings.append({
            "title": title,
            "link": link,
            "snippet": snippet,
            "raw_content": page_body
        })
        
    logger.info(f"Researcher compiled {len(findings)} page findings.")
    if event_queue:
        await event_queue.put({"type": "status", "agent": "researcher", "message": f"Compiled {len(findings)} page research findings."})
        
    return {
        "research_findings": findings,
        "next_step": "supervisor"
    }

