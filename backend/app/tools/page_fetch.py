import logging
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Standard user agent header to prevent simple request blockages
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}

def fetch_page_content(url: str, max_chars: int = 6000) -> str:
    """
    Fetches the content of a URL, cleans it of layout clutter, 
    and returns the main text body (up to max_chars characters).
    """
    try:
        logger.info(f"Scraping page URL: {url}")
        # Fetch page html content
        response = httpx.get(url, headers=HEADERS, timeout=8.0, follow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Strip script, style, header, footer, nav elements to extract core text content
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            element.decompose()
            
        # Get readable text content
        text = soup.get_text(separator=" ")
        
        # Clean up excessive spacing
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase for line in lines for phrase in line.split("  "))
        clean_text = "\n".join(chunk for chunk in chunks if chunk)
        
        # Truncate text content to avoid blowing up LLM prompt tokens
        if len(clean_text) > max_chars:
            return clean_text[:max_chars] + "... [TRUNCATED]"
            
        return clean_text
    except Exception as e:
        logger.error(f"Failed to fetch page content from {url}: {e}")
        return f"[Error: Could not retrieve page content from {url} due to connection error or blocking.]"
