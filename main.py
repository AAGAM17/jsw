import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from scrapers.perplexity_client import PerplexityClient
from scrapers.metro_scraper import MetroScraper
from utilities.email_handler import EmailHandler
from utilities.whatsapp_handler import WhatsAppHandler
from utilities.logger import configure_logging
from datetime import datetime
from config.settings import Config
import requests
import re
import time

configure_logging()
logger = logging.getLogger(__name__)

def _query_serp(query, site=None):
    """Make SERP API call with retries"""
    try:
        params = {
            'api_key': Config.SERP_API_KEY,
            'q': query + (' site:' + site if site else ' site:.in'),
            'gl': 'in',  # Set location to India
            'hl': 'en',  # Set language to English
            'tbs': 'qdr:d',  # Last day
            'location': 'India',
            'google_domain': 'google.co.in',
            'num': 100  # Maximum results
        }
        
        response = requests.get('https://serpapi.com/search.json', params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"SERP API error for query '{query}': {str(e)}")
        return None

def _search_google():
    """Search for projects using SERP API"""
    all_results = []
    
    # Core search queries
    core_queries = [
        "contract win construction infrastructure india",
        "project announcement foundation laying tender result construction start india",
        "infrastructure project awarded india",
        "construction contract awarded india"
    ]
    
    # Priority sector queries
    sector_queries = [
        "road infrastructure contract win india",
        "rail infrastructure project awarded india",
        "metro rail contract awarded india",
        "commercial real estate construction india",
        "residential real estate project india",
        "port development contract india"
    ]
    
    # Company-specific queries
    company_queries = [
        "Dilip Buildcon wins contract",
        "L&T Construction awarded project",
        "PNC Infratech wins contract",
        "HG Infra Engineering project",
        "IRB Infrastructure contract",
        "Cube Highways project",
        "GR Infraprojects awarded",
        "Afcons Infrastructure contract",
        "RVNL project awarded",
        "J Kumar Infrastructure contract",
        "MEIL project awarded",
        "Ashoka Buildcon contract"
    ]
    
    # Target websites to search
    target_sites = [
        "epc.gov.in",
        "nseindia.com",
        "nhai.gov.in",
        "constructionworld.in",
        "themetrorailguy.com",
        "biddetail.com",
        "newsonprojects.com",
        "constructionopportunities.in",
        "projectxindia.com",
        "metrorailtoday.com",
        "projectstoday.com"
    ]
    
    # Steel-specific queries
    steel_queries = [
        "steel requirement TMT bars india",
        "steel procurement HR plates india",
        "HSLA steel requirement project india",
        "coated steel products construction india",
        "solar steel structure requirement india"
    ]
    
    logger.info("Starting comprehensive SERP API search...")
    
    # Search each query combination
    for query in core_queries + sector_queries + company_queries + steel_queries:
        # Try general search first
        results = _query_serp(query)
        if results and 'organic_results' in results:
            for result in results['organic_results']:
                if _is_relevant_result(result):
                    all_results.append({
                        'title': result.get('title', ''),
                        'description': result.get('snippet', ''),
                        'source_url': result.get('link', ''),
                        'source': 'serp_web',
                        'query': query
                    })
        
        # Then search specific sites
        for site in target_sites:
            site_results = _query_serp(query, site)
            if site_results and 'organic_results' in site_results:
                for result in site_results['organic_results']:
                    if _is_relevant_result(result):
                        all_results.append({
                            'title': result.get('title', ''),
                            'description': result.get('snippet', ''),
                            'source_url': result.get('link', ''),
                            'source': f'serp_{site}',
                            'query': f"{query} site:{site}"
                        })
    
    # Remove duplicates based on URL
    seen_urls = set()
    unique_results = []
    for result in all_results:
        url = result.get('source_url', '').lower()
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_results.append(result)
    
    logger.info(f"Found {len(unique_results)} unique results from SERP API")
    return unique_results

def _is_relevant_result(result):
    """Check if a SERP result is relevant"""
    if not result.get('title') or not result.get('link'):
        return False
        
    title_lower = result.get('title', '').lower()
    snippet_lower = result.get('snippet', '').lower()
    
    # Keywords indicating relevance
    relevant_terms = [
        'contract', 'tender', 'project', 'awarded', 'wins', 'construction',
        'infrastructure', 'development', 'metro', 'railway', 'port',
        'residential', 'commercial', 'steel', 'tmt', 'hr plates', 'hsla',
        'coated', 'solar', 'procurement', 'foundation', 'announcement'
    ]
    
    # Exclude terms
    exclude_terms = [
        'supplier finalized', 'material ordered', 'completed project',
        'project completion', 'inauguration'
    ]
    
    # Check for excluded terms
    if any(term in title_lower or term in snippet_lower for term in exclude_terms):
        return False
    
    # Check for relevant terms
    return any(term in title_lower or term in snippet_lower for term in relevant_terms)

def _enrich_with_firecrawl(projects):
    """Enrich projects with Firecrawl data"""
    logger = logging.getLogger(__name__)
    enriched_projects = []
    firecrawl_attempts = 0
    max_firecrawl_attempts = 4  # Limit total Firecrawl attempts
    
    for project in projects:
        if not project.get('source_url'):
            continue
            
        # Skip social media, PDFs, and problematic domains
        if any(domain in project['source_url'].lower() for domain in [
            'facebook.com', 'twitter.com', '.pdf', 'business-standard.com', 
            'ianslive.in', 'investing.com', 'simplyhired'
        ]):
            continue
            
        try:
            # First try basic scraping
            basic_data = _basic_scrape(project['source_url'])
            if basic_data.get('description') and basic_data.get('value'):
                project.update(basic_data)
                enriched_projects.append(project)
                continue
            
            # Only try Firecrawl for high-priority sources and if we haven't hit the limit
            if firecrawl_attempts < max_firecrawl_attempts:
                # Prioritize specific domains
                priority_domains = ['themetrorailguy.com', 'constructionworld.in', 'projectstoday.com']
                if any(domain in project['source_url'].lower() for domain in priority_domains):
                    try:
                        response = requests.post(
                            'https://api.firecrawl.com/v1/extract',
                            headers={
                                'Authorization': f'Bearer {Config.FIRECRAWL_API_KEY}',
                                'Content-Type': 'application/json'
                            },
                            json={
                                'url': project['source_url'],
                                'selectors': Config.FIRECRAWL_SETTINGS['extraction_rules'],
                                'options': Config.FIRECRAWL_SETTINGS['extraction_options']
                            },
                            timeout=10
                        )
                        
                        if response.status_code == 200:
                            firecrawl_data = response.json()
                            project['firecrawl_data'] = firecrawl_data
                            logger.info(f"Successfully enriched project with Firecrawl: {project['title']}")
                            firecrawl_attempts += 1
                        
                        enriched_projects.append(project)
                        
                    except Exception as e:
                        logger.warning(f"Firecrawl failed for priority domain: {str(e)}")
                        if basic_data.get('description'):
                            project.update(basic_data)
                            enriched_projects.append(project)
                else:
                    # For non-priority domains, use basic scrape if it got any data
                    if basic_data.get('description'):
                        project.update(basic_data)
                        enriched_projects.append(project)
            else:
                # If we've hit the Firecrawl limit, just use basic scrape data
                if basic_data.get('description'):
                    project.update(basic_data)
                    enriched_projects.append(project)
                    
        except Exception as e:
            logger.error(f"Error in enrichment process: {str(e)}")
            continue
    
    return enriched_projects

def _basic_scrape(url):
    """Basic scraping fallback when Firecrawl fails"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove unwanted elements
        for element in soup.find_all(['script', 'style']):
            element.decompose()
        
        # Try to find main content
        main_content = None
        for selector in [
            'article', '.article', '.post', '.entry-content', 
            'main', '#main-content', '.main-content',
            '.news-content', '.project-details'
        ]:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        if not main_content:
            main_content = soup.find('body')
        
        # Extract text content
        text = ' '.join(p.get_text().strip() for p in main_content.find_all('p') if p.get_text().strip())
        
        # Extract any project value mentions
        value_pattern = r'(?:Rs\.?|INR)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)'
        value_match = re.search(value_pattern, text)
        value = float(value_match.group(1).replace(',', '')) if value_match else None
        
        return {
            'description': text[:1000],  # Limit description length
            'value': value,
            'scrape_method': 'basic'
        }
        
    except Exception as e:
        logger.warning(f"Basic scrape failed for {url}: {str(e)}")
        return {
            'description': '',
            'scrape_method': 'failed'
        }

def _extract_company_name(text):
    """Extract company name from text using common patterns"""
    # Common company name patterns
    patterns = [
        r'([A-Za-z\s&]+(?:Limited|Ltd|Corporation|Corp|Infrastructure|Infra|Construction|Engineering|Projects))',
        r'([A-Za-z\s&]+) wins',
        r'([A-Za-z\s&]+) bags',
        r'([A-Za-z\s&]+) secures',
        r'([A-Za-z\s&]+) awarded'
    ]
    
    for pattern in patterns:
        if match := re.search(pattern, text, re.IGNORECASE):
            company = match.group(1).strip()
            # Clean up common suffixes
            for suffix in ['Limited', 'Ltd', 'Corporation', 'Corp', 'Infrastructure', 'Infra', 'Construction', 'Engineering', 'Projects']:
                company = company.replace(suffix, '').strip()
            return company
    
    return 'Unknown Company'

def run_pipeline():
    """Main data processing pipeline"""
    logger = logging.getLogger(__name__)
    logger.info("Starting AI-powered project discovery pipeline...")
    
    try:
        # Initialize components
        perplexity = PerplexityClient()
        metro_scraper = MetroScraper()
        email_handler = EmailHandler()
        whatsapp_handler = WhatsAppHandler()
        
        # Get projects from all sources
        logger.info("Scraping themetrorailguy.com...")
        metro_projects = metro_scraper.scrape_latest_news()
        logger.info(f"Found {len(metro_projects)} projects from Metro Rail Guy")
        
        logger.info("Discovering projects using Perplexity AI...")
        ai_projects = perplexity.research_infrastructure_projects()
        logger.info(f"Found {len(ai_projects)} projects from Perplexity")
        
        logger.info("Fetching projects from SERP API...")
        serp_projects = _search_google()
        logger.info(f"Found {len(serp_projects)} projects from SERP API")
        
        # Combine all projects
        all_projects = metro_projects + ai_projects + serp_projects
        
        if not all_projects:
            logger.warning("No projects found - check sources")
            return
            
        # Try Firecrawl for one high-priority project first
        firecrawl_working = True
        for project in all_projects:
            if any(domain in project.get('source_url', '').lower() for domain in ['themetrorailguy.com', 'constructionworld.in', 'projectstoday.com']):
                try:
                    response = requests.post(
                        'https://api.firecrawl.com/v1/extract',
                        headers={
                            'Authorization': f'Bearer {Config.FIRECRAWL_API_KEY}',
                            'Content-Type': 'application/json'
                        },
                        json={
                            'url': project['source_url'],
                            'selectors': Config.FIRECRAWL_SETTINGS['extraction_rules'],
                            'options': Config.FIRECRAWL_SETTINGS['extraction_options']
                        },
                        timeout=10
                    )
                    response.raise_for_status()
                except Exception as e:
                    logger.warning(f"Firecrawl test failed, bypassing Firecrawl enrichment: {str(e)}")
                    firecrawl_working = False
                break
        
        # Process projects based on Firecrawl status
        quality_projects = []
        logger.info(f"Processing {len(all_projects)} projects for quality filtering...")
        
        for project in all_projects:
            # Skip social media and PDFs
            if any(domain in project.get('source_url', '').lower() for domain in ['facebook.com', 'twitter.com', '.pdf']):
                logger.debug(f"Skipping social/PDF source: {project.get('source_url')}")
                continue
                
            # Skip if title is too short or looks like an error page
            if len(project.get('title', '')) < 5 or any(term in project.get('title', '').lower() for term in ['404', 'error', 'not found']):
                logger.debug(f"Skipping invalid title: {project.get('title')}")
                continue
            
            # Try to extract value from title or description
            value = None
            value_pattern = r'(?:Rs\.?|INR)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)'
            text = f"{project.get('title', '')} {project.get('description', '')}"
            value_match = re.search(value_pattern, text)
            if value_match:
                try:
                    value = float(value_match.group(1).replace(',', ''))
                except ValueError:
                    value = None
            
            # If no value found in text, use the project's value field
            if not value:
                value = project.get('value')
            
            # More lenient value check - include all projects with any value
            if value is not None or project.get('description'):  # Allow projects even without value if they have description
                # Ensure all required fields are present
                project.update({
                    'value': value or 0,  # Default to 0 if no value found
                    'company': project.get('company') or _extract_company_name(text),
                    'description': project.get('description', ''),
                    'start_date': project.get('start_date', datetime.now()),
                    'end_date': project.get('end_date', datetime.now()),
                    'source': project.get('source', 'web'),
                    'source_url': project.get('source_url', ''),
                    'title': project.get('title', '').replace('&amp;', '&')
                })
                
                # Check for relevant terms - be more lenient
                relevant_terms = [
                    'contract', 'project', 'construction', 'infrastructure',
                    'metro', 'railway', 'port', 'highway', 'bridge', 'building',
                    'development', 'tender', 'awarded', 'win', 'steel',
                    'road', 'residential', 'commercial', 'industrial', 'power',
                    'energy', 'plant', 'factory', 'expansion', 'upgrade',
                    'modernization', 'new', 'phase', 'work', 'epc',
                    'contractor', 'builder', 'engineering', 'procurement'
                ]
                
                # More lenient term matching - check individual words and partial matches
                text_words = set(text.lower().split())
                if any(term in text.lower() for term in relevant_terms) or \
                   any(any(term in word for term in relevant_terms) for word in text_words):
                    logger.info(f"Adding quality project: {project['title']} (Rs. {value or 0} Cr)")
                    quality_projects.append(project)
                else:
                    logger.debug(f"Project lacks relevant terms: {project['title']}")
            else:
                logger.debug(f"Project has no value or description: {project['title']}")
        
        if not quality_projects:
            logger.warning("No quality projects found after filtering")
            return
        
        # Log detailed project information
        logger.info(f"\nQuality projects found ({len(quality_projects)}):")
        for idx, project in enumerate(quality_projects, 1):
            logger.info(f"{idx}. {project['company']} - {project['title']}")
            logger.info(f"   Value: Rs. {project.get('value', 0)} Cr")
            logger.info(f"   Source: {project.get('source_url', 'N/A')}\n")
        
        # Sort by value (simple priority)
        sorted_projects = sorted(quality_projects, key=lambda x: x.get('value', 0), reverse=True)
        
        # Log project details for debugging
        logger.info("Quality projects to be sent:")
        for idx, project in enumerate(sorted_projects, 1):
            logger.info(f"{idx}. {project['company']} - {project['title']} (Rs. {project.get('value', 0)} Cr)")
        
        # Send notifications
        logger.info(f"Sending notifications for {len(sorted_projects)} quality projects...")
        
        # Send emails
        email_success = email_handler.send_project_opportunities(sorted_projects)
        if email_success:
            logger.info("Successfully sent email notifications")
        else:
            logger.error("Failed to send email notifications")
        
        # Send WhatsApp messages
        whatsapp_success = whatsapp_handler.send_project_opportunities(sorted_projects)
        if whatsapp_success:
            logger.info("Successfully sent WhatsApp notifications")
        else:
            logger.warning("WhatsApp notifications not sent (disabled or failed)")
            
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    # Run immediately when starting
    run_pipeline()
    # Then schedule future runs
    scheduler.add_job(run_pipeline, 'interval', hours=6, misfire_grace_time=3600)
    print("Starting scheduler... (Ctrl+C to exit)")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("Scheduler stopped")