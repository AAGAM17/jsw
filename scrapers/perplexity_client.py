import requests # type: ignore
import json
import logging
from config.settings import Config
from datetime import datetime, timedelta
import re
import time

class PerplexityClient:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {Config.PERPLEXITY_API_KEY}',
            'Content-Type': 'application/json'
        })
    
    def research_infrastructure_projects(self):
        """Research latest infrastructure project news"""
        projects = []
        
        # Primary query focusing on recent contract awards
        primary_query = """
        Find recent infrastructure and construction project contract awards in India. Include:
        
        1. Metro Rail Projects:
        - Metro rail construction
        - Station works
        - Viaduct construction
        - Underground tunneling
        
        2. Infrastructure Projects:
        - Highway construction
        - Bridge and flyover projects
        - Port development
        - Airport expansion
        - Smart city projects
        
        3. Building Projects:
        - Commercial complexes
        - Industrial facilities
        - Residential townships
        - Warehouses and logistics
        
        4. Industrial Projects:
        - Steel plants
        - Manufacturing units
        - Processing facilities
        - Power plants
        
        For each project, provide:
        - Company Name
        - Project Name
        - Contract Value in Crores
        - Project Timeline
        - Source URL
        
        Focus on:
        - Projects worth Rs. 0.2 Cr to 100 Cr
        - Recently awarded contracts
        - Verified information from reliable sources
        """
        
        try:
            self.logger.info("Trying primary query...")
            results = self._query_perplexity(primary_query)
            projects.extend(self._parse_project_results(results))
            
            # If no projects found, try backup query
            if not projects:
                backup_query = """
                Search for the most recent construction and infrastructure tenders awarded in India.
                Check these specific sources:
                - www.themetrorailguy.com
                - www.constructionworld.in
                - www.projectstoday.com
                - Government tender websites
                - Infrastructure news portals
                
                Look for:
                1. Metro rail and railway projects
                2. Road and highway projects
                3. Building construction projects
                4. Industrial projects
                
                Format each result exactly as:
                [Company Name] wins [Project Name]
                Contract Value: Rs. [X] Cr
                Timeline: Start [Month Year] to End [Month Year]
                Source: [URL]
                """
                
                self.logger.info("Trying backup query...")
                results = self._query_perplexity(backup_query)
                projects.extend(self._parse_project_results(results))
            
            # If still no projects, try emergency query
            if not projects:
                emergency_query = """
                List ALL infrastructure and construction projects announced in India in the last 30 days.
                Include ANY project announcements, contract awards, or tenders.
                Do not filter by value.
                Must return at least 5 projects with company names and values.
                """
                
                self.logger.info("Trying emergency query...")
                results = self._query_perplexity(emergency_query)
                projects.extend(self._parse_project_results(results))
            
            # Log results
            self.logger.info(f"Found {len(projects)} projects")
            if not projects:
                self.logger.error("No projects found after all attempts")
            
            return projects
            
        except Exception as e:
            self.logger.error(f"Error researching projects: {str(e)}", exc_info=True)
            return []
    
    def _query_perplexity(self, query):
        """Make API call to Perplexity with retries"""
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    'https://api.perplexity.ai/chat/completions',
                    json={
                        'model': 'sonar-pro',
                        'messages': [
                            {
                                'role': 'system',
                                'content': 'You are a specialized infrastructure research assistant. Always perform thorough web searches to find the most recent project information. Return ONLY verified information from reliable sources. Format each project exactly as specified.'
                            },
                            {
                                'role': 'user',
                                'content': query
                            }
                        ],
                        'temperature': 0.1,  # Lower temperature for more focused results
                        'max_tokens': 2000,
                        'top_p': 0.9,
                        'web_search': True
                    },
                    timeout=30  # Add timeout
                )
                
                response.raise_for_status()
                response_data = response.json()
                
                if 'choices' in response_data and response_data['choices']:
                    content = response_data['choices'][0]['message']['content']
                    self.logger.debug(f"API Response Content (first 500 chars): {content[:500]}")
                    return response_data
                else:
                    raise Exception("No choices in API response")
                    
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue
        
        raise Exception(f"All retries failed. Last error: {last_error}")

    def _parse_project_results(self, results):
        """Parse project information from API response"""
        projects = []
        try:
            if not results or 'choices' not in results or not results['choices']:
                return projects
                
            content = results['choices'][0]['message']['content']
            
            # Split content into project sections
            sections = re.split(r'\n\s*\n', content)
            
            for section in sections:
                if not section.strip():
                    continue
                
                try:
                    # Try to parse project details
                    project = {}
                    
                    # Look for company and project name
                    if 'wins' in section.lower():
                        match = re.search(r'([^:\n]+)\s+wins\s+([^:\n]+)', section, re.IGNORECASE)
                        if match:
                            project['company'] = match.group(1).strip()
                            project['title'] = match.group(2).strip()
                    
                    # Look for contract value
                    value_match = re.search(r'(?:Contract Value|Value|Worth|Cost):\s*(?:Rs\.|₹|INR)?\s*([\d,]+(?:\.\d+)?)\s*(?:Cr|Crore)', section, re.IGNORECASE)
                    if value_match:
                        try:
                            project['value'] = float(value_match.group(1).replace(',', ''))
                        except ValueError:
                            continue
                    
                    # Look for timeline
                    timeline_match = re.search(r'(?:Timeline|Duration|Period):\s*(?:Start)?\s*([A-Za-z]+\s+\d{4})\s*(?:to|till|until|-)?\s*(?:End)?\s*([A-Za-z]+\s+\d{4})', section, re.IGNORECASE)
                    if timeline_match:
                        try:
                            project['start_date'] = datetime.strptime(timeline_match.group(1), '%B %Y')
                            project['end_date'] = datetime.strptime(timeline_match.group(2), '%B %Y')
                        except ValueError:
                            # Try alternate date format
                            try:
                                project['start_date'] = datetime.strptime(timeline_match.group(1), '%b %Y')
                                project['end_date'] = datetime.strptime(timeline_match.group(2), '%b %Y')
                            except ValueError:
                                project['start_date'] = datetime.now()
                                project['end_date'] = datetime.now() + timedelta(days=365*2)
                    
                    # Look for source URL
                    url_match = re.search(r'(?:Source|Link|URL):\s*(https?://\S+)', section, re.IGNORECASE)
                    if url_match:
                        project['source_url'] = url_match.group(1).strip()
                    
                    # Extract description
                    project['description'] = section.strip()[:500]
                    
                    # Add project if it has minimum required fields
                    if project.get('company') and project.get('title') and project.get('value'):
                        projects.append(project)
                        
                except Exception as e:
                    self.logger.error(f"Error parsing section: {str(e)}")
                    continue
            
            self.logger.info(f"Successfully parsed {len(projects)} projects")
            
        except Exception as e:
            self.logger.error(f"Error parsing results: {str(e)}")
        
        return projects

    def _get_procurement_team_info(self, company, project_title):
        """Get procurement team information for a specific company/project"""
        query = f"""
        Find information about the procurement team and key decision makers at {company} 
        who would be involved in steel procurement for the project: {project_title}
        
        Focus on:
        1. Head of Procurement/Materials
        2. Project Director/Manager
        3. Any other key decision makers
        
        Include their:
        - Name
        - Role/Position
        - Contact information (if publicly available)
        """
        
        try:
            results = self._query_perplexity(query)
            return self._parse_procurement_results(results)
        except Exception as e:
            self.logger.error(f"Error getting procurement team info: {str(e)}")
            return None

    def _parse_procurement_results(self, results):
        """Parse procurement team information"""
        try:
            content = results['choices'][0]['message']['content']
            
            procurement_info = {
                'key_contacts': [],
                'department_info': '',
                'recent_updates': ''
            }
            
            # Extract contact information
            contact_pattern = r'(?:^|\n)(?:[-•*]\s*)?([^:\n]+):\s*([^\n]+)(?:\n(?:[-•*]\s*)?(?:Contact|Email|Phone):\s*([^\n]+))?'
            contacts = re.finditer(contact_pattern, content, re.MULTILINE)
            
            for match in contacts:
                name = match.group(1).strip()
                role = match.group(2).strip()
                contact = match.group(3).strip() if match.group(3) else None
                
                if name and role:
                    procurement_info['key_contacts'].append({
                        'name': name,
                        'role': role,
                        'contact': contact
                    })
            
            return procurement_info
            
        except Exception as e:
            self.logger.error(f"Error parsing procurement results: {str(e)}")
            return None

    def _estimate_steel_requirement(self, description, project_value):
        """Estimate steel requirement based on project type and value"""
        desc_lower = description.lower()
        
        if any(word in desc_lower for word in ['metro', 'railway', 'rail']):
            factor = Config.STEEL_FACTORS['metro']
        elif any(word in desc_lower for word in ['bridge', 'viaduct']):
            factor = Config.STEEL_FACTORS['bridge']
        elif any(word in desc_lower for word in ['building', 'complex', 'tower']):
            factor = Config.STEEL_FACTORS['building']
        else:
            factor = Config.STEEL_FACTORS['default']
        
        return project_value * factor

    def get_project_info(self, project_context):
        """Get detailed project information based on context and user query"""
        try:
            # Prepare system message for project-specific context
            system_message = """You are a specialized project assistant for JSW Steel. You have deep knowledge about:
            1. Infrastructure and construction projects in India
            2. Steel requirements and specifications for different project types
            3. Project timelines and milestones
            4. Key stakeholders and procurement processes
            5. Market trends and competitive analysis
            
            Provide detailed, accurate responses based on the project context provided.
            If you're not sure about something, acknowledge it and suggest where to find that information.
            Keep responses concise but informative."""
            
            response = self.session.post(
                'https://api.perplexity.ai/chat/completions',
                json={
                    'model': 'sonar-pro',
                    'messages': [
                        {
                            'role': 'system',
                            'content': system_message
                        },
                        {
                            'role': 'user',
                            'content': project_context
                        }
                    ],
                    'temperature': 0.3,  # Lower temperature for more focused responses
                    'max_tokens': 1000,
                    'top_p': 0.9,
                    'web_search': True
                },
                timeout=30
            )
            
            response.raise_for_status()
            response_data = response.json()
            
            if 'choices' in response_data and response_data['choices']:
                return response_data['choices'][0]['message']['content']
            else:
                raise Exception("No response from Perplexity API")
                
        except Exception as e:
            self.logger.error(f"Error getting project info: {str(e)}")
            return "I apologize, but I encountered an error while retrieving that information. Please try asking in a different way or contact support for assistance." 