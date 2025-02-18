"""Contact finder utility using Exa AI and ContactOut."""

import logging
from exa_py import Exa
import requests
from config.settings import Config
import time
from typing import List, Dict, Optional

class ContactFinder:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.exa_client = Exa(api_key=Config.EXA_API_KEY)
        self.contactout_token = Config.CONTACTOUT_TOKEN
        self.contactout_base_url = "https://api.contactout.com/v2"
    
    def find_procurement_contacts(self, company_name: str) -> List[Dict]:
        """Find procurement contacts for a company using Exa AI and ContactOut."""
        try:
            self.logger.info(f"Searching for procurement contacts at {company_name}")
            
            # First use Exa to find LinkedIn profiles
            linkedin_profiles = self._search_linkedin_profiles(company_name)
            if not linkedin_profiles:
                self.logger.warning(f"No LinkedIn profiles found for {company_name}")
                return []
            
            # Then use ContactOut to get contact details
            contacts = []
            for profile in linkedin_profiles:
                contact_info = self._get_contact_details(profile)
                if contact_info:
                    contacts.append(contact_info)
            
            self.logger.info(f"Found {len(contacts)} contacts for {company_name}")
            return contacts
            
        except Exception as e:
            self.logger.error(f"Error finding contacts for {company_name}: {str(e)}")
            return []
    
    def _search_linkedin_profiles(self, company_name: str) -> List[Dict]:
        """Search for relevant LinkedIn profiles using Exa AI."""
        try:
            # Create search queries for procurement professionals
            queries = [
                f"site:linkedin.com/in procurement manager {company_name}",
                f"site:linkedin.com/in procurement head {company_name}",
                f"site:linkedin.com/in procurement director {company_name}",
                f"site:linkedin.com/in materials manager {company_name}",
                f"site:linkedin.com/in sourcing manager {company_name}",
                f"site:linkedin.com/in purchasing manager {company_name}"
            ]
            
            profiles = []
            for query in queries:
                try:
                    self.logger.debug(f"Searching with query: {query}")
                    results = self.exa_client.search(
                        query,
                        num_results=2,  # Limit to top 2 results per query
                        include_domains=["linkedin.com"],
                        exclude_domains=[]
                    )
                    
                    if results and results.results:
                        for result in results.results:
                            if "/in/" in result.url:  # Ensure it's a profile URL
                                profiles.append({
                                    'name': result.title.split('|')[0].strip(),
                                    'title': result.title.split('|')[1].strip() if '|' in result.title else '',
                                    'url': result.url,
                                    'description': result.text
                                })
                    
                    time.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    self.logger.error(f"Error in Exa search for query '{query}': {str(e)}")
                    continue
            
            # Remove duplicates based on URL
            unique_profiles = {p['url']: p for p in profiles}.values()
            return list(unique_profiles)
            
        except Exception as e:
            self.logger.error(f"Error searching LinkedIn profiles: {str(e)}")
            return []
    
    def _get_contact_details(self, profile: Dict) -> Optional[Dict]:
        """Get contact details from ContactOut API."""
        try:
            headers = {
                "Authorization": f"Bearer {self.contactout_token}",
                "Content-Type": "application/json"
            }
            
            # First, search for the profile
            search_url = f"{self.contactout_base_url}/linkedin/profile"
            search_params = {
                "profile_url": profile['url']
            }
            
            search_response = requests.get(
                search_url,
                headers=headers,
                params=search_params
            )
            
            if search_response.status_code != 200:
                self.logger.error(f"ContactOut search failed: {search_response.text}")
                return None
            
            search_data = search_response.json()
            if not search_data.get('data'):
                return None
            
            # Get detailed profile information
            profile_id = search_data['data'].get('profile_id')
            if not profile_id:
                return None
            
            detail_url = f"{self.contactout_base_url}/profile/{profile_id}"
            detail_response = requests.get(
                detail_url,
                headers=headers
            )
            
            if detail_response.status_code != 200:
                self.logger.error(f"ContactOut detail fetch failed: {detail_response.text}")
                return None
            
            detail_data = detail_response.json()
            if not detail_data.get('data'):
                return None
            
            # Format contact information
            contact_data = detail_data['data']
            contact_info = {
                'name': contact_data.get('full_name', profile['name']),
                'title': contact_data.get('current_role', profile['title']),
                'company': contact_data.get('current_company', ''),
                'email': next((email for email in contact_data.get('emails', []) if email.get('is_verified')), {}).get('address'),
                'phone': next((phone for phone in contact_data.get('phones', []) if phone.get('is_verified')), {}).get('number'),
                'linkedin_url': profile['url'],
                'location': contact_data.get('location', ''),
                'confidence_score': contact_data.get('confidence_score', 0)
            }
            
            # Only return if we have at least an email or phone
            if contact_info.get('email') or contact_info.get('phone'):
                return contact_info
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting contact details from ContactOut: {str(e)}")
            return None
    
    def enrich_project_contacts(self, project: Dict) -> Dict:
        """Enrich project with procurement contact information."""
        try:
            if not project.get('company'):
                return project
            
            contacts = self.find_procurement_contacts(project['company'])
            if contacts:
                project['contacts'] = contacts
                self.logger.info(f"Added {len(contacts)} contacts to project {project.get('title', '')}")
            
            return project
            
        except Exception as e:
            self.logger.error(f"Error enriching project contacts: {str(e)}")
            return project 