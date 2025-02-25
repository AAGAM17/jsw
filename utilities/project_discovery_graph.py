"""Project discovery workflow implementation using LangGraph."""

from typing import Annotated, Sequence, TypedDict, Union
from langgraph.graph import Graph, StateGraph
from langgraph.prebuilt import ToolExecutor
import operator
from datetime import datetime, timedelta
import logging
from config.settings import Config
from .email_handler import EmailHandler
from whatsapp.interakt_handler import InteraktHandler
from scrapers.metro_scraper import MetroScraper
import re
import time
from exa_py import Exa
from groq import Groq
from .contact_finder import ContactFinder

logger = logging.getLogger(__name__)

# Define state types
class ProjectData(TypedDict):
    """Type definition for project data."""
    title: str
    description: str
    source_url: str
    source: str
    value: float
    company: str
    start_date: datetime
    end_date: datetime
    steel_requirements: dict
    teams: list
    priority_score: int
    contacts: list

class WorkflowState(TypedDict):
    """Type definition for workflow state."""
    projects: list[ProjectData]
    filtered_projects: list[ProjectData]
    enriched_projects: list[ProjectData]
    prioritized_projects: list[ProjectData]
    error: Union[str, None]
    status: str

def extract_company_name(text: str) -> Union[str, None]:
    """Extract company name from text."""
    patterns = [
        r'(?:M/s\.|M/s|Messrs\.)?\s*([A-Za-z\s&\.]+(?:Limited|Ltd|Corporation|Corp|Infrastructure|Infra|Construction|Engineering|Projects|Builders|Industries|Enterprises|Company|Pvt|Private|Public))',
        r'(?:M/s\.|M/s|Messrs\.)?\s*([A-Za-z\s&\.]+)\s+(?:has been awarded|has won|wins|awarded to|bags|secures|emerges|selected for)',
        r'([A-Z&]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Limited|Ltd|Corp|Infrastructure|Construction))?)',
        r'([A-Za-z\s&\.]+)-([A-Za-z\s&\.]+)\s+(?:JV|Joint Venture|Consortium)'
    ]
    
    for pattern in patterns:
        if match := re.search(pattern, text):
            company = match.group(1).strip()
            # Remove all common prefixes including 'projects.'
            company = re.sub(r'^(?:M/s\.|M/s|Messrs\.|cr\s+|projects\.|Projects\.|project\.|Project\.)\s*', '', company)
            company = re.sub(r'\s+(?:Private|Pvt|Public|Company)\s+(?:Limited|Ltd)$', ' Limited', company)
            company = re.sub(r'\s+(?:Private|Pvt|Public|Company)$', '', company)
            company = re.sub(r'\s+', ' ', company)
            company = company.replace(' and ', ' & ')
            
            if len(company) > 3 and not any(term in company.lower() for term in ['404', 'error', 'not found', 'page']):
                return company
    
    return None

def extract_project_value(text: str) -> Union[float, None]:
    """Extract project value from text."""
    patterns = [
        r'(?:Rs\.|Rs|INR|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore|Cr)',
        r'contract value of (?:Rs\.|Rs|INR|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore|Cr)',
        r'project value of (?:Rs\.|Rs|INR|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore|Cr)',
        r'worth (?:Rs\.|Rs|INR|₹)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore|Cr)'
    ]
    
    for pattern in patterns:
        if match := re.search(pattern, text, re.IGNORECASE):
            try:
                value = float(match.group(1).replace(',', ''))
                if 1 <= value <= 100000:  # Validate between 1 crore and 1 lakh crore
                    return value
            except ValueError:
                continue
    
    return None

def determine_product_teams(project: ProjectData) -> list[str]:
    """Determine which product teams should receive the project."""
    text = f"{project.get('title', '')} {project.get('description', '')}".lower()
    
    # Define project type patterns with priority order
    project_patterns = [
        # Metro/Railway (highest priority)
        {
            'type': 'metro_rail',
            'patterns': ['metro', 'railway', 'rail', 'train', 'locomotive', 'coach', 'rolling stock'],
            'teams': ['HR_CR_PLATES', 'TMT_BARS']
        },
        # Roads/Highways/Bridges
        {
            'type': 'road_bridge',
            'patterns': ['highway', 'road', 'bridge', 'flyover', 'viaduct', 'corridor', 'expressway'],
            'teams': ['TMT_BARS', 'HR_CR_PLATES']
        },
        # Buildings/Real Estate
        {
            'type': 'building',
            'patterns': ['building', 'tower', 'complex', 'mall', 'hospital', 'hotel', 'apartment', 'residential'],
            'teams': ['TMT_BARS', 'COATED_PRODUCTS']
        },
        # Industrial/Manufacturing
        {
            'type': 'industrial',
            'patterns': ['factory', 'plant', 'manufacturing', 'industrial', 'warehouse', 'storage'],
            'teams': ['HR_CR_PLATES', 'COATED_PRODUCTS']
        },
        # Power/Energy (including solar)
        {
            'type': 'power',
            'patterns': ['power plant', 'solar', 'renewable', 'wind', 'energy', 'electricity'],
            'teams': ['SOLAR', 'COATED_PRODUCTS']
        },
        # Water/Irrigation
        {
            'type': 'water',
            'patterns': ['dam', 'reservoir', 'canal', 'pipeline', 'water', 'irrigation'],
            'teams': ['HR_CR_PLATES', 'TMT_BARS']
        }
    ]
    
    # Check patterns in priority order
    for pattern_group in project_patterns:
        if any(pattern in text for pattern in pattern_group['patterns']):
            project['project_type'] = pattern_group['type']  # Set project type
            return pattern_group['teams']
    
    # Default to TMT_BARS if no specific type matches
    project['project_type'] = 'infrastructure'
    return ['TMT_BARS']

def calculate_priority_score(project: ProjectData) -> int:
    """Calculate priority score for a project."""
    try:
        value = float(project.get('value', 0))
        start_date = project.get('start_date', datetime.now())
        
        # Calculate days until start
        days_until_start = (start_date - datetime.now()).days
        
        # Calculate time factor (higher score for closer start dates)
        time_factor = max(0, 1 - (days_until_start / 365))
        
        # Calculate value factor (higher score for higher values)
        value_factor = min(1, value / 1000)
        
        # Combine factors with weights
        priority_score = (
            time_factor * Config.PRIORITY_WEIGHTS['time_factor'] +
            value_factor * Config.PRIORITY_WEIGHTS['value_factor']
        )
        
        return round(priority_score * 100)
        
    except Exception as e:
        logger.error(f"Error calculating priority score: {str(e)}")
        return 50

def scrape_projects(state: WorkflowState) -> WorkflowState:
    """Scrape projects from various sources."""
    try:
        logger.info("Starting project scraping...")
        
        # Initialize components
        metro_scraper = MetroScraper()
        exa = Exa(api_key=Config.EXA_API_KEY)
        
        # Get projects from sources
        metro_projects = metro_scraper.scrape_latest_news()
        
        # Get Exa projects with retry mechanism
        exa_projects = []
        max_retries = 3
        for query in Config.EXA_SETTINGS['search_queries']:
            for retry in range(max_retries):
                try:
                    time.sleep(1 + retry)  # Exponential backoff
                    search_results = exa.search(
                        query,
                        num_results=2,
                        include_domains=Config.EXA_SETTINGS['search_parameters']['include_domains']
                    )
                    
                    if search_results and search_results.results:
                        for result in search_results.results:
                            if any(domain in result.url.lower() for domain in Config.EXA_SETTINGS['search_parameters']['exclude_domains']):
                                continue
                                
                            content = exa.get_contents(
                                urls=[result.url],
                                text={"max_characters": Config.EXA_SETTINGS['search_parameters']['max_characters']}
                            )
                            
                            if content and content.results:
                                exa_projects.append({
                                    'title': result.title,
                                    'description': content.results[0].text[:1000],
                                    'source_url': result.url,
                                    'source': 'exa_web',
                                    'value': 0,  # Will be enriched later
                                    'company': '',  # Will be enriched later
                                    'start_date': datetime.now(),
                                    'end_date': datetime.now() + timedelta(days=365)
                                })
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    if retry == max_retries - 1:  # Last retry
                        logger.error(f"Error in Exa search for query '{query}' after {max_retries} retries: {str(e)}")
                    time.sleep(1)  # Wait before retry
                    continue
        
        # Combine all projects with deduplication
        seen_urls = set()
        all_projects = []
        
        for project in metro_projects + exa_projects:
            url = project.get('source_url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_projects.append(project)
        
        state['projects'] = all_projects
        state['status'] = 'projects_scraped'
        return state
        
    except Exception as e:
        state['error'] = f"Error in project scraping: {str(e)}"
        state['status'] = 'error'
        return state

def filter_projects(state: WorkflowState) -> WorkflowState:
    """Filter and validate projects."""
    try:
        logger.info(f"Filtering {len(state['projects'])} projects...")
        
        # JSW filtering terms
        jsw_terms = [
            # Company names and variations
            'jsw', 'jindal', 'js steel', 'jindal steel', 'jindal steel & power',
            'jindal steel and power', 'jsw steel limited', 'jsw group',
            'jsw infrastructure', 'jsw energy', 'jsw holdings', 'jsw cement',
            'jsw paints', 'jsw ventures', 'jsw future energy', 'jsw one',
            'jsw renew', 'jsw hydro', 'jsw utilities', 'jsw steel usa',
            'jsw steel italy', 'jsw steel coated', 'jsw ispat', 'jsw projects',
            'jsw techno projects', 'jsw material handling', 'jsw severfield',
            'jsw steel (usa)', 'jsw steel (italy)', 'jsw mergers', 'jsw overseas',
            'jsw steel coated products', 'jsw steel plant', 'jsw steel factory',
            'jsw steel mill', 'jsw steel works', 'jsw steel expansion',
            'jsw steel production', 'jsw steel capacity', 'jsw steel output',
            'jsw steel exports', 'jsw steel imports', 'jsw steel sales',
            'jsw steel revenue', 'jsw steel profit', 'jsw steel earnings',
            'jsw steel results', 'jsw steel performance', 'jsw steel shares',
            'jsw steel stock', 'jsw steel market', 'jsw steel trade',
            'jsw steel supply', 'jsw steel demand', 'jsw steel prices',
            'jsw steel rates', 'jsw steel cost', 'jsw steel value',
            'jsw steel quality', 'jsw steel grade', 'jsw steel specification',
            'jsw steel standards', 'jsw steel certification', 'jsw steel testing',
            'jsw steel research', 'jsw steel development', 'jsw steel innovation',
            'jsw steel technology', 'jsw steel equipment', 'jsw steel machinery',
            'jsw steel tools', 'jsw steel components', 'jsw steel parts',
            'jsw steel materials', 'jsw steel raw materials', 'jsw steel scrap',
            'jsw steel ore', 'jsw steel coal', 'jsw steel coke',
            'jsw steel limestone', 'jsw steel flux', 'jsw steel additives',
            'jsw steel chemicals', 'jsw steel gases', 'jsw steel water',
            'jsw steel energy', 'jsw steel power', 'jsw steel electricity',
            'jsw steel fuel', 'jsw steel oil', 'jsw steel gas',
            'jsw steel environment', 'jsw steel safety', 'jsw steel health',
            'jsw steel security', 'jsw steel protection', 'jsw steel measures',
            'jsw steel standards', 'jsw steel compliance', 'jsw steel regulations',
            'jsw steel rules', 'jsw steel guidelines', 'jsw steel policies',
            'jsw steel procedures', 'jsw steel processes', 'jsw steel operations',
            'jsw steel activities', 'jsw steel tasks', 'jsw steel jobs',
            'jsw steel employment', 'jsw steel recruitment', 'jsw steel hiring',
            'jsw steel training', 'jsw steel education', 'jsw steel skills',
            'jsw steel knowledge', 'jsw steel expertise', 'jsw steel experience',
            'jsw steel qualification', 'jsw steel certification', 'jsw steel degree',
            'jsw steel diploma', 'jsw steel course', 'jsw steel program',
            
            # JSW Products and brands
            'jsw neosteel', 'jsw steel', 'jsw trusteel', 'neosteel', 'trusteel',
            'jsw fastbuild', 'jsw galvalume', 'jsw colour coated', 'jsw coated', 
            'jsw gi', 'jsw hr', 'jsw cr', 'jsw tmt', 'jsw electrical steel', 
            'jsw special steel', 'jsw plates', 'jsw structural',
            
            # Product variations
            'neosteel 550d', 'neosteel 600', 'neosteel eds', 'neosteel crs',
            'neosteel fastbuild', 'neostrands pc', 'trusteel plates',
            'jsw galvanized', 'jsw colour-coated', 'jsw coated',
            
            # Additional JSW-related terms
            'jspl', 'jindal saw', 'jindal stainless', 'jindal steel works',
            'jindal group', 'jindal family', 'sajjan jindal', 'parth jindal',
            'jsw foundation', 'jsw sports', 'jsw bengaluru fc', 'jsw bangalore'
        ]

        # Steel terms that might indicate JSW involvement
        steel_terms = [
            'steel', 'tmt', 'bars', 'coils', 'plates', 'sheets',
            'galvanized', 'colour-coated', 'color-coated', 'galvalume',
            'structural steel', 'special steel', 'electrical steel',
            'steel plant', 'steel mill', 'steel works', 'steel factory',
            'steel production', 'steel capacity', 'steel output',
            'steel exports', 'steel imports', 'steel sales',
            'steel supply', 'steel demand', 'steel prices',
            'steel quality', 'steel grade', 'steel specification'
        ]

        filtered_projects = []
        jsw_projects = []
        
        for project in state['projects']:
            try:
                # Skip invalid URLs
                if not project.get('source_url') or not isinstance(project.get('source_url'), str):
                    continue
                
                # Skip social media and PDFs
                if any(domain in project['source_url'].lower() for domain in ['facebook.com', 'twitter.com', '.pdf']):
                    continue
                
                # Validate title
                title = project.get('title', '').strip()
                if len(title) < 5 or any(term in title.lower() for term in ['404', 'error', 'not found']):
                    continue
                
                # Extract and validate company name early
                text = f"{title} {project.get('description', '')}"
                company_name = project.get('company') or extract_company_name(text)
                if not company_name or len(company_name) < 3:
                    continue
                
                # Combine all text for JSW checks
                title_lower = title.lower()
                desc_lower = project.get('description', '').lower()
                all_text = f"{company_name} {title} {project.get('description', '')} {project.get('source', '')}".lower()
                
                # Check for JSW mentions in title or description
                if 'jsw' in title_lower or 'jsw' in desc_lower or 'jindal' in title_lower or 'jindal' in desc_lower:
                    jsw_projects.append(project)
                    logger.info(f"Filtered JSW project (title/desc): {title}")
                    continue
                
                # Check for JSW supply/provider mentions
                if any(term in title_lower or term in desc_lower for term in [
                    'jsw steel to supply', 'jsw steel supplies', 'jsw steel to provide',
                    'jsw steel provides', 'jsw steel to deliver', 'jsw steel delivers',
                    'jindal steel to supply', 'jindal steel supplies', 'jindal steel to provide',
                    'jindal steel provides', 'jindal steel to deliver', 'jindal steel delivers'
                ]):
                    jsw_projects.append(project)
                    logger.info(f"Filtered JSW supply project: {title}")
                    continue
                
                # Check for JSW terms in all text
                if any(term in all_text for term in jsw_terms):
                    jsw_projects.append(project)
                    logger.info(f"Filtered JSW project (terms): {title}")
                    continue
                
                # Check URL for JSW domains
                if any(domain in project['source_url'].lower() for domain in [
                    'jsw.in', 'jswsteel.com', 'jsw.com', 'jindalsteel.com', 
                    'jindalsteelpower.com', 'jspl.com', 'jindalsawltd.com'
                ]):
                    jsw_projects.append(project)
                    logger.info(f"Filtered JSW project (URL): {title}")
                    continue
                
                # If mentions steel products, check for JSW connection
                if any(term in all_text for term in steel_terms):
                    if any(term in all_text for term in ['jsw', 'jindal', 'neosteel', 'trusteel']):
                        jsw_projects.append(project)
                        logger.info(f"Filtered JSW-related steel project: {title}")
                        continue
                
                # Extract and validate project value
                value = project.get('value') or extract_project_value(text)
                if not value or value <= 0:
                    continue
                
                # Check if JSW is mentioned as supplier or partner
                if 'jsw' in all_text and any(term in all_text for term in [
                    'supply', 'supplier', 'supplied by', 'partner', 'partnership',
                    'collaboration', 'agreement', 'mou', 'contract with'
                ]):
                    jsw_projects.append(project)
                    logger.info(f"Filtered JSW supplier/partner project: {title}")
                    continue
                
                # Validate and convert dates
                try:
                    start_date = project.get('start_date')
                    if isinstance(start_date, str):
                        start_date = datetime.strptime(start_date, '%Y-%m-%d')
                    elif not isinstance(start_date, datetime):
                        start_date = datetime.now()
                    
                    end_date = project.get('end_date')
                    if isinstance(end_date, str):
                        end_date = datetime.strptime(end_date, '%Y-%m-%d')
                    elif not isinstance(end_date, datetime):
                        end_date = start_date + timedelta(days=365)
                    
                    # Ensure end_date is after start_date
                    if end_date <= start_date:
                        end_date = start_date + timedelta(days=365)
                except (ValueError, TypeError):
                    start_date = datetime.now()
                    end_date = start_date + timedelta(days=365)
                
                # Update project with validated data
                project.update({
                    'title': title,
                    'value': value,
                    'company': company_name,
                    'start_date': start_date,
                    'end_date': end_date,
                    'description': project.get('description', '')[:2000]  # Limit description length
                })
                
                filtered_projects.append(project)
                
            except Exception as e:
                logger.error(f"Error filtering project: {str(e)}")
                continue
        
        # Log filtering results
        if jsw_projects:
            logger.info(f"Filtered out {len(jsw_projects)} JSW-related projects:")
            for project in jsw_projects:
                logger.info(f"- {project.get('company')}: {project.get('title')}")
        
        if not filtered_projects:
            logger.warning("No projects passed filtering stage")
        else:
            logger.info(f"Retained {len(filtered_projects)} non-JSW projects")
        
        state['filtered_projects'] = filtered_projects
        state['status'] = 'projects_filtered'
        return state
        
    except Exception as e:
        state['error'] = f"Error in project filtering: {str(e)}"
        state['status'] = 'error'
        return state

def generate_catchy_headline(project: dict) -> str:
    """Generate a catchy headline for a project using Groq."""
    try:
        groq_client = Groq()
        
        # Prepare context from project details
        context = f"""
        You are an AI assistant that specializes in writing concise headlines for JSW Steel's sales team about newly awarded infrastructure projects. Your goal is to quickly convey the potential steel demand of the project, not the monetary value of the contract. Focus on the physical size, length, area, or volume of the project.

        Project Details:
        - Original Title: {project.get('title', '')}
        - Company: {project.get('company', '')}
        - Description: {project.get('description', '')}
        - Specifications:
          * Length: {project.get('specifications', {}).get('length')}
          * Area: {project.get('specifications', {}).get('area')}
          * Capacity: {project.get('specifications', {}).get('capacity')}
          * Floors: {project.get('specifications', {}).get('floors')}
        - Project Type: {project.get('project_type', '')}

        Instructions:
        1. Analyze the input to identify the type of infrastructure project (e.g., road, metro, bridge, building).
        2. Extract key details about the project's size, such as:
           * Length in kilometers or meters (for roads, railways, pipelines)
           * Area in square meters or hectares (for buildings, industrial parks)
           * Number of units (for housing projects, bridges, stations)
           * Volume (for dams, reservoirs)
        3. Create a headline that is approximately 9-10 words in length that prioritizes the project's size over its monetary value.
        4. Use strong verbs and clear language.
        5. Do NOT include the exact contract value in the headline unless the size of the project cannot be described without it.

        Example Headlines:
        * L&T to build 65 km Patna road project
        * Afcons wins Delhi metro extension for 12 stations
        * Tata wins order for 5000 affordable housing units
        * MEIL to construct 200-km irrigation canal in Andhra
        
        Return ONLY the headline, no extra text or lines.
        """
        
        completion = groq_client.chat.completions.create(
            messages=[{
                "role": "system",
                "content": "You are an AI assistant that specializes in writing concise headlines for JSW Steel's sales team about newly awarded infrastructure projects. Your goal is to quickly convey the potential steel demand of the project, not the monetary value of the contract. Focus on the physical size, length, area, or volume of the project."
            }, {
                "role": "user",
                "content": context
            }],
            model="llama-3.1-8b-instant",
            temperature=0.3,  
            max_tokens=500   
        )
        
        headline = completion.choices[0].message.content.strip()
        
        headline = headline.replace('"', '').replace("'", "")
        headline = re.sub(r'\s+', ' ', headline).strip()
        headline = re.sub(r'\(.*?\)', '', headline).strip()  # Remove any parenthetical text
        headline = re.sub(r'(?i)\b(ltd|limited|corp|corporation)\b', '', headline).strip()  # Remove company suffixes
        
        # Remove any company headers or extra lines
        headline = headline.split('\n')[-1].strip()  # Take only the last line if multiple lines
        
        # Ensure it's not too long
        if len(headline) > 80:
            headline = headline[:77] + "..."
            
        return headline
        
    except Exception as e:
        logger.error(f"Error generating headline: {str(e)}")
        return project.get('title', '')  # Fallback to original title

def enrich_projects(state: WorkflowState) -> WorkflowState:
    """Enrich projects with steel requirements, team assignments, and contact information."""
    try:
        logger.info(f"Enriching {len(state['filtered_projects'])} projects...")
        
        email_handler = EmailHandler()
        contact_finder = ContactFinder()  # Initialize contact finder
        enriched_projects = []
        max_retries = 3
        
        # JSW product terms to filter out
        jsw_product_terms = [
            'jsw neosteel', 'jsw steel', 'jsw trusteel', 'neosteel', 'trusteel',
            'jsw fastbuild', 'jsw galvalume', 'jsw colour coated', 'jsw coated',
            'jsw gi', 'jsw hr', 'jsw cr', 'jsw tmt', 'jsw electrical steel',
            'jsw special steel', 'jsw plates', 'neosteel 550d', 'neosteel 600',
            'neosteel eds', 'neosteel crs', 'neosteel fastbuild', 'neostrands pc',
            'trusteel plates'
        ]
        
        for project in state['filtered_projects']:
            for retry in range(max_retries):
                try:
                    # Ensure project is a dictionary
                    if isinstance(project, str):
                        project = {
                            'title': project,
                            'description': project,
                            'value': 0,
                            'company': '',
                            'source_url': '',
                            'start_date': datetime.now(),
                            'end_date': datetime.now() + timedelta(days=365)
                        }
                    
                    # Calculate steel requirements with validation
                    enriched = email_handler._analyze_project_content(project)
                    
                    # Double check for JSW terms in enriched content
                    all_text = f"{enriched.get('title', '')} {enriched.get('description', '')} {str(enriched.get('steel_requirements', ''))}".lower()
                    if any(term in all_text for term in jsw_product_terms):
                        logger.info(f"Filtered JSW-related project during enrichment: {enriched.get('company')} - {enriched.get('title')}")
                        break
                    
                    # Validate steel requirements structure
                    steel_reqs = enriched.get('steel_requirements', {})
                    if not isinstance(steel_reqs, dict):
                        steel_reqs = {
                            'primary': {'type': 'TMT Bars', 'quantity': 0},
                            'secondary': [
                                {'type': 'Galvalume', 'quantity': 0},
                                {'type': 'Electrical Steel', 'quantity': 0}
                            ],
                            'tertiary': {'type': 'Wire Rods', 'quantity': 0}
                        }
                        enriched['steel_requirements'] = steel_reqs
                    
                    # Validate primary requirements
                    if not isinstance(steel_reqs.get('primary'), dict):
                        steel_reqs['primary'] = {'type': 'TMT Bars', 'quantity': 0}
                    
                    # Validate secondary requirements
                    if not isinstance(steel_reqs.get('secondary'), (dict, list)):
                        steel_reqs['secondary'] = [
                            {'type': 'Galvalume', 'quantity': 0},
                            {'type': 'Electrical Steel', 'quantity': 0}
                        ]
                    
                    # Generate catchy headline
                    original_title = enriched.get('title', '')
                    enriched['original_title'] = original_title
                    enriched['title'] = generate_catchy_headline(enriched)
                    
                    # Determine product teams with validation
                    teams = determine_product_teams(enriched)
                    if not teams:
                        teams = ['TMT_BARS']
                    enriched['teams'] = teams
                    
                    # Calculate priority score
                    priority_score = calculate_priority_score(enriched)
                    if priority_score < 0 or priority_score > 100:
                        priority_score = 50
                    enriched['priority_score'] = priority_score
                    
                    # Find procurement contacts
                    if enriched.get('company'):
                        logger.info(f"Finding procurement contacts for {enriched['company']}")
                        enriched = contact_finder.enrich_project_contacts(enriched)
                    
                    # Add to enriched projects
                    enriched_projects.append(enriched)
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    if retry == max_retries - 1:  # Last retry
                        logger.error(f"Error enriching project {project.get('title')} after {max_retries} retries: {str(e)}")
                    time.sleep(1)  # Wait before retry
                    continue
        
        if not enriched_projects:
            logger.warning("No projects were successfully enriched")
            
        logger.info(f"Successfully enriched {len(enriched_projects)} projects")
        state['enriched_projects'] = enriched_projects
        state['status'] = 'projects_enriched'
        return state
        
    except Exception as e:
        state['error'] = f"Error in project enrichment: {str(e)}"
        state['status'] = 'error'
        return state

def prioritize_projects(state: WorkflowState) -> WorkflowState:
    """Prioritize and sort projects."""
    try:
        logger.info(f"Prioritizing {len(state['enriched_projects'])} projects...")
        
        # Validate and normalize priority scores
        for project in state['enriched_projects']:
            try:
                score = project.get('priority_score', 0)
                if score < 0 or score > 100:
                    # Recalculate score if invalid
                    score = calculate_priority_score(project)
                project['priority_score'] = score
                
                # Add urgency tag based on timeline
                start_date = project.get('start_date', datetime.now())
                days_until_start = (start_date - datetime.now()).days
                
                if days_until_start <= 90:  # 3 months
                    project['tags'] = ['Urgent Priority']
                elif days_until_start <= 180:  # 6 months
                    project['tags'] = ['High Priority']
                else:
                    project['tags'] = ['Normal Priority']
                
                # Add value tag
                value = project.get('value', 0)
                if value >= 1000:
                    project['tags'].append('Major Project')
                elif value >= 500:
                    project['tags'].append('Large Project')
                
                # Add steel requirement tag
                steel_req = project.get('steel_requirements', {}).get('total', 0)
                if steel_req >= 10000:
                    project['tags'].append('High Steel Requirement')
                
            except Exception as e:
                logger.error(f"Error processing project tags: {str(e)}")
                project['tags'] = ['Normal Priority']
                continue
        
        # Sort projects by priority score
        prioritized_projects = sorted(
            state['enriched_projects'],
            key=lambda x: (
                x.get('priority_score', 0),
                x.get('value', 0),
                x.get('steel_requirements', {}).get('total', 0)
            ),
            reverse=True
        )
        
        # Limit to top projects but ensure minimum count
        min_projects = 3
        max_projects = 7
        if len(prioritized_projects) < min_projects:
            logger.warning(f"Only {len(prioritized_projects)} projects available after prioritization")
        
        state['prioritized_projects'] = prioritized_projects[:max_projects]
        state['status'] = 'projects_prioritized'
        return state
        
    except Exception as e:
        state['error'] = f"Error in project prioritization: {str(e)}"
        state['status'] = 'error'
        return state

def send_notifications(state: WorkflowState) -> WorkflowState:
    """Send notifications about discovered projects."""
    try:
        logger.info("Sending notifications...")
        
        if not state.get('prioritized_projects'):
            logger.warning("No projects to send notifications for")
            state['status'] = 'completed'
            return state
            
        # Initialize notification handlers
        email_handler = EmailHandler()
        whatsapp_handler = InteraktHandler()
        
        # Send email notifications
        email_success = email_handler.send_project_opportunities(state['prioritized_projects'])
        if not email_success:
            logger.error("Failed to send email notifications")
            
        # Send WhatsApp notifications
        whatsapp_success = whatsapp_handler.send_project_opportunities(state['prioritized_projects'])
        if not whatsapp_success:
            logger.error("Failed to send WhatsApp notifications")
            
        if email_success or whatsapp_success:
            state['status'] = 'completed'
        else:
            state['status'] = 'notification_failed'
            state['error'] = "Failed to send notifications"
            
        return state
        
    except Exception as e:
        logger.error(f"Error sending notifications: {str(e)}")
        state['error'] = f"Error in notifications: {str(e)}"
        state['status'] = 'error'
        return state

def create_workflow() -> Graph:
    workflow = StateGraph(WorkflowState)
    
    workflow.add_node("scrape_projects", scrape_projects)
    workflow.add_node("filter_projects", filter_projects)
    workflow.add_node("enrich_projects", enrich_projects)
    workflow.add_node("prioritize_projects", prioritize_projects)
    workflow.add_node("send_notifications", send_notifications)
    
    # Add edges
    workflow.add_edge("scrape_projects", "filter_projects")
    workflow.add_edge("filter_projects", "enrich_projects")
    workflow.add_edge("enrich_projects", "prioritize_projects")
    workflow.add_edge("prioritize_projects", "send_notifications")
    
    # Set entry point
    workflow.set_entry_point("scrape_projects")
    
    # Compile workflow
    return workflow.compile()

def run_workflow() -> dict:
    """Run the project discovery workflow."""
    try:
        # Initialize workflow
        workflow = create_workflow()
        
        # Initialize state with empty lists and status tracking
        initial_state = WorkflowState(
            projects=[],
            filtered_projects=[],
            enriched_projects=[],
            prioritized_projects=[],
            error=None,
            status='initialized'
        )
        
        # Track timing for monitoring
        start_time = datetime.now()
        
        # Run workflow with timing for each step
        final_state = workflow.invoke(initial_state)
        step_time = datetime.now() - start_time
        logger.info(f"Workflow completed in {step_time.total_seconds():.2f}s")
        
        # Log final statistics
        logger.info(f"Workflow completed with status: {final_state['status']}")
        logger.info(f"Projects found: {len(final_state.get('projects', []))}")
        logger.info(f"Projects filtered: {len(final_state.get('filtered_projects', []))}")
        logger.info(f"Projects enriched: {len(final_state.get('enriched_projects', []))}")
        logger.info(f"Projects prioritized: {len(final_state.get('prioritized_projects', []))}")
        
        return final_state
        
    except Exception as e:
        logger.error(f"Workflow error: {str(e)}")
        return {
            'error': str(e),
            'status': 'error',
            'projects': [],
            'filtered_projects': [],
            'enriched_projects': [],
            'prioritized_projects': []
        } 