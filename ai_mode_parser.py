from bs4 import BeautifulSoup, NavigableString
import re
from urllib.parse import urlparse, parse_qs
import json

def unwrap_google_url(href: str) -> str:
    """Unwrap Google redirect URLs to get the actual destination"""
    if not href:
        return ""
    
    if href.startswith('/url?'):
        try:
            params = parse_qs(href[5:])  # Remove '/url?'
            return params.get('q', [href])[0]
        except:
            return href
    elif href.startswith('https://www.google.com/url?'):
        try:
            params = parse_qs(href.split('?', 1)[1])
            return params.get('q', [href])[0]
        except:
            return href
    
    return href

def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    try:
        parsed = urlparse(url)
        return parsed.netloc.replace('www.', '')
    except:
        return ""

def clean_text(text: str) -> str:
    """Clean and normalize text content"""
    if not text:
        return ""
    
    # Remove extra whitespace and normalize
    text = re.sub(r'\s+', ' ', text.strip())
    return text

def is_ui_noise(text: str) -> bool:
    """Check if text looks like UI noise rather than content"""
    
    if not text or len(text) < 10:
        return True
    
    # For very large text blocks (> 1000 chars), don't filter based on starting patterns
    # as they likely contain substantial content mixed with UI elements
    if len(text) > 1000:
        return False
    
    # Common UI noise patterns (only for shorter text)
    noise_patterns = [
        r'^(Images|Videos|News|Shopping|Maps|Books|Tools|Settings|Sign in)(\s|$)',
        r'^\s*(Privacy|Terms|Advertising|About|Google)(\s|$)',
        r'^(All|Any time|Past hour|Past day|Past week)(\s|$)',
        r'^(Sort by|Clear)(\s|$)',
        r'^\s*(delete|click here|redirect|access|learn more)(\s|$)',
        r'^\s*(cookie|privacy policy|terms of service)',
        r'^\s*(search history|turn on|turn off)',
        r'^\s*(related searches|people also)',
        r'^\s*(Google apps|Google Account)',
    ]
    
    # Only apply UI noise filters to shorter text snippets
    for pattern in noise_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    
    return False

def extract_structured_from_html(html: str) -> dict:
    """Extract structured content from Google AI search results HTML"""
    
    # Parse HTML
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script and style tags
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    
    # Get clean text for processing
    clean_text_content = soup.get_text()
    
    # Extract inline images (filter out obvious UI images but be less restrictive)
    inline_images = []
    for img in soup.find_all('img'):
        src = img.get('src', '')
        alt = img.get('alt', '')
        
        # Skip obvious non-content images
        if (not src or
            src.startswith('data:image/svg') or  # Skip small SVG icons
            'favicon' in src.lower() or
            '/favicon' in src or
            src.endswith('.svg') and len(src) < 100):  # Skip small SVG files
            continue
        
        # Skip if alt text suggests it's a UI element
        if alt and (
            'icon' in alt.lower() or
            'logo' in alt.lower() and len(alt) < 20 or  # Allow longer logo descriptions
            alt.lower() in ['image', 'photo', 'picture'] or
            len(alt) < 3):
            continue
        
        # Include images that have meaningful alt text or are from content sources
        if (alt and len(alt) > 3) or ('gstatic' not in src.lower() and 'google' not in src.lower()):
            inline_images.append({
                "title": alt or "Image",  # Map alt to title for ScrapingDog compatibility
                "url": src,              # Map src to url for ScrapingDog compatibility
                "width": None,           # Optional field
                "height": None           # Optional field
            })
    
    # Parse text blocks from clean text
    text_blocks = parse_text_blocks(clean_text_content)
    
    # Extract references from HTML structure
    references = extract_references_from_html(soup)
    
    return {
        "inline_images": inline_images[:5],  # Limit images
        "text_blocks": text_blocks,
        "references": references
    }

def parse_text_blocks(text: str) -> list:
    """Parse text into structured blocks (paragraphs and lists)"""
    
    if not text.strip():
        return []
    
    blocks = []
    
    # First, try to identify the main content area
    # Look for substantial paragraphs that aren't UI noise
    paragraphs = []
    
    # Split by double newlines to get paragraph candidates
    sections = re.split(r'\n\s*\n+', text)
    
    for section in sections:
        section = section.strip()
        
        # Skip if looks like UI noise
        if is_ui_noise(section):
            continue
            
        # Skip very short sections
        if len(section) < 30:
            continue
            
        # Skip sections that are mostly punctuation or navigation
        if len(re.sub(r'[^\w\s]', '', section)) < len(section) * 0.5:
            continue
        
        paragraphs.append(section)
    
    # Process the substantial paragraphs
    for paragraph in paragraphs:
        # Check if this looks like a list
        if detect_list_pattern(paragraph):
            list_items = parse_list_items(paragraph)
            if list_items:
                blocks.append({
                    "type": "list", 
                    "items": list_items
                })
        else:
            # Split long paragraphs into sentences
            sentences = split_into_sentences(paragraph)
            for sentence in sentences:
                if sentence and len(sentence) > 20:  # Filter short fragments
                    blocks.append({
                        "type": "paragraph",
                        "snippet": sentence
                    })
    
    # Deduplicate similar blocks
    blocks = deduplicate_blocks(blocks)
    
    # Hard-coded removal: Delete first 3 paragraphs (usually Google UI noise)
    paragraphs_removed = 0
    filtered_blocks = []
    
    for block in blocks:
        if block["type"] == "paragraph" and paragraphs_removed < 3:
            paragraphs_removed += 1
            continue  # Skip this paragraph
        filtered_blocks.append(block)
    
    return filtered_blocks

def split_into_sentences(text: str) -> list:
    """Split text into logical sentences"""
    
    # Split by sentence endings, but be careful with abbreviations
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
    
    cleaned = []
    for sentence in sentences:
        sentence = sentence.strip()
        # Only include substantial sentences
        if len(sentence) > 20 and not is_ui_noise(sentence):
            cleaned.append(sentence)
    
    return cleaned

def detect_list_pattern(text: str) -> bool:
    """Detect if text contains list-like patterns"""
    
    # Look for common list indicators
    list_patterns = [
        r'^\s*[\•\-\*]\s+',  # Bullet points at start
        r'^\s*\d+\.\s+',     # Numbered lists at start  
        r'\n\s*[\•\-\*]\s+', # Bullet points in text
        r'\n\s*\d+\.\s+',    # Numbered items in text
        r':\s*\n\s*[A-Z]',   # Colon followed by newline and capital letter
    ]
    
    for pattern in list_patterns:
        if re.search(pattern, text, re.MULTILINE):
            return True
    
    # Also check if text has multiple lines with colon-separated items
    lines = text.split('\n')
    colon_count = sum(1 for line in lines if ':' in line and len(line) > 10)
    
    return colon_count >= 2

def parse_list_items(text: str) -> list:
    """Parse text into list items"""
    
    items = []
    
    # Try multiple splitting strategies
    potential_items = []
    
    # Strategy 1: Split by bullet points and numbers
    parts = re.split(r'\n\s*(?:[\•\-\*]|\d+\.)\s+', text)
    potential_items.extend(parts)
    
    # Strategy 2: Split by colons (for definition-style lists)  
    if ':' in text:
        lines = text.split('\n')
        for line in lines:
            if ':' in line and len(line) > 15:
                potential_items.append(line.strip())
    
    # Clean and filter items
    for item in potential_items:
        item = item.strip()
        
        # Skip very short items or UI noise
        if len(item) < 10 or is_ui_noise(item):
            continue
            
        # Clean up formatting
        item = re.sub(r'\s+', ' ', item)
        
        if item not in items:  # Avoid duplicates
            items.append(item)
    
    return items[:10]  # Limit list items

def deduplicate_blocks(blocks: list) -> list:
    """Remove duplicate or very similar blocks"""
    
    if not blocks:
        return []
    
    unique_blocks = []
    seen_snippets = set()
    
    for block in blocks:
        if block["type"] == "paragraph":
            snippet = block["snippet"]
            # Check for substantial overlap with existing snippets
            is_duplicate = False
            for seen in seen_snippets:
                if (len(snippet) > 20 and len(seen) > 20 and
                    (snippet in seen or seen in snippet or
                     len(set(snippet.split()) & set(seen.split())) > min(len(snippet.split()), len(seen.split())) * 0.7)):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_blocks.append(block)
                seen_snippets.add(snippet)
        else:
            # For lists, add without deduplication for now
            unique_blocks.append(block)
    
    return unique_blocks[:20]  # Limit total blocks

def extract_references_from_html(soup: BeautifulSoup) -> list:
    """Extract reference links from HTML structure"""
    
    references = []
    seen_urls = set()
    
    # Find all links that look like references - use multiple strategies
    candidate_links = []
    
    # Strategy 1: Find links with Google redirect patterns
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if href.startswith('/url?') or 'google.com/url?' in href:
            candidate_links.append(link)
    
    # Strategy 2: Find links with ping attribute (often used for external links)
    for link in soup.find_all('a', ping=True):
        candidate_links.append(link)
    
    # Strategy 3: Find regular external links
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if href.startswith('http') and 'google.com' not in href and 'gstatic.com' not in href:
            candidate_links.append(link)
    
    # Remove duplicates while preserving order
    unique_links = []
    seen_elements = set()
    for link in candidate_links:
        if id(link) not in seen_elements:
            unique_links.append(link)
            seen_elements.add(id(link))
    
    for link in unique_links:
        href = link.get('href', '')
        text = clean_text(link.get_text())
        
        # For links with empty direct text, try to find meaningful text in nearby elements
        if not text or len(text) < 3:
            # Look for text in parent element
            if link.parent:
                parent_text = clean_text(link.parent.get_text())
                if parent_text and len(parent_text) > 10:
                    text = parent_text[:100]  # Use first part as title
            
            # Look for text in siblings
            if not text or len(text) < 5:
                for sibling in link.next_siblings:
                    if hasattr(sibling, 'get_text'):
                        sibling_text = clean_text(sibling.get_text())
                        if len(sibling_text) > 10:
                            text = sibling_text[:100]
                            break
                    elif isinstance(sibling, str):
                        sibling_text = clean_text(sibling)
                        if len(sibling_text) > 10:
                            text = sibling_text[:100]
                            break
        
        # Skip if we still can't find meaningful text
        if not text or len(text) < 3:
            continue
        
        # Unwrap Google redirect URLs
        actual_url = unwrap_google_url(href)
        
        # Skip internal Google links and invalid URLs
        if (not actual_url or 
            actual_url.startswith('#') or 
            actual_url == href and href.startswith('/') or  # relative internal links
            'google.com' in actual_url or
            'gstatic.com' in actual_url):
            continue
        
        # Avoid duplicate URLs
        if actual_url in seen_urls:
            continue
        
        seen_urls.add(actual_url)
        
        # Extract domain for reference
        domain = extract_domain(actual_url)
        if not domain:
            continue
        
        # Enhanced snippet extraction - look for context in nearby elements
        snippet = extract_link_snippet(link, text)
        
        references.append({
            "title": text[:100],  # Limit title length
            "link": actual_url,
            "snippet": snippet[:250] if snippet else "",
            "source": domain,
            "thumbnail": "",  # Could be enhanced to find nearby images
            "favicon": "",    # Could be enhanced with domain + '/favicon.ico'
            "index": len(references) + 1
        })
        
        # Stop if we have enough good references
        if len(references) >= 10:
            break
    
    return references


def extract_link_snippet(link, link_text: str) -> str:
    """Extract a contextual snippet for a reference link"""
    snippet = ""
    
    # Strategy 1: Look for snippet in parent element
    parent = link.parent
    if parent:
        parent_text = clean_text(parent.get_text())
        if parent_text and len(parent_text) > len(link_text) + 30:
            # Remove the link text to get surrounding context
            snippet = parent_text.replace(link_text, '').strip()
            snippet = re.sub(r'^[\s\-\|•]+', '', snippet)
            snippet = re.sub(r'[\s\-\|•]+$', '', snippet)
    
    # Strategy 2: Look for snippet in grandparent if parent snippet is too short
    if not snippet or len(snippet) < 30:
        grandparent = parent.parent if parent else None
        if grandparent:
            gp_text = clean_text(grandparent.get_text())
            if gp_text and len(gp_text) > len(link_text) + 50:
                snippet = gp_text.replace(link_text, '').strip()
                snippet = re.sub(r'^[\s\-\|•]+', '', snippet)
                snippet = re.sub(r'[\s\-\|•]+$', '', snippet)
    
    # Strategy 3: Look for nearby text nodes
    if not snippet or len(snippet) < 20:
        # Look for next sibling with substantial text
        next_sibling = link.next_sibling
        while next_sibling and len(snippet) < 50:
            if hasattr(next_sibling, 'get_text'):
                sibling_text = clean_text(next_sibling.get_text())
                if len(sibling_text) > 20:
                    snippet = sibling_text[:100]
                    break
            elif isinstance(next_sibling, str):
                sibling_text = clean_text(next_sibling)
                if len(sibling_text) > 20:
                    snippet = sibling_text[:100]
                    break
            next_sibling = next_sibling.next_sibling
    
    # Clean up the final snippet
    if snippet:
        # Remove common prefixes/suffixes
        snippet = re.sub(r'^(Learn more|Read more|Click here|Visit|Go to)\s*', '', snippet, flags=re.IGNORECASE)
        snippet = re.sub(r'\s*(Learn more|Read more|Click here)$', '', snippet, flags=re.IGNORECASE)
        
        # Don't use snippet if it looks like UI noise
        if is_ui_noise(snippet):
            snippet = ""
    
    return snippet
