import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from grokipedia_api_sdk import AsyncClient
from grokipedia_api_sdk.exceptions import (
    GrokipediaAPIError,
    GrokipediaBadRequestError,
    GrokipediaNetworkError,
    GrokipediaNotFoundError,
)

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import CallToolResult, TextContent


@dataclass
class AppContext:
    client: AsyncClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    async with AsyncClient() as client:
        yield AppContext(client=client)


mcp = FastMCP(
    "Grokipedia",
    lifespan=app_lifespan,
    instructions="MCP server for searching and retrieving content from Grokipedia, a wiki-style knowledge base.",
)


@mcp.tool()
async def search(
    query: str,
    limit: int = 12,
    offset: int = 0,
    sort_by: str = "relevance",
    min_views: int | None = None,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> CallToolResult:
    """Search for articles in Grokipedia with optional filtering and sorting.
    
    Args:
        query: Search query string
        limit: Maximum number of results (default: 12)
        offset: Pagination offset (default: 0)
        sort_by: Sort results by 'relevance' or 'views' (default: relevance)
        min_views: Minimum view count filter (optional)
    """
    if ctx is None:
        raise ValueError("Context is required")

    await ctx.debug(f"Searching for: '{query}' (limit={limit}, offset={offset}, sort_by={sort_by})")

    try:
        client = ctx.request_context.lifespan_context.client
        result = await client.search(query=query, limit=limit * 2, offset=offset)
        
        results = result.results
        
        if min_views is not None:
            results = [r for r in results if r.view_count >= min_views]
            await ctx.debug(f"Filtered to {len(results)} results with min_views >= {min_views}")
        
        if sort_by == "views":
            results = sorted(results, key=lambda x: x.view_count, reverse=True)
            await ctx.debug("Sorted results by view count")
        
        results = results[:limit]

        await ctx.info(f"Found {len(results)} results for query: '{query}'")
        
        text_lines = [f"Found {len(results)} results for '{query}'"]
        if sort_by == "views":
            text_lines[0] += " (sorted by views)"
        if min_views:
            text_lines[0] += f" (min views: {min_views})"
        text_lines.append("")
        
        for i, item in enumerate(results, 1):
            text_lines.append(f"{i}. {item.title}")
            text_lines.append(f"   Slug: {item.slug}")
            text_lines.append(f"   Snippet: {item.snippet}")
            text_lines.append(f"   Relevance: {item.relevance_score:.3f}")
            text_lines.append(f"   Views: {item.view_count}")
            text_lines.append("")
        
        return CallToolResult(
            content=[TextContent(type="text", text="\n".join(text_lines))],
            structuredContent={"results": [r.model_dump() for r in results]},
        )

    except GrokipediaBadRequestError as e:
        await ctx.error(f"Bad request: {e}")
        raise ValueError(f"Invalid search parameters: {e}") from e
    except GrokipediaNetworkError as e:
        await ctx.error(f"Network error: {e}")
        raise RuntimeError(f"Failed to connect to Grokipedia API: {e}") from e
    except GrokipediaAPIError as e:
        await ctx.error(f"API error: {e}")
        raise RuntimeError(f"Grokipedia API error: {e}") from e


@mcp.tool()
async def get_page(
    slug: str,
    max_content_length: int = 5000,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> CallToolResult:
    """Get complete page information including metadata, content preview, and citations summary."""
    if ctx is None:
        raise ValueError("Context is required")

    await ctx.debug(f"Fetching page: '{slug}'")

    try:
        client = ctx.request_context.lifespan_context.client
        result = await client.get_page(slug=slug, include_content=True)

        if not result.found or result.page is None:
            await ctx.warning(f"Page not found: '{slug}', searching for alternatives")
            search_result = await client.search(query=slug, limit=5)
            if search_result.results:
                suggestions = [f"{r.title} ({r.slug})" for r in search_result.results[:3]]
                await ctx.info(f"Found {len(search_result.results)} similar pages")
                raise ValueError(
                    f"Page not found: {slug}. Did you mean one of these? {', '.join(suggestions)}"
                )
            raise ValueError(f"Page not found: {slug}")

        await ctx.info(f"Retrieved page: '{result.page.title}' ({slug})")
        
        page = result.page
        content_len = len(page.content) if page.content else 0
        is_truncated = content_len > max_content_length
        
        text_parts = [
            f"# {page.title}",
            "",
            f"**Slug:** {page.slug}",
        ]
        
        if page.description:
            text_parts.extend(["", f"**Description:** {page.description}", ""])
        
        if page.content:
            preview_length = min(1000, max_content_length)
            text_parts.extend(["", "## Content Preview", "", page.content[:preview_length]])
            if content_len > preview_length:
                text_parts.append(f"\n... (showing first {preview_length} of {content_len} chars)")
        
        if page.citations:
            text_parts.extend(["", f"## Citations ({len(page.citations)} total)", ""])
            for i, citation in enumerate(page.citations[:5], 1):
                text_parts.append(f"{i}. {citation.title}: {citation.url}")
            if len(page.citations) > 5:
                text_parts.append(f"... and {len(page.citations) - 5} more")
        
        page_dict = page.model_dump()
        if is_truncated:
            page_dict["content"] = page.content[:max_content_length]
            page_dict["_content_truncated"] = True
            page_dict["_original_length"] = content_len
            await ctx.warning(
                f"Content truncated from {content_len} to {max_content_length} chars. "
                f"Use get_page_content tool for full content access."
            )
        
        return CallToolResult(
            content=[TextContent(type="text", text="\n".join(text_parts))],
            structuredContent=page_dict,
        )

    except GrokipediaNotFoundError as e:
        await ctx.error(f"Page not found: {e}")
        raise ValueError(f"Page not found: {slug}") from e
    except GrokipediaBadRequestError as e:
        await ctx.error(f"Bad request: {e}")
        raise ValueError(f"Invalid page slug: {e}") from e
    except GrokipediaNetworkError as e:
        await ctx.error(f"Network error: {e}")
        raise RuntimeError(f"Failed to connect to Grokipedia API: {e}") from e
    except GrokipediaAPIError as e:
        await ctx.error(f"API error: {e}")
        raise RuntimeError(f"Grokipedia API error: {e}") from e


@mcp.tool()
async def get_page_content(
    slug: str,
    max_length: int = 10000,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> CallToolResult:
    """Get only the article content without citations or metadata."""
    if ctx is None:
        raise ValueError("Context is required")

    await ctx.debug(f"Fetching content for: '{slug}'")

    try:
        client = ctx.request_context.lifespan_context.client
        result = await client.get_page(slug=slug, include_content=True)

        if not result.found or result.page is None:
            await ctx.warning(f"Page not found: '{slug}'")
            raise ValueError(f"Page not found: {slug}")

        page = result.page
        content = page.content or ""
        content_len = len(content)
        is_truncated = content_len > max_length
        
        if is_truncated:
            content = content[:max_length]
            await ctx.warning(
                f"Content truncated from {content_len} to {max_length} chars. "
                f"Use max_length parameter to adjust."
            )
        
        await ctx.info(f"Retrieved content for: '{page.title}' ({content_len} chars)")
        
        text_output = f"# {page.title}\n\n{content}"
        if is_truncated:
            text_output += f"\n\n... (truncated at {max_length} of {content_len} chars)"
        
        structured = {
            "slug": page.slug,
            "title": page.title,
            "content": content,
            "content_length": len(content),
        }
        
        if is_truncated:
            structured["_truncated"] = True
            structured["_original_length"] = content_len
        
        return CallToolResult(
            content=[TextContent(type="text", text=text_output)],
            structuredContent=structured,
        )

    except GrokipediaNotFoundError as e:
        await ctx.error(f"Page not found: {e}")
        raise ValueError(f"Page not found: {slug}") from e
    except GrokipediaBadRequestError as e:
        await ctx.error(f"Bad request: {e}")
        raise ValueError(f"Invalid page slug: {e}") from e
    except GrokipediaNetworkError as e:
        await ctx.error(f"Network error: {e}")
        raise RuntimeError(f"Failed to connect to Grokipedia API: {e}") from e
    except GrokipediaAPIError as e:
        await ctx.error(f"API error: {e}")
        raise RuntimeError(f"Grokipedia API error: {e}") from e


@mcp.tool()
async def get_page_citations(
    slug: str,
    limit: int | None = None,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> CallToolResult:
    """Get the citations list for a specific page."""
    if ctx is None:
        raise ValueError("Context is required")

    await ctx.debug(f"Fetching citations for: '{slug}' (limit={limit})")

    try:
        client = ctx.request_context.lifespan_context.client
        result = await client.get_page(slug=slug, include_content=False)

        if not result.found or result.page is None:
            await ctx.warning(f"Page not found: '{slug}'")
            raise ValueError(f"Page not found: {slug}")

        page = result.page
        all_citations = page.citations or []
        total_count = len(all_citations)
        
        citations = all_citations[:limit] if limit else all_citations
        is_limited = limit and total_count > limit
        
        await ctx.info(
            f"Retrieved {len(citations)} of {total_count} citations for: '{page.title}'"
        )
        
        if not all_citations:
            text_output = f"# {page.title}\n\nNo citations found."
            structured = {
                "slug": page.slug,
                "title": page.title,
                "citations": [],
                "total_count": 0,
                "returned_count": 0,
            }
        else:
            header = f"# {page.title}\n\n"
            if is_limited:
                header += f"Showing {len(citations)} of {total_count} citations:\n"
            else:
                header += f"Found {total_count} citations:\n"
            
            text_parts = [header]
            for i, citation in enumerate(citations, 1):
                text_parts.append(f"{i}. **{citation.title}**")
                text_parts.append(f"   URL: {citation.url}")
                if citation.description:
                    text_parts.append(f"   Description: {citation.description}")
                text_parts.append("")
            
            if is_limited:
                text_parts.append(f"... and {total_count - len(citations)} more citations")
            
            text_output = "\n".join(text_parts)
            structured = {
                "slug": page.slug,
                "title": page.title,
                "citations": [c.model_dump() for c in citations],
                "total_count": total_count,
                "returned_count": len(citations),
            }
            
            if is_limited:
                structured["_limited"] = True
        
        return CallToolResult(
            content=[TextContent(type="text", text=text_output)],
            structuredContent=structured,
        )

    except GrokipediaNotFoundError as e:
        await ctx.error(f"Page not found: {e}")
        raise ValueError(f"Page not found: {slug}") from e
    except GrokipediaBadRequestError as e:
        await ctx.error(f"Bad request: {e}")
        raise ValueError(f"Invalid page slug: {e}") from e
    except GrokipediaNetworkError as e:
        await ctx.error(f"Network error: {e}")
        raise RuntimeError(f"Failed to connect to Grokipedia API: {e}") from e
    except GrokipediaAPIError as e:
        await ctx.error(f"API error: {e}")
        raise RuntimeError(f"Grokipedia API error: {e}") from e


@mcp.tool()
async def get_related_pages(
    slug: str,
    limit: int = 10,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> CallToolResult:
    """Get pages that are linked from the specified page."""
    if ctx is None:
        raise ValueError("Context is required")

    await ctx.debug(f"Fetching related pages for: '{slug}' (limit={limit})")

    try:
        client = ctx.request_context.lifespan_context.client
        result = await client.get_page(slug=slug, include_content=False)

        if not result.found or result.page is None:
            await ctx.warning(f"Page not found: '{slug}'")
            raise ValueError(f"Page not found: {slug}")

        page = result.page
        linked_pages = page.linked_pages or []
        total_count = len(linked_pages)
        
        related = linked_pages[:limit] if limit else linked_pages
        is_limited = limit and total_count > limit
        
        await ctx.info(f"Found {len(related)} of {total_count} related pages for: '{page.title}'")
        
        if not linked_pages:
            text_output = f"# {page.title}\n\nNo related pages found."
            structured = {
                "slug": page.slug,
                "title": page.title,
                "related_pages": [],
                "total_count": 0,
                "returned_count": 0,
            }
        else:
            header = f"# {page.title}\n\n"
            if is_limited:
                header += f"Showing {len(related)} of {total_count} related pages:\n\n"
            else:
                header += f"Found {total_count} related pages:\n\n"
            
            text_parts = [header]
            for i, rel_page in enumerate(related, 1):
                if isinstance(rel_page, dict):
                    title = rel_page.get("title", "Unknown")
                    slug_val = rel_page.get("slug", "")
                else:
                    title = str(rel_page)
                    slug_val = ""
                text_parts.append(f"{i}. {title}")
                if slug_val:
                    text_parts.append(f"   Slug: {slug_val}")
                text_parts.append("")
            
            if is_limited:
                text_parts.append(f"... and {total_count - len(related)} more")
            
            text_output = "\n".join(text_parts)
            structured = {
                "slug": page.slug,
                "title": page.title,
                "related_pages": related,
                "total_count": total_count,
                "returned_count": len(related),
            }
            
            if is_limited:
                structured["_limited"] = True
        
        return CallToolResult(
            content=[TextContent(type="text", text=text_output)],
            structuredContent=structured,
        )

    except GrokipediaNotFoundError as e:
        await ctx.error(f"Page not found: {e}")
        raise ValueError(f"Page not found: {slug}") from e
    except GrokipediaBadRequestError as e:
        await ctx.error(f"Bad request: {e}")
        raise ValueError(f"Invalid page slug: {e}") from e
    except GrokipediaNetworkError as e:
        await ctx.error(f"Network error: {e}")
        raise RuntimeError(f"Failed to connect to Grokipedia API: {e}") from e
    except GrokipediaAPIError as e:
        await ctx.error(f"API error: {e}")
        raise RuntimeError(f"Grokipedia API error: {e}") from e


@mcp.tool()
async def get_page_section(
    slug: str,
    section_header: str,
    max_length: int = 5000,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> CallToolResult:
    """Extract a specific section from an article by header name."""
    if ctx is None:
        raise ValueError("Context is required")

    await ctx.debug(f"Fetching section '{section_header}' from: '{slug}'")

    try:
        client = ctx.request_context.lifespan_context.client
        result = await client.get_page(slug=slug, include_content=True)

        if not result.found or result.page is None:
            await ctx.warning(f"Page not found: '{slug}'")
            raise ValueError(f"Page not found: {slug}")

        page = result.page
        content = page.content or ""
        
        header_pattern = rf'^#+\s*{re.escape(section_header)}\s*$'
        lines = content.split('\n')
        
        section_start = None
        section_end = None
        section_level = None
        
        for i, line in enumerate(lines):
            if section_start is None:
                if re.match(header_pattern, line, re.IGNORECASE):
                    section_start = i
                    section_level = len(line) - len(line.lstrip('#'))
            elif section_start is not None:
                if line.startswith('#'):
                    current_level = len(line) - len(line.lstrip('#'))
                    if current_level <= section_level:
                        section_end = i
                        break
        
        if section_start is None:
            await ctx.warning(f"Section '{section_header}' not found in '{slug}'")
            raise ValueError(f"Section '{section_header}' not found")
        
        if section_end is None:
            section_end = len(lines)
        
        section_content = '\n'.join(lines[section_start:section_end]).strip()
        section_len = len(section_content)
        is_truncated = section_len > max_length
        
        if is_truncated:
            section_content = section_content[:max_length]
            await ctx.warning(
                f"Section content truncated from {section_len} to {max_length} chars"
            )
        
        await ctx.info(f"Extracted section '{section_header}' from '{page.title}'")
        
        text_output = f"# {page.title}\n## {section_header}\n\n{section_content}"
        if is_truncated:
            text_output += f"\n\n... (truncated at {max_length} of {section_len} chars)"
        
        structured = {
            "slug": page.slug,
            "title": page.title,
            "section_header": section_header,
            "section_content": section_content,
            "content_length": len(section_content),
        }

        if is_truncated:
            structured["_truncated"] = True
            structured["_original_length"] = section_len

        return CallToolResult(
            content=[TextContent(type="text", text=text_output)],
            structuredContent=structured,
        )

    except GrokipediaNotFoundError as e:
        await ctx.error(f"Page not found: {e}")
        raise ValueError(f"Page not found: {slug}") from e
    except GrokipediaBadRequestError as e:
        await ctx.error(f"Bad request: {e}")
        raise ValueError(f"Invalid page slug: {e}") from e
    except GrokipediaNetworkError as e:
        await ctx.error(f"Network error: {e}")
        raise RuntimeError(f"Failed to connect to Grokipedia API: {e}") from e
    except GrokipediaAPIError as e:
        await ctx.error(f"API error: {e}")
        raise RuntimeError(f"Grokipedia API error: {e}") from e


# Prompts
@mcp.prompt()
def research_topic():
    """Research a topic by searching and retrieving detailed information"""
    return """I'll help you research a topic from Grokipedia. Please provide the topic you want to research.

I will:
1. Search for articles related to your topic
2. Retrieve the most relevant article
3. Provide a comprehensive overview including related pages and citations

What topic would you like to research?"""


@mcp.prompt()
def find_sources():
    """Find authoritative sources and citations for a topic"""
    return """I'll help you find sources and citations for a topic from Grokipedia.

I will:
1. Search for articles on your topic
2. Retrieve citation information
3. List all source materials with URLs

What topic do you need sources for?"""


@mcp.prompt()
def explore_related():
    """Explore topics related to a specific article"""
    return """I'll help you explore related topics and discover connections in Grokipedia.

I will:
1. Get the page you're interested in
2. Find all related/linked pages
3. Show you connections and suggest further reading

Which topic would you like to explore?"""


@mcp.prompt()
def compare_topics(topic1: str = "Topic 1", topic2: str = "Topic 2"):
    """Compare two topics side by side"""
    return f"""I'll help you compare two topics from Grokipedia.

I will:
1. Retrieve articles for both {topic1} and {topic2}
2. Compare their content, key points, and citations
3. Highlight similarities and differences

Please provide the two topics you want to compare (or confirm the suggestions above)."""


@mcp.tool()
async def get_page_sections(
    slug: str,
    ctx: Context[ServerSession, AppContext] | None = None,
) -> CallToolResult:
    """Get a list of all section headers in an article."""
    if ctx is None:
        raise ValueError("Context is required")

    await ctx.debug(f"Fetching section headers for: '{slug}'")

    try:
        client = ctx.request_context.lifespan_context.client
        result = await client.get_page(slug=slug, include_content=True)

        if not result.found or result.page is None:
            await ctx.warning(f"Page not found: '{slug}', searching for alternatives")
            search_result = await client.search(query=slug, limit=5)
            if search_result.results:
                suggestions = [f"{r.title} ({r.slug})" for r in search_result.results[:3]]
                await ctx.info(f"Found {len(search_result.results)} similar pages")
                raise ValueError(
                    f"Page not found: {slug}. Did you mean one of these? {', '.join(suggestions)}"
                )
            raise ValueError(f"Page not found: {slug}")

        page = result.page
        content = page.content or ""
        
        # Extract all markdown headers
        lines = content.split('\n')
        sections = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                # Count the number of # symbols for header level
                level = len(line) - len(line.lstrip('#'))
                header_text = stripped.lstrip('#').strip()
                if header_text:  # Only include non-empty headers
                    sections.append({
                        "level": level,
                        "header": header_text
                    })
        
        await ctx.info(f"Found {len(sections)} section headers in '{page.title}'")
        
        if not sections:
            text_output = f"# {page.title}\n\nNo section headers found."
            structured = {
                "slug": page.slug,
                "title": page.title,
                "sections": [],
                "count": 0,
            }
        else:
            text_parts = [f"# {page.title}", "", f"Found {len(sections)} sections:", ""]
            for i, section in enumerate(sections, 1):
                indent = "  " * (section["level"] - 1)
                text_parts.append(f"{i}. {indent}{section['header']} (Level {section['level']})")
            
            text_output = "\n".join(text_parts)
            structured = {
                "slug": page.slug,
                "title": page.title,
                "sections": sections,
                "count": len(sections),
            }
        
        return CallToolResult(
            content=[TextContent(type="text", text=text_output)],
            structuredContent=structured,
        )

    except GrokipediaNotFoundError as e:
        await ctx.error(f"Page not found: {e}")
        raise ValueError(f"Page not found: {slug}") from e
    except GrokipediaBadRequestError as e:
        await ctx.error(f"Bad request: {e}")
        raise ValueError(f"Invalid page slug: {e}") from e
    except GrokipediaNetworkError as e:
        await ctx.error(f"Network error: {e}")
        raise RuntimeError(f"Failed to connect to Grokipedia API: {e}") from e
    except GrokipediaAPIError as e:
        await ctx.error(f"API error: {e}")
        raise RuntimeError(f"Grokipedia API error: {e}") from e
