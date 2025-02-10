import logging
from datetime import datetime, timedelta
import json
from typing import List, Dict, Any
import requests
from config.settings import Config
from .contact_enricher import ContactEnricher
from .email_handler import EmailHandler
import re
from bs4 import BeautifulSoup

class Agent:
    def __init__(self, name: str, instructions: str, functions: List[callable]):
        self.name = name
        self.instructions = instructions
        self.functions = functions
        self.logger = logging.getLogger(f"agent.{name}")

class ProjectDiscoverySystem:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.contact_enricher = ContactEnricher()
        self.email_handler = EmailHandler()
        
        # Initialize Firecrawl headers
        self.firecrawl_headers = {
            'Authorization': f'Bearer {Config.FIRECRAWL_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        # Initialize agents
        self.agents = self._initialize_agents()
        
    def _initialize_agents(self) -> Dict[str, Agent]:
        """Initialize the agent system with enhanced instructions"""
        
        def handoff_to_search_google():
            return self.agents['search']
            
        def handoff_to_map_url():
            return self.agents['mapper']
            
        def handoff_to_website_scraper():
            return self.agents['scraper']
            
        def handoff_to_analyst():
            return self.agents['analyst']
        
        interface_instructions = """
        Automatically detect and analyze recent Indian infrastructure projects requiring steel supply.
        Daily search parameters:
        1. Find all contract awards in last 1 day (0.2cr+ value)
        2. Identify new project announcements with steel procurement needs
        3. Detect tender awards where steel supplier isn't finalized
        4. Track construction milestones requiring material orders
        
        Priority sectors:
        - Road/Rail Infrastructure (especially Metro Projects)
        - Commercial Real Estate
        - Industrial Parks
        - Port Developments
        
        Auto-filter criteria:
        - Projects >0.2 crore INR
        - Procurement within 6 months
        - At least 50 MT steel requirement
        - Indian developers/contractors
        
        Additional JSW-specific criteria:
        - Track previous relationships with contractors
        - Monitor competitor activities
        - Identify projects with TMT Bars and HR Plates requirements
        - Flag high-priority opportunities based on:
            * Project value
            * Existing relationships
            * Strategic importance
            * Timeline urgency
        """
        
        search_instructions = """
        Use these search patterns:
        "contract award" "steel supply" (last week)
        "project announcement" "foundation laying" (last month)
        "tender result" "structural steel" (last 14 days)
        "groundbreaking ceremony" "construction start"
        
        Site-specific searches:
        site:epc.gov.in "awarded to" AND "steel"
        site:nseindia.com "contract win" AND "construction"
        site:nhai.gov.in "tender result"
        site:constructionworld.in "project update"
        site:themetrorailguy.com "contract awarded"
        
        JSW-specific patterns:
        "[company name] wins [project type]"
        "steel requirement" AND "TMT" OR "HR plates"
        "procurement timeline" AND "steel"
        
        Exclude: 
        "supplier finalized", "material ordered", "completed project"
        """
        
        mapper_instructions = """
        Prioritize mapping of:
        - Government tender portals (epc.gov.in, nhai.gov.in)
        - Company investor relations pages
        - Stock exchange filings
        - Verified industry news portals
        
        Focus on:
        - PDF documents with contract details
        - Press releases with procurement information
        - Project timelines and steel requirements
        - Contact information of procurement teams
        
        JSW-specific mapping:
        - Track competitor supply agreements
        - Monitor customer announcements
        - Map project locations to JSW plant proximity
        """
        
        scraper_instructions = """
        Extract detailed project information focusing on:
        1. Contract award details and dates
        2. Steel requirements breakdown by type
        3. Project timelines and milestones
        4. Procurement team contacts
        
        Special attention to:
        - TMT Bars specifications and quantities
        - HR Plates requirements
        - Delivery schedules
        - Quality requirements
        
        Format data for priority analysis:
        - High priority indicators
        - Relationship history
        - Strategic importance factors
        """
        
        analyst_instructions = """
        Extract structured data from content with focus on:
        1. Project value (INR crores)
        2. Steel requirement (metric tons)
        3. Procurement timeline
        4. Contract award date
        5. Key decision makers
        
        Validate financial figures against project scope.
        Calculate approximate steel needs using:
        - High-rise construction: 60kg/sqft
        - Infrastructure projects: 100-150kg/lane-km
        - Metro projects: 150-200kg/meter
        - Industrial structures: 80-100kg/sqft
        
        JSW-specific analysis:
        - Match requirements with JSW product portfolio
        - Calculate delivery logistics from nearest plant
        - Assess competition presence
        - Evaluate relationship leverage opportunities
        
        Priority scoring based on:
        - Project value and steel requirement
        - Timeline urgency
        - Strategic importance
        - Existing relationships
        - Geographic proximity to JSW plants
        
        Format results with:
        - Verified source links
        - Contact information
        - Relationship history
        - Priority indicators
        - Action recommendations
        """
        
        return {
            'interface': Agent("Steel Opportunity Interface", interface_instructions, [handoff_to_search_google]),
            'search': Agent("Steel Project Search Agent", search_instructions, [self._search_google, handoff_to_map_url]),
            'mapper': Agent("Government & Corporate Source Mapper", mapper_instructions, [self._map_url_pages, handoff_to_website_scraper]),
            'scraper': Agent("Website Scraper Agent", scraper_instructions, [self._scrape_url, handoff_to_analyst]),
            'analyst': Agent("Steel Opportunity Analyst", analyst_instructions, [self._analyze_website_content])
        }
    
    def discover_opportunities(self) -> List[Dict[str, Any]]:
        """Main method to discover and process new opportunities"""
        try:
            # Start with interface agent
            interface_agent = self.agents['interface']
            self.logger.info(f"Starting opportunity discovery with {interface_agent.name}")
            
            # Get search results
            search_agent = interface_agent.functions[0]()
            search_results = search_agent.functions[0]()
            
            # Process each search result
            opportunities = []
            for result in search_results:
                try:
                    # Map URLs
                    mapper_agent = search_agent.functions[1]()
                    mapped_urls = mapper_agent.functions[0](result)
                    
                    # Scrape content
                    scraper_agent = mapper_agent.functions[1]()
                    content = scraper_agent.functions[0](mapped_urls)
                    
                    # Analyze content
                    analyst_agent = scraper_agent.functions[1]()
                    opportunity = analyst_agent.functions[0](content)
                    
                    if self._validate_opportunity(opportunity):
                        opportunities.append(opportunity)
                        
                except Exception as e:
                    self.logger.error(f"Error processing search result: {str(e)}")
                    continue
            
            return opportunities
            
        except Exception as e:
            self.logger.error(f"Error in opportunity discovery: {str(e)}")
            return []
    
    def _search_google(self) -> List[Dict[str, Any]]:
        """Execute SERP API search with retries"""
        try:
            headers = {
                'Authorization': f'Bearer {Config.SERP_API_KEY}',
                'Content-Type': 'application/json'
            }
            
            all_results = []
            
            # 1. Search Google Web Results
            for query in Config.SERP_SETTINGS['search_queries']:
                try:
                    # Add company names to query for better targeting
                    company_names = [
                        company['name']
                        for category in Config.PROJECT_DISCOVERY['target_companies'].values()
                        for company in category
                    ]
                    
                    # Create company-specific queries
                    for company in company_names:
                        company_query = f'"{company}" {query}'
                        
                        response = requests.get(
                            'https://serpapi.com/search',
                            params={
                                'q': company_query,
                                **Config.SERP_SETTINGS['search_parameters']
                            },
                            headers=headers
                        )
                        
                        response.raise_for_status()
                        data = response.json()
                        
                        if 'organic_results' in data:
                            all_results.extend(data['organic_results'])
                            
                except Exception as e:
                    self.logger.error(f"Error in SERP API search for query '{query}': {str(e)}")
                    continue
            
            # 2. Search Google News
            for query in Config.SERP_SETTINGS['search_queries']:
                try:
                    response = requests.get(
                        'https://serpapi.com/search',
                        params={
                            'q': query,
                            **Config.SERP_SETTINGS['news_parameters']
                        },
                        headers=headers
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    if 'news_results' in data:
                        all_results.extend(data['news_results'])
                        
                except Exception as e:
                    self.logger.error(f"Error in SERP News API search for query '{query}': {str(e)}")
                    continue
            
            # 3. Scrape company announcement pages
            for category in Config.PROJECT_DISCOVERY['target_companies'].values():
                for company in category:
                    for url in company['announcement_urls']:
                        try:
                            # Use Firecrawl to scrape announcement pages
                            response = requests.post(
                                'https://api.firecrawl.io/extract',
                                headers=self.firecrawl_headers,
                                json={
                                    'url': url,
                                    'elements': {
                                        'announcements': {
                                            'selectors': [
                                                '.news-item',
                                                '.announcement',
                                                '.media-item',
                                                'article'
                                            ]
                                        }
                                    },
                                    **Config.FIRECRAWL_SETTINGS['extraction_options']
                                }
                            )
                            
                            response.raise_for_status()
                            data = response.json()
                            
                            if 'announcements' in data:
                                announcements = data['announcements']
                                for announcement in announcements:
                                    # Add company context to the announcement
                                    announcement['company'] = company['name']
                                    announcement['source'] = 'company_announcement'
                                    all_results.append(announcement)
                                    
                        except Exception as e:
                            self.logger.error(f"Error scraping announcement page {url}: {str(e)}")
                            continue
            
            # Remove duplicates based on URL
            seen_urls = set()
            unique_results = []
            
            for result in all_results:
                url = result.get('link') or result.get('url')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_results.append(result)
            
            return unique_results
            
        except Exception as e:
            self.logger.error(f"Error in search operations: {str(e)}")
            return []
    
    def _map_url_pages(self, search_results: List[Dict[str, Any]]) -> List[str]:
        """Map search results to relevant URLs"""
        try:
            mapped_urls = []
            for result in search_results:
                url = result.get('link')
                if url and self._is_relevant_url(url):
                    mapped_urls.append(url)
            return mapped_urls
        except Exception as e:
            self.logger.error(f"Error mapping URLs: {str(e)}")
            return []
    
    def _is_relevant_url(self, url: str) -> bool:
        """Check if URL is from a relevant source"""
        relevant_domains = [
            'constructionworld.in',
            'themetrorailguy.com',
            'epc.gov.in',
            'nhai.gov.in',
            'nseindia.com'
        ]
        return any(domain in url.lower() for domain in relevant_domains)
    
    def _scrape_url(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Scrape content from URLs using Firecrawl"""
        try:
            scraped_content = []
            for url in urls:
                try:
                    # Use Firecrawl's extraction API
                    response = requests.post(
                        'https://api.firecrawl.io/extract',
                        headers=self.firecrawl_headers,
                        json={
                            'url': url,
                            'elements': {
                                'project_details': {
                                    'selectors': [
                                        'article',
                                        '.entry-content',
                                        '.project-details',
                                        '.tender-details'
                                    ]
                                },
                                'contact_info': {
                                    'selectors': [
                                        '.contact-details',
                                        '.procurement-team',
                                        '.project-contact'
                                    ]
                                },
                                'dates': {
                                    'selectors': [
                                        '.project-timeline',
                                        '.schedule',
                                        '.dates'
                                    ]
                                },
                                'specifications': {
                                    'selectors': [
                                        '.specifications',
                                        '.requirements',
                                        '.steel-specs'
                                    ]
                                }
                            },
                            'clean_html': True,
                            'remove_ads': True,
                            'extract_tables': True
                        }
                    )
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    # Process extracted content
                    processed_content = self._process_firecrawl_response(data, url)
                    if processed_content:
                        scraped_content.append(processed_content)
                        
                except Exception as e:
                    self.logger.error(f"Error scraping URL {url} with Firecrawl: {str(e)}")
                    # Fallback to basic scraping if Firecrawl fails
                    try:
                        basic_content = self._basic_scrape(url)
                        if basic_content:
                            scraped_content.append(basic_content)
                    except Exception as basic_error:
                        self.logger.error(f"Basic scraping also failed for {url}: {str(basic_error)}")
                    continue
                    
            return scraped_content
            
        except Exception as e:
            self.logger.error(f"Error in URL scraping: {str(e)}")
            return []
    
    def _process_firecrawl_response(self, data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """Process the Firecrawl API response"""
        try:
            processed_data = {
                'url': url,
                'content': {},
                'metadata': {}
            }
            
            # Extract project details
            if project_content := data.get('project_details', {}).get('content'):
                processed_data['content']['project_details'] = project_content
                
                # Try to extract project value
                value_matches = re.findall(r'(?:Rs\.?|INR)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)', project_content)
                if value_matches:
                    processed_data['metadata']['project_value'] = float(value_matches[0].replace(',', ''))
                
                # Try to extract steel requirements
                steel_matches = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)', project_content)
                if steel_matches:
                    processed_data['metadata']['steel_requirement'] = float(steel_matches[0].replace(',', ''))
            
            # Extract contact information
            if contact_content := data.get('contact_info', {}).get('content'):
                processed_data['content']['contact_info'] = contact_content
                
                # Try to extract email addresses
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', contact_content)
                if emails:
                    processed_data['metadata']['contact_emails'] = emails
                
                # Try to extract phone numbers
                phones = re.findall(r'(?:\+91|0)?[789]\d{9}', contact_content)
                if phones:
                    processed_data['metadata']['contact_phones'] = phones
            
            # Extract dates
            if dates_content := data.get('dates', {}).get('content'):
                processed_data['content']['dates'] = dates_content
                
                # Try to extract project timeline
                date_matches = re.findall(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}', dates_content)
                if len(date_matches) >= 2:
                    processed_data['metadata']['start_date'] = datetime.strptime(date_matches[0], '%B %Y')
                    processed_data['metadata']['end_date'] = datetime.strptime(date_matches[1], '%B %Y')
            
            # Extract specifications
            if specs_content := data.get('specifications', {}).get('content'):
                processed_data['content']['specifications'] = specs_content
                
                # Try to extract steel types
                steel_types = {
                    'TMT': re.findall(r'TMT[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)', specs_content),
                    'HR_Plates': re.findall(r'HR[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)', specs_content)
                }
                if any(steel_types.values()):
                    processed_data['metadata']['steel_types'] = steel_types
            
            return processed_data
            
        except Exception as e:
            self.logger.error(f"Error processing Firecrawl response: {str(e)}")
            return None
    
    def _basic_scrape(self, url: str) -> Dict[str, Any]:
        """Basic scraping fallback method"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.select('script, style, iframe, nav, footer, header, aside'):
                element.decompose()
            
            # Get main content
            main_content = ''
            for tag in ['article', '.entry-content', '.post-content', 'main']:
                if content := soup.select_one(tag):
                    main_content = content.get_text(strip=True)
                    break
            
            if not main_content:
                main_content = soup.get_text(strip=True)
            
            return {
                'url': url,
                'content': {'raw_text': main_content},
                'metadata': {}
            }
            
        except Exception as e:
            self.logger.error(f"Error in basic scraping for {url}: {str(e)}")
            return None
    
    def _analyze_website_content(self, content_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze scraped content for project opportunities"""
        try:
            opportunities = []
            for content in content_list:
                try:
                    opportunity = self._extract_project_info(content)
                    if opportunity:
                        opportunities.append(opportunity)
                except Exception as e:
                    self.logger.error(f"Error analyzing content from {content['url']}: {str(e)}")
                    continue
            return opportunities
        except Exception as e:
            self.logger.error(f"Error in content analysis: {str(e)}")
            return []
    
    def _extract_project_info(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract project information from content"""
        # Implementation would include parsing logic specific to each source
        pass
    
    def _validate_opportunity(self, opportunity: Dict[str, Any]) -> bool:
        """Validate if opportunity meets criteria"""
        try:
            if not opportunity:
                return False
                
            # Check project value
            value_in_cr = opportunity.get('value', 0)
            if value_in_cr < 500:  # 500 crore minimum
                return False
            
            # Check steel requirement
            steel_req = opportunity.get('steel_requirement', 0)
            if steel_req < 5000:  # 5000 MT minimum
                return False
            
            # Check timeline
            start_date = opportunity.get('start_date')
            if start_date:
                months_to_start = (start_date - datetime.now()).days / 30
                if months_to_start > 6:  # Within 6 months
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating opportunity: {str(e)}")
            return False 