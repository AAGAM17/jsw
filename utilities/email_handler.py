import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime, timedelta
from config.settings import Config
import re
import time
from .contact_enricher import ContactEnricher
from groq import Groq
import requests
import urllib.parse

class EmailHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Load email configuration
        self.smtp_server = Config.EMAIL_SMTP_SERVER
        self.smtp_port = Config.EMAIL_SMTP_PORT
        self.sender_email = Config.EMAIL_SENDER
        self.sender_password = Config.EMAIL_PASSWORD
        self.team_emails = Config.TEAM_EMAILS
        self.groq_client = Groq()
        self.contactout_token = Config.CONTACTOUT_TOKEN
        
        # Initialize contact enricher
        self.contact_enricher = ContactEnricher()
        
        # Validate email configuration
        if not all([self.smtp_server, self.smtp_port, self.sender_email, self.sender_password]):
            raise ValueError("Missing email configuration. Please check your .env file.")
            
        self.logger.info(f"Initialized EmailHandler with sender: {self.sender_email}")
        
        # Test SMTP connection on initialization
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.sender_email, self.sender_password)
                self.logger.info("SMTP connection test successful on initialization")
        except Exception as e:
            self.logger.error(f"Failed to initialize SMTP connection: {str(e)}")
            raise
        
    def determine_product_team(self, project):
        """Determine the most relevant product team based on project details"""
        try:
            # Handle string input
            if isinstance(project, str):
                text = project.lower()
            # Handle dictionary input
            elif isinstance(project, dict):
                title = project.get('title', '').lower()
                description = project.get('description', '').lower()
                text = f"{title} {description}"
            else:
                self.logger.error(f"Invalid project type: {type(project)}")
                return 'TMT_BARS'  # Default team
        
            # Check for specific keywords in order of priority
            if any(word in text for word in ['metro', 'railway', 'rail', 'train']):
                return 'HR_CR_PLATES'
            elif any(word in text for word in ['solar', 'renewable', 'pv']):
                return 'SOLAR'
            elif any(word in text for word in ['building', 'residential', 'commercial']):
                return 'TMT_BARS'
            elif any(word in text for word in ['industrial', 'factory', 'plant']):
                return 'HR_CR_PLATES'
            elif any(word in text for word in ['road', 'highway', 'bridge']):
                return 'TMT_BARS'
            
            return 'TMT_BARS'
        except Exception as e:
            self.logger.error(f"Error in determine_product_team: {str(e)}")
            return 'TMT_BARS'  # Default team in case of error
    
    def calculate_steel_requirement(self, project, product_type):
        """Calculate steel requirement based on project type and value"""
        try:
            # Handle string input
            if isinstance(project, str):
                text = project.lower()
                value_in_cr = 0  # Default value for string inputs
            # Handle dictionary input
            elif isinstance(project, dict):
                value_in_cr = project.get('value', 0)
                title = project.get('title', '').lower()
                description = project.get('description', '').lower()
                text = f"{title} {description}"
            else:
                self.logger.error(f"Invalid project type: {type(project)}")
                return 0

            rates = Config.STEEL_RATES.get(product_type, {})
            rate = rates.get('default', 10)  # Default rate if nothing else matches
            
            for category, category_rate in rates.items():
                if category != 'default' and category in text:
                    rate = category_rate
                    break
            
            steel_tons = value_in_cr * rate * 0.8  # Using 0.8 as conservative factor
            return steel_tons
        except Exception as e:
            self.logger.error(f"Error in calculate_steel_requirement: {str(e)}")
            return 0  # Return 0 in case of error
    
    def calculate_priority_score(self, project):
        """Calculate priority score based on contract value, timeline, and recency"""
        try:
            # Handle string input
            if isinstance(project, str):
                return 0  # String inputs get lowest priority
            
            # Handle dictionary input
            if not isinstance(project, dict):
                self.logger.error(f"Invalid project type: {type(project)}")
                return 0
            
            value_in_cr = project.get('value', 0)
            steel_tons = project.get('steel_requirement', 0)
            
            # Calculate months until project start
            start_date = project.get('start_date', datetime.now() + timedelta(days=730))  # Default 24 months
            if isinstance(start_date, str):
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d')
                except ValueError:
                    start_date = datetime.now() + timedelta(days=730)
            
            months_to_start = max(1, (start_date - datetime.now()).days / 30)
            
            # Calculate recency factor
            news_date = project.get('news_date', datetime.now())
            if isinstance(news_date, str):
                try:
                    news_date = datetime.strptime(news_date, '%Y-%m-%d')
                except ValueError:
                    news_date = datetime.now()
            
            months_old = (datetime.now() - news_date).days / 30
            
            if months_old < 1:  # Less than a month old
                recency_factor = 1.0
            elif months_old < 3:  # Less than 3 months old
                recency_factor = 0.8
            elif months_old < 6:  # Less than 6 months old
                recency_factor = 0.6
            else:
                recency_factor = 0.4
            
            # Value factor (normalized to 0-1 range)
            value_factor = min(value_in_cr / 1000, 1.0)  # Cap at 1000 crore
            
            # Steel requirement factor (normalized to 0-1 range)
            steel_factor = min(steel_tons / 10000, 1.0)  # Cap at 10000 MT
            
            # Timeline factor (higher score for projects starting sooner)
            timeline_factor = 1.0 / (1 + months_to_start/12)  # Decay over 12 months
            
            # Calculate priority score (0-1 range)
            priority_score = (
                0.3 * value_factor +
                0.3 * steel_factor +
                0.2 * timeline_factor +
                0.2 * recency_factor
            )
            
            return priority_score
            
        except Exception as e:
            self.logger.error(f"Error calculating priority score: {str(e)}")
            return 0
    
    def _analyze_project_content(self, project):
        """Analyze project content to extract better estimates and details using expert analysis"""
        try:
            # Input validation and conversion
            if isinstance(project, str):
                # If project is a string, create a basic project dict with the string as both title and description
                project_dict = {
                    'title': project,
                    'description': project,
                    'value': 0,
                    'company': '',
                    'source_url': '',
                    'news_date': datetime.now().strftime('%Y-%m-%d'),
                    'start_date': datetime.now(),
                    'end_date': datetime.now() + timedelta(days=365),
                    'steel_requirements': {
                        'primary': {'type': 'TMT Bars', 'quantity': 0, 'category': 'Long Products'},
                        'secondary': [
                            {'type': 'Hot Rolled', 'quantity': 0, 'category': 'Flat Products'},
                            {'type': 'Cold Rolled', 'quantity': 0, 'category': 'Flat Products'},
                            {'type': 'Galvanized', 'quantity': 0, 'category': 'Flat Products'}
                        ],
                        'tertiary': {'type': 'Wire Rods', 'quantity': 0, 'category': 'Long Products'}
                    },
                    'project_type': 'infrastructure',
                    'specifications': {
                        'length': None,
                        'area': None,
                        'capacity': None,
                        'floors': None
                    },
                    'teams': ['TMT_BARS']
                }
            elif isinstance(project, dict):
                # If it's already a dict, make a copy and ensure all required fields exist
                project_dict = project.copy()
                project_dict.setdefault('title', '')
                project_dict.setdefault('description', '')
                project_dict.setdefault('value', 0)
                project_dict.setdefault('company', '')
                project_dict.setdefault('source_url', '')
                project_dict.setdefault('news_date', datetime.now().strftime('%Y-%m-%d'))
                project_dict.setdefault('start_date', datetime.now())
                project_dict.setdefault('end_date', datetime.now() + timedelta(days=365))
                project_dict.setdefault('steel_requirements', {
                    'primary': {'type': 'TMT Bars', 'quantity': 0, 'category': 'Long Products'},
                    'secondary': [
                        {'type': 'Hot Rolled', 'quantity': 0, 'category': 'Flat Products'},
                        {'type': 'Cold Rolled', 'quantity': 0, 'category': 'Flat Products'},
                        {'type': 'Galvanized', 'quantity': 0, 'category': 'Flat Products'}
                    ],
                    'tertiary': {'type': 'Wire Rods', 'quantity': 0, 'category': 'Long Products'}
                })
                project_dict.setdefault('project_type', 'infrastructure')
                project_dict.setdefault('specifications', {
                    'length': None,
                    'area': None,
                    'capacity': None,
                    'floors': None
                })
                project_dict.setdefault('teams', ['TMT_BARS'])
            else:
                raise ValueError(f"Project must be a string or dictionary, got {type(project)}")

            # Prepare project information for analysis
            title = str(project_dict.get('title', '')).lower()
            description = str(project_dict.get('description', '')).lower()
            text = f"{title} {description}"
            
            # Determine project type and teams
            if any(term in text for term in ['metro', 'railway', 'rail', 'train']):
                project_dict['project_type'] = 'metro_rail'
                project_dict['teams'] = ['HOT_ROLLED', 'TMT_BARS', 'ELECTRICAL_STEEL']
            elif any(term in text for term in ['highway', 'road', 'bridge', 'flyover', 'viaduct']):
                project_dict['project_type'] = 'highway_bridge'
                project_dict['teams'] = ['TMT_BARS', 'WIRE_RODS']
            elif any(term in text for term in ['residential', 'housing', 'apartment', 'building', 'tower']):
                project_dict['project_type'] = 'realty'
                project_dict['teams'] = ['TMT_BARS', 'GALVALUME']
            elif any(term in text for term in ['industrial', 'factory', 'plant', 'warehouse', 'manufacturing']):
                project_dict['project_type'] = 'industrial'
                project_dict['teams'] = ['HOT_ROLLED', 'COLD_ROLLED', 'GALVANIZED']
            elif any(term in text for term in ['solar', 'power plant', 'renewable', 'energy']):
                project_dict['project_type'] = 'energy'
                project_dict['teams'] = ['GALVALUME', 'ELECTRICAL_STEEL']
            else:
                project_dict['project_type'] = 'infrastructure'
                project_dict['teams'] = ['TMT_BARS']  # Default team
            
            # Extract numerical specifications
            specs = project_dict['specifications']
            
            # Length extraction (km, meters)
            length_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:km|kilometer|meter)', description)
            if length_match:
                specs['length'] = float(length_match.group(1))
            
            # Area extraction (sq ft, sq m)
            area_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:sq ft|sqft|square feet|sq m|sqm)', description)
            if area_match:
                specs['area'] = float(area_match.group(1))
            
            # Capacity extraction (MW, KW)
            capacity_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mw|kw|megawatt|kilowatt)', description)
            if capacity_match:
                specs['capacity'] = float(capacity_match.group(1))
            
            # Floor count extraction
            floor_match = re.search(r'(\d+)(?:\s*-?\s*(?:floor|storey|story))', description)
            if floor_match:
                specs['floors'] = int(floor_match.group(1))
            
            # Calculate steel requirements based on project type and value
            value_in_cr = float(project_dict.get('value', 0))
            steel_reqs = project_dict['steel_requirements']
            
            if project_dict['project_type'] == 'metro_rail':
                steel_reqs['primary'] = {
                    'type': 'TMT Bars',
                    'quantity': round(specs['length'] * 175 if specs['length'] else value_in_cr * 35, -2),
                    'category': 'Long Products'
                }
                steel_reqs['secondary'] = [
                    {
                        'type': 'Hot Rolled',
                        'quantity': round((specs['length'] * 50 if specs['length'] else value_in_cr * 10), -2),
                        'category': 'Flat Products'
                    },
                    {
                        'type': 'Electrical Steel',
                        'quantity': round((specs['length'] * 30 if specs['length'] else value_in_cr * 8), -2),
                        'category': 'Flat Products'
                    },
                    {
                        'type': 'Galvalume Steel',
                        'quantity': round((specs['length'] * 25 if specs['length'] else value_in_cr * 6), -2),
                        'category': 'Flat Products'
                    }
                ]
                steel_reqs['tertiary'] = {
                    'type': 'Special Alloy Steel',
                    'quantity': round((specs['length'] * 25 if specs['length'] else value_in_cr * 5), -2),
                    'category': 'Long Products'
                }
            elif project_dict['project_type'] == 'highway_bridge':
                steel_reqs['primary'] = {
                    'type': 'TMT Bars',
                    'quantity': round(specs['length'] * 125 if specs['length'] else value_in_cr * 30, -2)
                }
                steel_reqs['secondary'] = [
                    {
                        'type': 'Galvalume',
                        'quantity': round((specs['length'] * 40 if specs['length'] else value_in_cr * 8), -2)
                    },
                    {
                        'type': 'Electrical Steel',
                        'quantity': round((specs['length'] * 20 if specs['length'] else value_in_cr * 5), -2)
                    }
                ]
                steel_reqs['tertiary'] = {
                    'type': 'Wire Rods',
                    'quantity': round((specs['length'] * 15 if specs['length'] else value_in_cr * 4), -2)
                }
            elif project_dict['project_type'] == 'realty':
                steel_reqs['primary'] = {
                    'type': 'TMT Bars',
                    'quantity': round(specs['floors'] * 45 if specs['floors'] else value_in_cr * 25, -2)
                }
                steel_reqs['secondary'] = [
                    {
                        'type': 'Galvalume',
                        'quantity': round(specs['area'] * 0.15 if specs['area'] else value_in_cr * 6, -2)
                    },
                    {
                        'type': 'Electrical Steel',
                        'quantity': round(specs['area'] * 0.1 if specs['area'] else value_in_cr * 4, -2)
                    }
                ]
                steel_reqs['tertiary'] = {
                    'type': 'Wire Rods',
                    'quantity': round(specs['area'] * 0.05 if specs['area'] else value_in_cr * 3, -2)
                }
            elif project_dict['project_type'] == 'industrial':
                steel_reqs['primary'] = {
                    'type': 'TMT Bars',
                    'quantity': round(specs['area'] * 0.2 if specs['area'] else value_in_cr * 20, -2)
                }
                steel_reqs['secondary'] = [
                    {
                        'type': 'Galvalume',
                        'quantity': round(specs['area'] * 0.1 if specs['area'] else value_in_cr * 8, -2)
                    },
                    {
                        'type': 'Electrical Steel',
                        'quantity': round(specs['area'] * 0.08 if specs['area'] else value_in_cr * 6, -2)
                    }
                ]
                steel_reqs['tertiary'] = {
                    'type': 'Wire Rods',
                    'quantity': round(specs['area'] * 0.05 if specs['area'] else value_in_cr * 4, -2)
                }
            elif project_dict['project_type'] == 'energy':
                steel_reqs['primary'] = {
                    'type': 'TMT Bars',
                    'quantity': round(specs['capacity'] * 35 if specs['capacity'] else value_in_cr * 15, -2)
                }
                steel_reqs['secondary'] = [
                    {
                        'type': 'Galvalume',
                        'quantity': round(specs['capacity'] * 20 if specs['capacity'] else value_in_cr * 8, -2)
                    },
                    {
                        'type': 'Electrical Steel',
                        'quantity': round(specs['capacity'] * 15 if specs['capacity'] else value_in_cr * 6, -2)
                    }
                ]
                steel_reqs['tertiary'] = {
                    'type': 'Wire Rods',
                    'quantity': round(specs['capacity'] * 10 if specs['capacity'] else value_in_cr * 4, -2)
                }
            
            # Ensure minimum quantities
            min_quantity = 100
            if steel_reqs['primary']['quantity'] < min_quantity:
                steel_reqs['primary']['quantity'] = min_quantity
            for sec_req in steel_reqs['secondary']:
                if sec_req['quantity'] < min_quantity:
                    sec_req['quantity'] = min_quantity
            if steel_reqs['tertiary']['quantity'] < min_quantity:
                steel_reqs['tertiary']['quantity'] = min_quantity
            
            # Format the requirements string
            steel_reqs_str = f"Estimated requirement:\n"
            steel_reqs_str += f"{steel_reqs['primary']['type']} (~{steel_reqs['primary']['quantity']:,}MT) - Primary\n"
            for sec_req in steel_reqs['secondary']:
                steel_reqs_str += f"{sec_req['type']} - Secondary\n"
            steel_reqs_str += f"{steel_reqs['tertiary']['type']} - Tertiary"
            
            project_dict['steel_requirements_display'] = steel_reqs_str
            
            return project_dict
            
        except Exception as e:
            self.logger.error(f"Error analyzing project: {str(e)}")
            # Return a basic project structure even if analysis fails
            return {
                'title': str(project) if isinstance(project, str) else '',
                'description': str(project) if isinstance(project, str) else '',
                'value': 0,
                'company': '',
                'source_url': '',
                'news_date': datetime.now().strftime('%Y-%m-%d'),
                'start_date': datetime.now(),
                'end_date': datetime.now() + timedelta(days=365),
                'steel_requirements': {
                    'primary': {'type': 'TMT Bars', 'quantity': 100},
                    'secondary': {'type': 'HR Plates', 'quantity': 100}
                },
                'project_type': 'infrastructure',
                'specifications': {'length': None, 'area': None, 'capacity': None, 'floors': None},
                'teams': ['TMT_BARS']
            }
    
    def _prioritize_projects(self, projects):
        """Prioritize projects based on multiple factors"""
        try:
            # Convert any string projects to dictionaries first
            processed_projects = []
            for project in projects:
                if isinstance(project, str):
                    processed_projects.append({
                        'title': project,
                        'description': project,
                        'value': 0,
                        'company': '',
                        'source_url': '',
                        'news_date': datetime.now().strftime('%Y-%m-%d'),
                        'start_date': datetime.now(),
                        'end_date': datetime.now() + timedelta(days=365),
                        'source': 'perplexity'
                    })
                else:
                    processed_projects.append(project)

            # Calculate initial priority scores
            for project in processed_projects:
                # Calculate base priority score without Groq
                value = project.get('value', 0)
                source_boost = 1.2 if project.get('source') == 'exa_web' else 1.0
                size_boost = 1.3 if value < 100 else (1.1 if value < 500 else 1.0)
                
                # Basic priority calculation
                base_score = (value / 1000) * source_boost * size_boost
                project['initial_priority'] = base_score
            
            # Sort by initial priority and take top 7 projects
            pre_sorted = sorted(processed_projects, key=lambda x: x.get('initial_priority', 0), reverse=True)[:7]
            
            # Now use Groq for detailed analysis of limited set
            analyzed_projects = []
            for project in pre_sorted:
                try:
                    # Add delay between Groq calls to avoid rate limits
                    time.sleep(2)
                    
                    # Analyze with Groq
                    analyzed = self._analyze_project_content(project)
                    if analyzed:
                        # Calculate final priority score
                        priority_score = self.calculate_priority_score(analyzed)
                        analyzed['final_priority_score'] = priority_score
                        analyzed_projects.append(analyzed)
                        
                except Exception as e:
                    self.logger.error(f"Error analyzing project with Groq: {str(e)}")
                    # Still include project but with original data
                    project['final_priority_score'] = project.get('initial_priority', 0)
                    analyzed_projects.append(project)
            
            # Final sort and limit to top 5
            final_projects = sorted(analyzed_projects, key=lambda x: x.get('final_priority_score', 0), reverse=True)[:5]
            
            return final_projects
            
        except Exception as e:
            self.logger.error(f"Error prioritizing projects: {str(e)}")
            # Fallback to simple prioritization if something goes wrong
            return sorted(projects, key=lambda x: x.get('value', 0) if isinstance(x, dict) else 0, reverse=True)[:5]
    
    def _search_linkedin_contacts(self, company_name):
        """Search for contacts using ContactOut APIs with improved search strategy"""
        try:
            self.logger.info(f"Starting ContactOut search for company: {company_name}")
            contacts = []
            
            # Setup ContactOut API headers
            search_headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.contactout_token}'
            }
            
            # Clean company name
            company_name = company_name.lower().strip()
            
            # Remove problematic parts from company name
            company_parts = company_name.split()
            filtered_parts = [part for part in company_parts if part not in {
                'limited', 'ltd', 'pvt', 'private', 'jv', 'india', 'infra', 
                'infrastructure', 'construction', 'and', '&', 'projects', 
                'project', 'engineering', 'services', 'under', 'tracking', 
                'platform'
            }]
            
            # Get the main company name (first 2-3 words)
            main_company = ' '.join(filtered_parts[:3])
            self.logger.info(f"Using main company name: {main_company}")
            
            # 1. Try exact company search first
            search_params = {
                'query': f'company:"{main_company}"',
                'type': 'profile',
                'limit': 25
            }
            
            response = requests.get(
                'https://api.contactout.com/v2/search',
                headers=search_headers,
                params=search_params
            )
            
            if response.status_code == 200:
                profiles = response.json().get('profiles', [])
                if profiles:
                    self.logger.info(f"Found {len(profiles)} profiles via exact company search")
                    self._process_contact_profiles(profiles, contacts, search_headers)
            
            # 2. If no results, try keyword search
            if len(contacts) < 3:
                search_params = {
                    'query': f'"{main_company}"',
                    'type': 'profile',
                    'limit': 25
                }
                
                response = requests.get(
                    'https://api.contactout.com/v2/search',
                    headers=search_headers,
                    params=search_params
                )
                
                if response.status_code == 200:
                    profiles = response.json().get('profiles', [])
                    if profiles:
                        self.logger.info(f"Found {len(profiles)} profiles via keyword search")
                        self._process_contact_profiles(profiles, contacts, search_headers)
            
            # 3. Try role-based search if still needed
            if len(contacts) < 3:
                role_queries = [
                    'procurement manager',
                    'project manager',
                    'site engineer',
                    'director',
                    'managing director',
                    'general manager',
                    'head',
                    'ceo',
                    'vp'
                ]
                
                for role in role_queries:
                    if len(contacts) >= 5:
                        break
                        
                    search_params = {
                        'query': f'company:"{main_company}" AND title:"{role}"',
                        'type': 'profile',
                        'limit': 10
                    }
                    
                    response = requests.get(
                        'https://api.contactout.com/v2/search',
                        headers=search_headers,
                        params=search_params
                    )
                    
                    if response.status_code == 200:
                        profiles = response.json().get('profiles', [])
                        if profiles:
                            self.logger.info(f"Found {len(profiles)} profiles via role search for {role}")
                            self._process_contact_profiles(profiles, contacts, search_headers)
            
            # 4. Try location-based search as last resort
            if len(contacts) < 2:
                locations = ['mumbai', 'delhi', 'bangalore', 'hyderabad', 'chennai']
                for location in locations:
                    if len(contacts) >= 3:
                        break
                        
                    search_params = {
                        'query': f'"{main_company}" AND location:"{location}"',
                        'type': 'profile',
                        'limit': 10
                    }
                    
                    response = requests.get(
                        'https://api.contactout.com/v2/search',
                        headers=search_headers,
                        params=search_params
                    )
                    
                    if response.status_code == 200:
                        profiles = response.json().get('profiles', [])
                        if profiles:
                            self.logger.info(f"Found {len(profiles)} profiles via location search for {location}")
                            self._process_contact_profiles(profiles, contacts, search_headers)
            
            # Process found contacts
            unique_contacts = []
            seen_urls = set()
            
            for contact in contacts:
                url = contact.get('profile_url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    # Verify contact has required fields
                    if contact.get('name') and (contact.get('role') or contact.get('title')):
                        unique_contacts.append(contact)
            
            self.logger.info(f"Total unique contacts found for {company_name}: {len(unique_contacts)}")
            return unique_contacts
            
        except Exception as e:
            self.logger.error(f"Contact search failed for {company_name}: {str(e)}")
            return []

    def _get_company_name_variations(self, company_name):
        """Generate variations of company name for better search results"""
        variations = set()
        
        # Original name
        variations.add(company_name)
        
        # Clean the company name
        clean_name = company_name.lower()
        clean_name = re.sub(r'[^\w\s-]', ' ', clean_name)
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        variations.add(clean_name)
        
        # Remove common suffixes
        suffixes = [' limited', ' ltd', ' pvt', ' private', ' jv', ' india', ' infra', ' infrastructure', ' construction']
        base_name = clean_name
        for suffix in suffixes:
            if base_name.endswith(suffix):
                base_name = base_name[:-len(suffix)].strip()
                variations.add(base_name)
        
        # Handle hyphenated names
        if '-' in base_name:
            parts = base_name.split('-')
            variations.add(parts[0].strip())
            variations.add(parts[-1].strip())
        
        # Handle spaces
        if ' ' in base_name:
            parts = base_name.split()
            if len(parts) > 2:
                variations.add(parts[0])
                variations.add(' '.join(parts[:2]))
        
        return list(variations)

    def _process_contact_profiles(self, profiles, contacts, headers):
        """Process profiles from ContactOut enrichment"""
        if not profiles or not isinstance(profiles, list):
            self.logger.error("Invalid profiles data: expected non-empty list")
            return
        
        for profile in profiles:
            if not isinstance(profile, dict):
                self.logger.warning(f"Skipping invalid profile format: {type(profile)}")
                continue
            
            try:
                # Get static CRM data
                contact = {
                    'name': profile.get('full_name', ''),
                    'role': profile.get('current_position', {}).get('title', ''),
                    'company': profile.get('current_position', {}).get('company', ''),
                    'location': profile.get('location', ''),
                    'profile_url': profile.get('linkedin_url', ''),
                    'source': 'CRM'
                }
                
                if contact.get('name') and contact.get('role'):
                    if not any(c.get('profile_url') == contact['profile_url'] for c in contacts):
                        contacts.append(contact)
                        self.logger.info(f"Added contact: {contact['name']} ({contact['role']})")
            
            except Exception as e:
                self.logger.error(f"Error processing profile: {str(e)}")
                continue
    
    def _process_profiles(self, profiles, contacts, headers, company_name):
        """Process profiles from ContactOut API"""
        for profile in profiles:
            try:
                if profile.get('linkedin_url'):
                    detail_response = requests.get(
                        'https://api.contactout.com/v2/profile',
                        headers=headers,
                        params={'profile_url': profile['linkedin_url']}
                    )

                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        contact = {
                            'name': detail_data.get('full_name', profile.get('full_name', '')),
                            'role': detail_data.get('current_position', {}).get('title', profile.get('current_position', {}).get('title', '')),
                            'company': detail_data.get('current_position', {}).get('company', profile.get('current_position', {}).get('company', '')),
                            'location': detail_data.get('location', profile.get('location', '')),
                            'profile_url': profile.get('linkedin_url', ''),
                            'source': 'ContactOut'
                        }
                    else:
                        contact = {
                            'name': profile.get('full_name', ''),
                            'role': profile.get('current_position', {}).get('title', ''),
                            'company': profile.get('current_position', {}).get('company', ''),
                            'location': profile.get('location', ''),
                            'profile_url': profile.get('linkedin_url', ''),
                            'source': 'ContactOut'
                        }
                    
                    if contact.get('name') and contact.get('role'):
                        if not any(c.get('profile_url') == contact['profile_url'] for c in contacts):
                            contacts.append(contact)
                            self.logger.info(f"Added contact: {contact['name']} ({contact['role']})")
            
            except Exception as e:
                self.logger.error(f"Error processing profile: {str(e)}")
                continue
    
    def _process_linkedin_profiles(self, profiles, contacts, headers, company_name):
        """Process profiles from LinkedIn scraping using ContactOut enrichment"""
        if not profiles or not isinstance(profiles, list):
            self.logger.error("Invalid profiles data: expected non-empty list")
            return

        for profile in profiles:
            if not isinstance(profile, dict):
                self.logger.warning(f"Skipping invalid profile format: {type(profile)}")
                continue
            
            try:
                profile_url = profile.get('profile_url')
                if not profile_url:
                    continue

                current_position = profile.get('current_position', {})
                if not isinstance(current_position, dict):
                    current_position = {}
                
                contact = {
                    'name': profile.get('full_name', ''),
                    'role': current_position.get('title', profile.get('title', '')),
                    'company': current_position.get('company', company_name),
                    'email': '',  # Only use CRM data
                    'phone': '',  # Only use CRM data
                    'location': profile.get('location', ''),
                    'profile_url': profile_url,
                    'source': 'CRM'
                }
                
                if contact.get('name') and contact.get('role'):
                    if not any(c.get('profile_url') == contact['profile_url'] for c in contacts):
                        contacts.append(contact)
                        self.logger.info(f"Added contact: {contact['name']} ({contact['role']}) via {contact.get('source', 'Unknown')}")

            except Exception as e:
                self.logger.error(f"Error processing LinkedIn profile: {str(e)}")
                continue

    def _format_project_for_email(self, project):
        """Format a single project for HTML email."""
        try:
            # Ensure project has steel requirements
            if not project.get('steel_requirements'):
                project = self._analyze_project_content(project)
            
            # Get priority class and color
            priority_tag = next((tag for tag in project.get('tags', []) if 'Priority' in tag), 'Normal Priority')
            is_high_priority = 'High' in priority_tag
            priority_color = '#dc3545' if is_high_priority else '#2e7d32'
            priority_bg = '#fde8e8' if is_high_priority else '#e8f5e9'
            priority_tag = 'High Priority' if is_high_priority else 'Normal Priority'
            
            # Get CRM data
            company_name = project.get('company', '').lower()
            crm_data = self.contact_enricher.crm_data.get(company_name, {})
            
            # Get contacts from CRM only
            contacts = crm_data.get('contacts', [])
            relationship_data = crm_data.get('projects', {})
            
            # Generate relationship HTML based on CRM data
            if relationship_data:
                relationship_html = f'''
                    <div class="mb-2">
                        <strong style="color: #1a1a1a;">Current Project:</strong> {relationship_data.get('current', 'No current project')}
                    </div>
                    <div class="mb-2">
                        <strong style="color: #1a1a1a;">Volume:</strong> {relationship_data.get('volume', 'N/A')}
                    </div>
                    <div class="mb-2">
                        <strong style="color: #1a1a1a;">Materials:</strong> {relationship_data.get('materials', 'N/A')}
                    </div>
                    <div>
                        <strong style="color: #1a1a1a;">Notes:</strong> {relationship_data.get('notes', 'No additional notes')}
                    </div>
                '''
            else:
                relationship_html = f'''
                    <div>
                        <strong style="color: #1a1a1a;">No existing relationship found</strong>
                        <div style="margin-top: 10px;">
                            <button onclick="this.innerHTML='Done'; this.style.background='#28a745'; this.style.color='white'; this.disabled=true;" 
                               style="display: inline-block; background: #e9ecef; color: #495057; padding: 8px 15px; 
                                      text-decoration: none; border-radius: 4px; font-size: 14px; border: none; cursor: pointer;">
                                Update Relationship
                            </button>
                        </div>
                    </div>
                '''
            
            # Generate contacts HTML
            contacts_html = ''
            if contacts:
                contacts_html = '<div style="margin-top: 20px; border-top: 1px solid #eee; padding-top: 15px;">'
                contacts_html += '<h4 style="color: #1a1a1a; margin: 0 0 15px 0;">Key Contacts</h4>'
                
            for contact in contacts:
                name = contact.get('name', 'N/A')
                role = contact.get('role', 'N/A')
                email = contact.get('email', '')
                phone = contact.get('phone', '')
                location = contact.get('location', '')
                company = project.get('company', contact.get('company', ''))
                
                # Only show contact if we have at least a name or role
                if name != 'N/A' or role != 'N/A':
                    contacts_html += f'''
                        <div style="background: #f8f9fa; border-radius: 8px; padding: 15px; margin-bottom: 15px;">
                            <div style="display: flex; justify-content: space-between; align-items: start;">
                                <div>
                                    <p style="margin: 0; color: #202124; font-size: 16px; font-weight: 500;">
                                        {name}
                                    </p>
                                    <p style="margin: 4px 0; color: #5f6368; font-size: 14px;">
                                        {role} at {company}
                                    </p>
                                </div>
                            </div>
                            <div style="margin-top: 10px; font-size: 14px; color: #5f6368;">
                                {f'<p style="margin: 4px 0;"><strong>Email:</strong> <a href="mailto:{email}" style="color: #1a73e8; text-decoration: none;">{email}</a></p>' if email else ''}
                                {f'<p style="margin: 4px 0;"><strong>Phone:</strong> {phone}</p>' if phone else ''}
                                {f'<p style="margin: 4px 0;"><strong>Location:</strong> {location}</p>' if location else ''}
                            </div>
                        </div>
                    '''
            else:
                contacts_html = '''
                    <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 8px;">
                        <p style="margin: 0; color: #5f6368;">No contacts found in CRM.</p>
                    </div>
                '''
            
            # Create HTML for single project
            html = f'''
            <div style="border-left: 4px solid {priority_color}; border-radius: 8px; border: 1px solid #e0e0e0; margin: 20px 0; padding: 20px;">
                <div style="margin-bottom: 15px;">
                    <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 14px; background: {priority_bg}; color: {priority_color};">
                        {priority_tag}
                    </span>
                </div>
                
                <h4 style="color: #424242; font-size: 20px; margin: 0 0 20px 0;">{project.get('title', '')}</h4>
                
                {self._format_project_details(project)}
                
                <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 15px 0; font-size: 16px; color: #1a1a1a;">
                    {relationship_html}
                </div>
                
                <div style="margin-bottom: 20px;">
                    {contacts_html}
                </div>
                
                <div style="margin-top: 20px;">
                    <a href="{project.get('source_url', '#')}" style="display: inline-block; background: #1a73e8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-right: 10px;">
                        View Announcement
                    </a>
                    <a href="https://jsww.onrender.com/project-details?title={urllib.parse.quote(project.get('title', ''))}&company={urllib.parse.quote(project.get('company', ''))}&value={project.get('value', 0)}&description={urllib.parse.quote(project.get('description', ''))}&source_url={urllib.parse.quote(project.get('source_url', ''))}" 
                       style="display: inline-block; background: #f8f9fa; color: #1a73e8; padding: 10px 20px; text-decoration: none; border-radius: 4px; border: 1px solid #1a73e8;">
                        Get More Info
                    </a>
                </div>
            </div>
            '''
            
            return html
            
        except Exception as e:
            self.logger.error(f"Error formatting project: {str(e)}")
            return f'''
            <div style="margin: 20px 0; padding: 20px; border: 1px solid #dc3545; border-radius: 8px;">
                Error formatting project details
            </div>
            '''

    def _format_project_details(self, project):
        """Format the project details for email."""
        # Get steel requirements with proper structure
        steel_reqs = project.get('steel_requirements', {})
        
        # Format primary requirement (Long Products)
        primary_req = steel_reqs.get('primary', {})
        primary_html = f'''
            <div style="font-size: 16px; margin-bottom: 12px;">
                <strong style="color: #1a1a1a;">Primary ({primary_req.get('category', 'Long Products')}):</strong> 
                {primary_req.get('type', 'TMT Bars')} (~{primary_req.get('quantity', 0):,}MT)
            </div>
        '''
        
        # Format secondary requirements (Flat Products)
        secondary_reqs = steel_reqs.get('secondary', [])
        secondary_html = '<div style="margin-left: 20px;">'
        for req in secondary_reqs:
            if req.get('quantity', 0) > 0:
                secondary_html += f'''
                    <div style="font-size: 16px; margin-bottom: 8px;">
                        <strong style="color: #1a1a1a;">Secondary ({req.get('category', 'Flat Products')}):</strong> 
                        {req.get('type', '')} (~{req.get('quantity', 0):,}MT)
                    </div>
                '''
        secondary_html += '</div>'
        
        # Format tertiary requirement (Long Products)
        tertiary_req = steel_reqs.get('tertiary', {})
        tertiary_html = f'''
            <div style="font-size: 16px; margin-bottom: 12px;">
                <strong style="color: #1a1a1a;">Tertiary ({tertiary_req.get('category', 'Long Products')}):</strong> 
                {tertiary_req.get('type', 'Special Alloy Steel')} (~{tertiary_req.get('quantity', 0):,}MT)
            </div>
        '''
        
        # Format timeline
        timeline_html = f'''
            <div style="font-size: 16px; margin-bottom: 12px;">
                <strong style="color: #1a1a1a;">Work Begins:</strong> 
                {project.get('start_date', datetime.now()).strftime('%B %Y')} - 
                {project.get('end_date', datetime.now() + timedelta(days=365)).strftime('%B %Y')}
            </div>
        '''
        
        return f'''
            <div style="margin-bottom: 20px;">
                <div style="font-weight: bold; color: #1a1a1a; margin-bottom: 10px;">Estimated Requirements:</div>
                {primary_html}
                {secondary_html}
                {tertiary_html}
                {timeline_html}
            </div>
            '''

    def _get_team_emails(self, teams): 
        """Get email addresses for teams"""
        try:
            if isinstance(teams, list) and all(isinstance(t, str) for t in teams):
                return [self.team_emails.get(team) for team in teams if team in self.team_emails]
            
            if isinstance(teams, str):
                return [self.team_emails.get(teams)] if teams in self.team_emails else []
            
            if isinstance(teams, dict):
                team_list = []
                if teams.get('primary') in self.team_emails:
                    team_list.append(self.team_emails[teams['primary']])
                if teams.get('secondary') in self.team_emails:
                    team_list.append(self.team_emails[teams['secondary']])
                return team_list
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting team emails: {str(e)}")
            return []
    
    def send_project_opportunities(self, projects):
        """Send project opportunities to respective teams"""
        try:
            team_projects = {}
            
            for project in projects:
                try:
                    if not project.get('steel_requirements'):
                        project = self._analyze_project_content(project)
                    
                    teams = project.get('teams', ['TMT_BARS'])
                    team_emails = self._get_team_emails(teams)
                    
                    if not team_emails:
                        self.logger.warning(f"No team emails found for project: {project.get('title')}")
                        continue
                    
                    for email in team_emails:
                        if email not in team_projects:
                            team_projects[email] = []
                        team_projects[email].append(project)
                    
                except Exception as e:
                    self.logger.error(f"Error processing project {project.get('title')}: {str(e)}")
                    continue
            
            for email, team_project_list in team_projects.items():
                try:
                    msg = MIMEMultipart('alternative')
                    msg['From'] = self.sender_email
                    msg['To'] = email
                    msg['Subject'] = "JSW Steel Project Leads"
                    
                    html_content = f'''
                    <html>
                    <head>
                        <style>
                            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                            .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                            h1 {{ color: #202124; margin-bottom: 30px; font-size: 28px; }}
                            h3 {{ color: #424242; font-size: 22px; margin: 0 0 8px 0; }}
                            h4 {{ color: #424242; font-size: 20px; margin: 0 0 20px 0; }}
                            .project {{ margin: 20px 0; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; }}
                            .tag {{ padding: 2px 8px; border-radius: 4px; font-size: 14px; margin-right: 8px; }}
                            .requirements {{ font-size: 16px; margin-bottom: 12px; }}
                            .contact-info {{ font-size: 15px; }}
                            .relationship-note {{ background: #f8f9fa; padding: 15px; border-radius: 6px; margin: 15px 0; font-size: 16px; color: #1a1a1a; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>Leads for the {team_project_list[0]['teams'][0].replace('_', ' ')} team</h1>
                            {''.join(self._format_project_for_email(project) for project in team_project_list)}
                            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 14px;">
                                <p>This is an automated notification from the JSW Steel Project Discovery System.</p>
                                <p>For any questions or support, please contact the sales team.</p>
                            </div>
                        </div>
                    </body>
                    </html>
                    '''
                    
                    msg.attach(MIMEText(html_content, 'html'))
                    
                    with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                        server.starttls()
                        server.login(self.sender_email, self.sender_password)
                        server.send_message(msg)
                    
                    self.logger.info(f"Successfully sent email to {email}")
                except Exception as e:
                    self.logger.error(f"Error sending email to {email}: {str(e)}")
                    continue
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error in send_project_opportunities: {str(e)}")
            return False

    def send_project_opportunity(self, project, recipient_email):
        """Send a single project opportunity via email"""
        try:
            subject = f"JSW Steel Leads"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #202124; margin-top: 0;">{{project('company')}}</h3>
                        <h4 style="color: #202124;">{{project('title')}}</h4>
                        
                        <p><strong>Timeline:</strong><br>
                        Start: {{project.get('start_date', datetime.now()).strftime('%B %Y')}}<br>
                        End: {{project.get('end_date', datetime.now()).strftime('%B %Y')}}</p>
                        
                        <p><strong>Contract Value:</strong> Rs. {{project.get('value', 0):,.0f}} Cr</p>
                        
                        <p><strong>Estimated Steel Requirement:</strong> {{project.get('steel_requirement', 0):,.0f}} MT</p>
                        
                        <p><strong>Source:</strong> <a href="{{project.get('source_url', '#')}}" style="color: #1a73e8;">View Announcement</a></p>
                    </div>
                    
                    <div style="margin-top: 20px; font-size: 12px; color: #666;">
                        <p>This is an automated message from JSW Steel Project Bot. Please do not reply directly to this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            msg.attach(MIMEText(html_content, 'html'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
                
            self.logger.info(f"Successfully sent project opportunity email to {{recipient_email}}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email: {{str(e)}}")
            return False
            
    def send_project_summary(self, projects, recipient_email):
        """Send a summary of multiple project opportunities"""
        try:
            subject = f"JSW Steel Leads"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #28a745;">New Project Opportunities Summary</h2>
                    
                    <p>We found {{len(projects)}} new project opportunities that might interest you:</p>
            """
            
            for idx, project in enumerate(projects, 1):
                html_content += f"""
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #202124; margin-top: 0;">#{idx}: {{project('company')}}</h3>
                        <h4 style="color: #202124;">{{project('title')}}</h4>
                        
                        <p><strong>Timeline:</strong><br>
                        Start: {{project.get('start_date', datetime.now()).strftime('%B %Y')}}<br>
                        End: {{project.get('end_date', datetime.now()).strftime('%B %Y')}}</p>
                        
                        <p><strong>Contract Value:</strong> Rs. {{project.get('value', 0):,.0f}} Cr</p>
                        <p><strong>Estimated Steel Requirement:</strong> {{project.get('steel_requirement', 0):,.0f}} MT</p>
                        
                        <p><a href="{{project.get('source_url', '#')}}" style="color: #1a73e8;">View Announcement</a></p>
                    </div>
                """
            
            # Add footer
            html_content += """
                    <div style="background-color: #e8f0fe; padding: 15px; border-radius: 5px;">
                        <h4 style="color: #1a73e8; margin-top: 0;">Need more information?</h4>
                        <ul style="list-style-type: none; padding-left: 0;">
                            <li>• Reply to this email for specific project details</li>
                            <li>• Contact your JSW representative for assistance</li>
                        </ul>
                    </div>
                    
                    <div style="margin-top: 20px; font-size: 12px; color: #666;">
                        <p>This is an automated message from JSW Steel Project Bot. Please do not reply directly to this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            # Add HTML content
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
                
            self.logger.info(f"Successfully sent project summary email to {{recipient_email}}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email: {{str(e)}}")
            return False

    def send_whatsapp_message(self, project):
        """Send project details via WhatsApp"""
        try:
            # Format the WhatsApp message
            message = f"""*New Project Lead*

*Company:* {project.get('company', 'N/A')}
*Project:* {project.get('title', 'N/A')}
*Value:* ₹{project.get('value', 0):,.0f} Cr

*Steel Requirements:*
Primary: {project.get('steel_requirements', {}).get('primary', {}).get('quantity', 0):,} MT ({project.get('steel_requirements', {}).get('primary', {}).get('type', '')})
Secondary: {project.get('steel_requirements', {}).get('secondary', {}).get('quantity', 0):,} MT ({project.get('steel_requirements', {}).get('secondary', {}).get('type', '')})

*Timeline:* {project.get('start_date', datetime.now()).strftime('%B %Y')} - {project.get('end_date', datetime.now() + timedelta(days=365)).strftime('%B %Y')}

View Details: {project.get('source_url', 'N/A')}"""

            # WhatsApp API endpoint
            url = f"https://graph.facebook.com/v17.0/{Config.WHATSAPP_PHONE_NUMBER_ID}/messages"
            
            # Headers with authentication
            headers = {
                "Authorization": f"Bearer {Config.WHATSAPP_API_TOKEN}",
                "Content-Type": "application/json"
            }
            
            # Payload for WhatsApp message
            payload = {
                "messaging_product": "whatsapp",
                "to": Config.WHATSAPP_RECIPIENT,
                "type": "text",
                "text": {
                    "preview_url": True,
                    "body": message
                }
            }
            
            # Send the message with retry logic
            for attempt in range(3):  # Try up to 3 times
                try:
                    response = requests.post(url, headers=headers, json=payload)
                    response.raise_for_status()
                    
                    # Check response content
                    response_data = response.json()
                    if response_data.get('messages', []):
                        message_id = response_data['messages'][0].get('id')
                        self.logger.info(f"Successfully sent WhatsApp message. Message ID: {message_id}")
                        return True
                    else:
                        self.logger.warning("No message ID in response")
                        
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"WhatsApp API request failed on attempt {attempt + 1}: {str(e)}")
                    if attempt < 2:  # Don't sleep on last attempt
                        time.sleep(2 ** attempt)  # Exponential backoff
                    continue
                except Exception as e:
                    self.logger.error(f"Unexpected error sending WhatsApp message: {str(e)}")
                    break
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False

    def send_project_via_whatsapp(self, project):
        """Send a single project opportunity via WhatsApp with detailed information"""
        try:
            # Format the message with project details
            message = f"""*JSW Steel - New Project Lead*

*Project Details:*
Company: {project.get('company', 'N/A')}
Title: {project.get('title', 'N/A')}
Location: {project.get('location', 'N/A')}

*Value & Requirements:*
Contract Value: ₹{project.get('value', 0):,.0f} Cr
Steel Requirements:
• Primary: {project.get('steel_requirements', {}).get('primary', {}).get('quantity', 0):,} MT ({project.get('steel_requirements', {}).get('primary', {}).get('type', '')})
• Secondary: {project.get('steel_requirements', {}).get('secondary', {}).get('quantity', 0):,} MT ({project.get('steel_requirements', {}).get('secondary', {}).get('type', '')})

*Timeline:*
Start: {project.get('start_date', datetime.now()).strftime('%B %Y')}
End: {project.get('end_date', datetime.now() + timedelta(days=365)).strftime('%B %Y')}
Duration: {project.get('duration', 'N/A')}

*Key Contacts:*"""
            
            # Add contact information if available
            contacts = project.get('contacts', [])
            if contacts:
                for contact in contacts[:3]:  # Limit to top 3 contacts
                    message += f"""
• {contact.get('name', 'N/A')} ({contact.get('role', 'N/A')})
  {contact.get('email', '')}
  {contact.get('phone', '')}"""
            else:
                message += "\nNo contacts available yet"
            
            message += f"""

*Priority:* {project.get('priority', 'Normal Priority')}
*Source:* {project.get('source_url', 'N/A')}

For more details, visit: https://jsww.onrender.com"""
            
            url = f"https://graph.facebook.com/v17.0/{Config.WHATSAPP_PHONE_NUMBER_ID}/messages"
            
            headers = {
                "Authorization": f"Bearer {Config.WHATSAPP_API_TOKEN}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messaging_product": "whatsapp",
                "to": Config.WHATSAPP_RECIPIENT,
                "type": "text",
                "text": {
                    "preview_url": True,
                    "body": message
                }
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            self.logger.info(f"Successfully sent detailed project info via WhatsApp for: {project.get('title')}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending project via WhatsApp: {str(e)}")
            return False 