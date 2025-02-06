import requests # type: ignore
import json
import logging
from config.settings import Config
from datetime import datetime, timedelta
import re

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
        query = """
        Find the most recent infrastructure and construction project contract awards in India. Focus on:

        1. Infrastructure Projects:
        - Metro rail projects
        - Highway and bridge construction
        - Railway projects
        - Port development
        - Smart city projects
        - Government infrastructure

        2. Construction Projects:
        - Commercial buildings
        - Industrial projects
        - Residential complexes
        - Warehouses and logistics
        - Steel-intensive projects

        For each project, provide information in exactly this format:
        [Company Name] wins [Project Name].
        Project is going to start from [Month Year] and end by [Month Year].
        Contract Value: Rs. [X] Cr
        Source: [URL]

        Important:
        - Only include projects worth between Rs. 0.2 Cr to 100 Cr
        - Only include contracts awarded in the last 45 days
        - Only include verified information from reliable sources
        - Must include start date and end date
        - Must include exact contract value
        - Must include source URL
        - Check metrorailguy.com and construction industry news
        """
        
        try:
            self.logger.info("Making Perplexity API call...")
            
            # Make API call with retries
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    results = self._query_perplexity(query)
                    if results and 'choices' in results:
                        break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    self.logger.warning(f"Retry {attempt + 1}/{max_retries} after error: {str(e)}")
                    continue
            
            projects = self._parse_project_results(results)
            
            if not projects:
                # Try backup query with different format
                backup_query = """
                Search for the latest infrastructure and construction contract awards in India announced in the last 45 days.
                Focus on projects between Rs. 0.2 Cr to 100 Cr.
                
                Format each result exactly like this example:
                L&T wins Mumbai Metro Line-3 Station Work.
                Project is going to start from March 2024 and end by December 2026.
                Contract Value: Rs. 45.5 Cr
                Source: www.example.com/announcement
                
                Important rules:
                - Must be recent contract wins/awards only
                - Must include exact company name
                - Must include contract value in crores
                - Must include project timeline
                - Must include source URL
                - Check metrorailguy.com and construction news sites
                """
                
                self.logger.info("Trying backup query...")
                results = self._query_perplexity(backup_query)
                projects = self._parse_project_results(results)
            
            return projects
            
        except Exception as e:
            self.logger.error(f"Error researching projects: {str(e)}", exc_info=True)
            return []
    
    def _query_perplexity(self, query):
        """Make API call to Perplexity"""
        try:
            response = self.session.post(
                'https://api.perplexity.ai/chat/completions',
                json={
                    'model': 'sonar-pro',
                    'messages': [
                        {
                            'role': 'system',
                            'content': 'You are a specialized infrastructure research assistant focused on finding construction and infrastructure projects in India. Always perform web searches to find the most recent information. Only report verified information from reliable sources.'
                        },
                        {
                            'role': 'user',
                            'content': query
                        }
                    ],
                    'temperature': 0.2,  # Lower temperature for more focused results
                    'max_tokens': 2000,
                    'top_p': 0.9,
                    'web_search': True
                }
            )
            
            response.raise_for_status()
            
            # Log response for debugging
            self.logger.debug(f"API Response Status: {response.status_code}")
            response_data = response.json()
            
            if 'choices' in response_data and response_data['choices']:
                content = response_data['choices'][0]['message']['content']
                self.logger.debug(f"API Response Content (first 500 chars): {content[:500]}")
            else:
                self.logger.error("No choices in API response")
                self.logger.debug(f"Full response: {response_data}")
            
            return response_data
            
        except Exception as e:
            self.logger.error(f"Perplexity API error: {str(e)}", exc_info=True)
            raise

    def _parse_project_results(self, results):
        """Parse project information from API response"""
        projects = []
        try:
            if not results or 'choices' not in results or not results['choices']:
                self.logger.error("Invalid API response format")
                return projects
                
            content = results['choices'][0]['message']['content']
            
            # Split content into project sections
            sections = content.split('\n\n')
            
            current_project = {}
            for section in sections:
                if not section.strip():
                    continue
                    
                lines = section.strip().split('\n')
                if len(lines) < 3:  # Need at least company, timeline, and value
                    continue
                
                # Parse project details
                for line in lines:
                    line = line.strip()
                    
                    # Company and project title
                    if 'wins' in line.lower() and not current_project:
                        parts = line.split(' wins ', 1)
                        if len(parts) == 2:
                            current_project = {
                                'company': parts[0].strip().rstrip('.'),
                                'title': parts[1].strip().rstrip('.')
                            }
                    
                    # Timeline
                    elif 'start from' in line.lower() and 'end by' in line.lower():
                        try:
                            start_str = line.split('start from')[1].split('and end by')[0].strip()
                            end_str = line.split('end by')[1].strip().rstrip('.')
                            
                            current_project['start_date'] = datetime.strptime(start_str, '%B %Y')
                            current_project['end_date'] = datetime.strptime(end_str, '%B %Y')
                        except Exception as e:
                            self.logger.error(f"Error parsing dates: {str(e)}")
                    
                    # Contract value
                    elif 'contract value' in line.lower() or 'value:' in line.lower():
                        try:
                            value_str = re.search(r'Rs\.\s*([\d,]+(?:\.\d+)?)\s*Cr', line)
                            if value_str:
                                current_project['value'] = float(value_str.group(1).replace(',', ''))
                        except Exception as e:
                            self.logger.error(f"Error parsing value: {str(e)}")
                    
                    # Source URL
                    elif 'source:' in line.lower():
                        current_project['source_url'] = line.split(':', 1)[1].strip()
                
                # Add project if it has required fields
                if current_project and current_project.get('company') and current_project.get('value'):
                    # Validate value range (0.2 Cr to 100 Cr)
                    if 0.2 <= current_project['value'] <= 100:
                        projects.append(current_project.copy())
                    current_project = {}
            
            self.logger.info(f"Successfully parsed {len(projects)} projects")
            
        except Exception as e:
            self.logger.error(f"Error parsing results: {str(e)}", exc_info=True)
        
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