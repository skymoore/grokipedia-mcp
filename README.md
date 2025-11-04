[![Add to Cursor](https://fastmcp.me/badges/cursor_dark.svg)](https://fastmcp.me/MCP/Details/1349/grokipedia)
[![Add to VS Code](https://fastmcp.me/badges/vscode_dark.svg)](https://fastmcp.me/MCP/Details/1349/grokipedia)
[![Add to Claude](https://fastmcp.me/badges/claude_dark.svg)](https://fastmcp.me/MCP/Details/1349/grokipedia)
[![Add to ChatGPT](https://fastmcp.me/badges/chatgpt_dark.svg)](https://fastmcp.me/MCP/Details/1349/grokipedia)
[![Add to Codex](https://fastmcp.me/badges/codex_dark.svg)](https://fastmcp.me/MCP/Details/1349/grokipedia)
[![Add to Gemini](https://fastmcp.me/badges/gemini_dark.svg)](https://fastmcp.me/MCP/Details/1349/grokipedia)

# Grokipedia MCP Server

[![smithery badge](https://smithery.ai/badge/@skymoore/grokipedia-mcp)](https://smithery.ai/server/@skymoore/grokipedia-mcp)

MCP server for searching and retrieving content from Grokipedia

The User of the MCP assumes full responsibility for interacting with [Grokipedia](https://grokipedia.com).

Please see the [Xai Terms of Service](https://x.ai/legal/terms-of-service) if you have any doubts.

Elon, please don't sue me.  I only wanted my agents to have access to truthful information and stop referencing wikipedia all the time.

## Quick Start

Add this to your MCP configuration file:

```json
{
  "mcpServers": {
    "grokipedia": {
      "command": "uvx",
      "args": ["grokipedia-mcp"]
    }
  }
}
```

### Verifying Installation

You should see the Grokipedia server available with these tools:

- `search` - Search with filters
- `get_page` - Get page overview
- `get_page_content` - Get full content
- `get_page_citations` - Get citations
- `get_related_pages` - Get linked pages
- `get_page_sections` - List all section headers
- `get_page_section` - Extract specific sections

And these prompts:

- `research_topic` - Research workflow
- `find_sources` - Find citations
- `explore_related` - Explore connections
- `compare_topics` - Compare two topics

## Features

- **Search with Filters**: Search with sorting (relevance/views) and filtering (min views)
- **Page Content**: Retrieve articles, citations, and metadata with smart truncation
- **Related Pages**: Discover linked/related articles
- **Section Extraction**: Get specific sections from long articles
- **Smart Suggestions**: Helpful alternatives when pages aren't found
- **Guided Prompts**: Pre-built workflows for research, sources, exploration

## Installation (Development)

Using `uv`:

```bash
cd grokipedia-mcp
uv sync
```

For development with MCP Inspector and CLI tools:

```bash
uv sync --dev
```

## Usage

### Run with MCP Inspector (Development)

The fastest way to test and debug (requires dev dependencies):

```bash
uv run --dev mcp dev main.py
```

This launches the MCP Inspector UI where you can:

- Explore available tools
- Test search queries
- Retrieve page content
- View structured output

### Run Directly

```bash
# Using the installed entry point
uv run grokipedia-mcp

# Or as a Python module
uv run python -m grokipedia_mcp

# Or directly
uv run python main.py
```

## Available Tools

### `search`

Search for articles in Grokipedia with filtering and sorting options.

**Parameters:**

- `query` (string, required) - Search query
- `limit` (int, optional, default: 12) - Maximum number of results
- `offset` (int, optional, default: 0) - Pagination offset
- `sort_by` (string, optional, default: "relevance") - Sort by "relevance" or "views"
- `min_views` (int, optional) - Filter to articles with at least this many views

**Returns:** List of search results with title, slug, snippet, relevance score, and view count.

**Examples:**

```json
// Basic search
{"query": "machine learning", "limit": 5}

// Sort by most viewed
{"query": "python", "sort_by": "views"}

// Filter popular articles only
{"query": "artificial intelligence", "min_views": 1000}
```

---

### `get_page`

Get complete page information including metadata, content preview, and citations summary. **Includes smart suggestion of alternatives if page not found.**

**Parameters:**

- `slug` (string, required) - Article identifier (from search results)
- `max_content_length` (int, optional, default: 5000) - Maximum content length

**Returns:** Complete page object with metadata, truncated content, and citation summaries.

**Features:**

- Suggests similar pages if the requested slug doesn't exist
- Provides overview with content preview and citations

**Use this when:** You need an overview of a page with metadata and a content preview.

**Example:**

```json
{"slug": "Machine_learning"}
```

---

### `get_page_content`

Get only the article content without citations or metadata.

**Parameters:**

- `slug` (string, required) - Article identifier
- `max_length` (int, optional, default: 10000) - Maximum content length

**Returns:** Only the article content (title and content text).

**Use this when:** You need to read the full article content without citations.

**Example:**

```json
{"slug": "Machine_learning", "max_length": 15000}
```

---

### `get_page_citations`

Get the citations list for a specific page.

**Parameters:**

- `slug` (string, required) - Article identifier
- `limit` (int, optional) - Maximum number of citations to return (returns all if not specified)

**Returns:** List of citations with titles, URLs, and descriptions. Includes total count and returned count.

**Use this when:** You need to access source references and citations.

**Examples:**

```json
// Get all citations
{"slug": "Machine_learning"}

// Get first 10 citations only
{"slug": "Machine_learning", "limit": 10}
```

---

### `get_related_pages`

Get pages that are linked from a specific article.

**Parameters:**

- `slug` (string, required) - Article identifier
- `limit` (int, optional, default: 10) - Maximum number of related pages to return

**Returns:** List of related/linked pages with titles and slugs.

**Use this when:** You want to discover related topics or explore connections between articles.

**Examples:**

```json
// Get related pages
{"slug": "Machine_learning"}

// Get more related pages
{"slug": "Quantum_computing", "limit": 20}
```

---

### `get_page_sections`

Get a list of all section headers in an article.

**Parameters:**

- `slug` (string, required) - Article identifier

**Returns:** List of all section headers with their levels (h1, h2, h3, etc.).

**Use this when:** You want to see the structure/outline of an article before reading specific sections.

**Example:**

```json
{"slug": "Machine_learning"}
```

---

### `get_page_section`

Extract a specific section from an article by header name.

**Parameters:**

- `slug` (string, required) - Article identifier
- `section_header` (string, required) - Section header to extract (case-insensitive)
- `max_length` (int, optional, default: 5000) - Maximum section content length

**Returns:** Content of the specified section only.

**Use this when:** You need just one section of a long article (e.g., "Applications", "History", "Examples").

**Examples:**

```json
// Get specific section
{"slug": "Neural_networks", "section_header": "Applications"}

// Get longer section
{"slug": "Python", "section_header": "Syntax", "max_length": 10000}
```

---

**Note:** Articles can be 100,000+ characters. Content is automatically truncated to prevent overwhelming LLM context windows. Use the `max_length` parameters to control the amount returned.

## Prompts

The server provides pre-built prompts for common workflows:

### `research_topic`

Guided workflow to research a topic: search → retrieve → analyze related pages and citations

### `find_sources`

Find authoritative sources and citations for academic/research purposes

### `explore_related`

Discover connections between topics and suggested further reading

### `compare_topics`

Compare two topics side-by-side with their content and citations

## Architecture

The server uses:

- **FastMCP** for declarative MCP server implementation
- **grokipedia-api-sdk** AsyncClient for API communication
- **Lifespan context** for client connection management
- **Structured output** using Pydantic models from the SDK
- **Comprehensive error handling** with specific exception types

## Error Handling

The server handles various error scenarios:

- `ValueError` for invalid parameters or not found pages
- `RuntimeError` for network or API errors
- Detailed logging at debug, info, warning, and error levels

## Development

### Project Structure

```
grokipedia-mcp/
├── grokipedia_mcp/
│   ├── __init__.py       # Package exports
│   ├── __main__.py       # CLI entry point
│   └── server.py         # FastMCP server implementation
├── main.py               # Direct execution entry point
├── pyproject.toml        # Project configuration
└── README.md             # This file
```

### Testing

Use the MCP Inspector for interactive testing:

```bash
uv run mcp dev main.py
```

## License

MIT