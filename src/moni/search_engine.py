"""
Moni Search System - Multilingual Search Engine
Advanced search functionality with YouTube, Academic Papers, and Web content support.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urlencode, quote
import asyncio
import aiohttp
import requests

from .internationalization import get_translator, TranslationKey, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)


class SearchType(Enum):
    """Types of search sources."""
    YOUTUBE = "youtube"
    ACADEMIC = "academic"
    WEB = "web"
    NEWS = "news"
    IMAGES = "images"


class SearchEngine(Enum):
    """Available search engines for each type."""
    # YouTube
    YOUTUBE_API = "youtube_api"
    YOUTUBE_SCRAPER = "youtube_scraper"

    # Academic
    GOOGLE_SCHOLAR = "google_scholar"
    ARXIV = "arxiv"
    PUBMED = "pubmed"
    SEMANTIC_SCHOLAR = "semantic_scholar"

    # Web
    GOOGLE = "google"
    BING = "bing"
    DUCKDUCKGO = "duckduckgo"
    BRAVE = "brave"

    # News
    GOOGLE_NEWS = "google_news"
    BING_NEWS = "bing_news"

    # Images
    GOOGLE_IMAGES = "google_images"
    BING_IMAGES = "bing_images"


@dataclass
class SearchQuery:
    """Search query parameters."""
    query: str
    search_type: SearchType
    engine: SearchEngine
    language: str = "en"
    region: str = "US"
    max_results: int = 10
    filters: Dict[str, Any] = field(default_factory=dict)
    safe_search: bool = True


@dataclass
class SearchResult:
    """Individual search result."""
    title: str
    description: str
    url: str
    source: SearchEngine
    search_type: SearchType
    published_date: Optional[datetime] = None
    author: Optional[str] = None
    thumbnail_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    relevance_score: float = 0.0


@dataclass
class SearchResponse:
    """Complete search response."""
    query: SearchQuery
    results: List[SearchResult]
    total_results: int
    search_time: float
    suggestions: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)


class BaseSearchProvider(ABC):
    """Abstract base class for search providers."""

    def __init__(self, api_key: Optional[str] = None, timeout: int = 10):
        self.api_key = api_key
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        if not self.session:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None

    @abstractmethod
    async def search(self, query: SearchQuery) -> SearchResponse:
        """Perform search and return results."""
        pass

    @abstractmethod
    def get_supported_languages(self) -> List[str]:
        """Return list of supported languages."""
        pass

    @abstractmethod
    def get_supported_regions(self) -> List[str]:
        """Return list of supported regions."""
        pass


class YouTubeSearchProvider(BaseSearchProvider):
    """YouTube search provider."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key, timeout=15)
        self.base_url = "https://www.googleapis.com/youtube/v3"

    async def search(self, query: SearchQuery) -> SearchResponse:
        """Search YouTube videos."""
        if not self.api_key:
            # Fallback to web scraping if no API key
            return await self._scrape_youtube(query)

        start_time = datetime.now()

        params = {
            'part': 'snippet',
            'q': query.query,
            'key': self.api_key,
            'maxResults': min(query.max_results, 50),
            'type': 'video',
            'relevanceLanguage': query.language,
            'regionCode': query.region
        }

        if query.filters.get('published_after'):
            params['publishedAfter'] = query.filters['published_after'].isoformat() + 'Z'
        if query.filters.get('published_before'):
            params['publishedBefore'] = query.filters['published_before'].isoformat() + 'Z'
        if query.filters.get('duration'):
            params['videoDuration'] = query.filters['duration']

        url = f"{self.base_url}/search"
        async with self.session or aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"YouTube API error: {response.status}")
                    return await self._scrape_youtube(query)

                data = await response.json()

        results = []
        for item in data.get('items', []):
            snippet = item.get('snippet', {})

            result = SearchResult(
                title=snippet.get('title', ''),
                description=snippet.get('description', ''),
                url=f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                source=SearchEngine.YOUTUBE_API,
                search_type=SearchType.YOUTUBE,
                published_date=datetime.fromisoformat(snippet['publishedAt'].replace('Z', '+00:00')),
                author=snippet.get('channelTitle', ''),
                thumbnail_url=snippet.get('thumbnails', {}).get('default', {}).get('url', ''),
                metadata={
                    'video_id': item['id']['videoId'],
                    'channel_id': snippet.get('channelId', ''),
                    'duration': self._parse_duration(snippet.get('duration', '')),
                    'view_count': snippet.get('viewCount', 0),
                    'like_count': snippet.get('likeCount', 0)
                }
            )
            results.append(result)

        search_time = (datetime.now() - start_time).total_seconds()

        return SearchResponse(
            query=query,
            results=results,
            total_results=data.get('pageInfo', {}).get('totalResults', len(results)),
            search_time=search_time,
            suggestions=self._extract_suggestions(data)
        )

    async def _scrape_youtube(self, query: SearchQuery) -> SearchResponse:
        """Fallback YouTube scraping (limited functionality)."""
        # This would implement web scraping as fallback
        # For now, return empty response
        logger.warning("YouTube API key not provided, scraping not implemented")

        return SearchResponse(
            query=query,
            results=[],
            total_results=0,
            search_time=0.0
        )

    def _parse_duration(self, duration: str) -> Optional[str]:
        """Parse ISO 8601 duration format."""
        # Implementation for parsing PT4M13S format
        if not duration:
            return None
        # Simplified implementation
        return duration

    def _extract_suggestions(self, data: dict) -> List[str]:
        """Extract search suggestions from API response."""
        return []

    def get_supported_languages(self) -> List[str]:
        """Return supported YouTube languages."""
        return [
            'en', 'ja', 'zh', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ko',
            'ar', 'hi', 'th', 'vi', 'tr', 'pl', 'nl', 'sv', 'da', 'no',
            'fi', 'he', 'cs', 'hu', 'ro', 'bg', 'hr', 'sk', 'sl', 'et'
        ]

    def get_supported_regions(self) -> List[str]:
        """Return supported YouTube regions."""
        return [
            'US', 'GB', 'CA', 'AU', 'DE', 'FR', 'JP', 'KR', 'BR', 'MX',
            'IN', 'RU', 'ES', 'IT', 'NL', 'SE', 'NO', 'DK', 'FI', 'PL'
        ]


class AcademicSearchProvider(BaseSearchProvider):
    """Academic paper search provider."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key, timeout=20)
        self.engines = {
            SearchEngine.GOOGLE_SCHOLAR: self._search_google_scholar,
            SearchEngine.ARXIV: self._search_arxiv,
            SearchEngine.SEMANTIC_SCHOLAR: self._search_semantic_scholar,
        }

    async def search(self, query: SearchQuery) -> SearchResponse:
        """Search academic papers."""
        start_time = datetime.now()

        if query.engine not in self.engines:
            raise ValueError(f"Unsupported academic search engine: {query.engine}")

        search_func = self.engines[query.engine]
        results = await search_func(query)

        search_time = (datetime.now() - start_time).total_seconds()

        return SearchResponse(
            query=query,
            results=results,
            total_results=len(results),
            search_time=search_time
        )

    async def _search_google_scholar(self, query: SearchQuery) -> List[SearchResult]:
        """Search Google Scholar."""
        # Implementation for Google Scholar scraping
        # This would use requests or selenium for scraping
        logger.info(f"Searching Google Scholar: {query.query}")

        results = []
        # Placeholder implementation
        return results

    async def _search_arxiv(self, query: SearchQuery) -> List[SearchResult]:
        """Search arXiv."""
        base_url = "http://export.arxiv.org/api/query"

        params = {
            'search_query': f'all:"{query.query}"',
            'start': 0,
            'max_results': query.max_results,
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }

        if query.filters.get('category'):
            params['search_query'] += f' AND cat:{query.filters["category"]}'

        async with self.session or aiohttp.ClientSession() as session:
            async with session.get(base_url, params=params) as response:
                if response.status != 200:
                    logger.error(f"arXiv API error: {response.status}")
                    return []

                xml_content = await response.text()

        # Parse XML response
        import xml.etree.ElementTree as ET
        root = ET.fromstring(xml_content)

        results = []
        for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
            title_elem = entry.find('.//{http://www.w3.org/2005/Atom}title')
            summary_elem = entry.find('.//{http://www.w3.org/2005/Atom}summary')
            author_elems = entry.findall('.//{http://www.w3.org/2005/Atom}author/{http://www.w3.org/2005/Atom}name')
            published_elem = entry.find('.//{http://www.w3.org/2005/Atom}published')
            link_elem = entry.find('.//{http://www.w3.org/2005/Atom}link[@title="pdf"]')

            if title_elem is None:
                continue

            authors = [author.text for author in author_elems if author.text]

            result = SearchResult(
                title=title_elem.text or '',
                description=summary_elem.text if summary_elem is not None else '',
                url=link_elem.get('href', '') if link_elem is not None else '',
                source=SearchEngine.ARXIV,
                search_type=SearchType.ACADEMIC,
                published_date=datetime.fromisoformat(published_elem.text.replace('Z', '+00:00')) if published_elem is not None else None,
                author=', '.join(authors) if authors else None,
                metadata={
                    'arxiv_id': entry.find('.//{http://arxiv.org/schemas/atom}id').text if entry.find('.//{http://arxiv.org/schemas/atom}id') is not None else '',
                    'categories': [cat.get('term') for cat in entry.findall('.//{http://www.w3.org/2005/Atom}category')]
                }
            )
            results.append(result)

        return results

    async def _search_semantic_scholar(self, query: SearchQuery) -> List[SearchResult]:
        """Search Semantic Scholar."""
        # Implementation for Semantic Scholar API
        logger.info(f"Searching Semantic Scholar: {query.query}")
        results = []
        # Placeholder implementation
        return results

    def get_supported_languages(self) -> List[str]:
        """Return supported academic search languages."""
        return ['en', 'zh', 'es', 'fr', 'de', 'ja', 'pt', 'ru', 'it']

    def get_supported_regions(self) -> List[str]:
        """Return supported regions for academic search."""
        return ['US', 'EU', 'ASIA', 'GLOBAL']


class WebSearchProvider(BaseSearchProvider):
    """General web search provider."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key, timeout=15)
        self.engines = {
            SearchEngine.GOOGLE: self._search_google,
            SearchEngine.BING: self._search_bing,
            SearchEngine.DUCKDUCKGO: self._search_duckduckgo,
            SearchEngine.BRAVE: self._search_brave,
        }

    async def search(self, query: SearchQuery) -> SearchResponse:
        """Search the web."""
        start_time = datetime.now()

        if query.engine not in self.engines:
            raise ValueError(f"Unsupported web search engine: {query.engine}")

        search_func = self.engines[query.engine]
        results = await search_func(query)

        search_time = (datetime.now() - start_time).total_seconds()

        return SearchResponse(
            query=query,
            results=results,
            total_results=len(results),
            search_time=search_time
        )

    async def _search_google(self, query: SearchQuery) -> List[SearchResult]:
        """Search Google."""
        # Implementation for Google Search
        # This would typically use Google Custom Search API or scraping
        logger.info(f"Searching Google: {query.query}")
        results = []
        # Placeholder implementation
        return results

    async def _search_bing(self, query: SearchQuery) -> List[SearchResult]:
        """Search Bing."""
        # Implementation for Bing Search API
        logger.info(f"Searching Bing: {query.query}")
        results = []
        # Placeholder implementation
        return results

    async def _search_duckduckgo(self, query: SearchQuery) -> List[SearchResult]:
        """Search DuckDuckGo."""
        # Implementation for DuckDuckGo search
        logger.info(f"Searching DuckDuckGo: {query.query}")
        results = []
        # Placeholder implementation
        return results

    async def _search_brave(self, query: SearchQuery) -> List[SearchResult]:
        """Search Brave."""
        # Implementation for Brave Search API
        logger.info(f"Searching Brave: {query.query}")
        results = []
        # Placeholder implementation
        return results

    def get_supported_languages(self) -> List[str]:
        """Return supported web search languages."""
        return [
            'en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'ko', 'zh',
            'ar', 'hi', 'th', 'vi', 'tr', 'pl', 'nl', 'sv', 'da', 'no',
            'fi', 'he', 'cs', 'hu', 'ro', 'bg', 'hr', 'sk', 'sl', 'et',
            'lv', 'lt', 'mt', 'ga', 'cy', 'eu', 'ca', 'gl', 'ast', 'oc'
        ]

    def get_supported_regions(self) -> List[str]:
        """Return supported regions for web search."""
        return [
            'US', 'GB', 'CA', 'AU', 'DE', 'FR', 'JP', 'KR', 'BR', 'MX',
            'IN', 'RU', 'ES', 'IT', 'NL', 'SE', 'NO', 'DK', 'FI', 'PL',
            'TR', 'GR', 'PT', 'CZ', 'HU', 'RO', 'BG', 'HR', 'SK', 'SI'
        ]


class SearchManager:
    """Main search manager coordinating all search providers."""

    def __init__(self):
        self.providers: Dict[SearchType, BaseSearchProvider] = {}
        self.cache: Dict[str, SearchResponse] = {}
        self.cache_max_age = 300  # 5 minutes
        self._setup_providers()

    def _setup_providers(self) -> None:
        """Initialize search providers."""
        # YouTube provider
        youtube_api_key = self._get_config_value('youtube_api_key')
        self.providers[SearchType.YOUTUBE] = YouTubeSearchProvider(youtube_api_key)

        # Academic provider
        scholar_api_key = self._get_config_value('scholar_api_key')
        self.providers[SearchType.ACADEMIC] = AcademicSearchProvider(scholar_api_key)

        # Web provider
        self.providers[SearchType.WEB] = WebSearchProvider()

    def _get_config_value(self, key: str) -> Optional[str]:
        """Get configuration value from unified config."""
        try:
            from .unified_config import unified_config_manager
            return unified_config_manager.get(f"search.{key}", None)
        except Exception:
            return None

    async def search(self, query: Union[SearchQuery, str], **kwargs) -> SearchResponse:
        """Perform search with query string or SearchQuery object."""
        if isinstance(query, str):
            query = SearchQuery(
                query=query,
                search_type=kwargs.get('search_type', SearchType.WEB),
                engine=kwargs.get('engine', SearchEngine.GOOGLE),
                language=kwargs.get('language', 'en'),
                max_results=kwargs.get('max_results', 10)
            )

        # Check cache first
        cache_key = self._get_cache_key(query)
        cached_response = self._get_cached_response(cache_key)
        if cached_response:
            logger.info(f"Returning cached result for: {query.query}")
            return cached_response

        # Perform search
        provider = self.providers.get(query.search_type)
        if not provider:
            raise ValueError(f"No provider available for search type: {query.search_type}")

        logger.info(f"Searching {query.search_type.value} with {query.engine.value}: {query.query}")

        async with provider:
            response = await provider.search(query)

        # Cache the response
        self._cache_response(cache_key, response)

        return response

    def _get_cache_key(self, query: SearchQuery) -> str:
        """Generate cache key for query."""
        return f"{query.search_type.value}:{query.engine.value}:{query.language}:{hash(query.query)}"

    def _get_cached_response(self, cache_key: str) -> Optional[SearchResponse]:
        """Get cached response if not expired."""
        if cache_key in self.cache:
            cached = self.cache[cache_key]
            # Check if cache is still valid (simple implementation)
            # In production, you'd want more sophisticated cache management
            return cached
        return None

    def _cache_response(self, cache_key: str, response: SearchResponse) -> None:
        """Cache search response."""
        self.cache[cache_key] = response

        # Clean up old cache entries if too many
        if len(self.cache) > 100:
            oldest_keys = sorted(self.cache.keys())[:20]
            for key in oldest_keys:
                del self.cache[key]

    def get_supported_languages(self, search_type: Optional[SearchType] = None) -> Dict[SearchType, List[str]]:
        """Get supported languages for each search type."""
        if search_type:
            provider = self.providers.get(search_type)
            if provider:
                return {search_type: provider.get_supported_languages()}
            return {search_type: []}

        return {
            search_type: provider.get_supported_languages()
            for search_type, provider in self.providers.items()
        }

    def get_supported_engines(self, search_type: SearchType) -> List[SearchEngine]:
        """Get supported engines for a search type."""
        if search_type == SearchType.YOUTUBE:
            return [SearchEngine.YOUTUBE_API, SearchEngine.YOUTUBE_SCRAPER]
        elif search_type == SearchType.ACADEMIC:
            return [SearchEngine.GOOGLE_SCHOLAR, SearchEngine.ARXIV, SearchEngine.SEMANTIC_SCHOLAR]
        elif search_type == SearchType.WEB:
            return [SearchEngine.GOOGLE, SearchEngine.BING, SearchEngine.DUCKDUCKGO, SearchEngine.BRAVE]
        return []

    def clear_cache(self) -> None:
        """Clear search cache."""
        self.cache.clear()
        logger.info("Search cache cleared")


# Global search manager instance
search_manager = SearchManager()
