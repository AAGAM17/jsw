import requests
import logging
import json
from config.settings import Config
import re
from datetime import datetime
import time
from scrapers.linkedin_scraper import LinkedInScraper

class ContactEnricher:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = Config.CONTACT_OUT_API_KEY
        self.crm_data = self._load_crm_data()
        self.linkedin = LinkedInScraper()
        
    def _load_crm_data(self):
        """Load CRM data from the predefined dictionary"""
        crm_data = {
            'rahee': {
                'contacts': [
                    {
                        'name': 'Ashish Raheja',
                        'role': 'VP, Eng. Procurement',
                        'email': 'ashish.raheja@rahee.com',
                        'phone': '+91 9898439394',
                        'relationship_notes': 'Previously worked with Sanjay Mirchandani from TMT Bars team on Mumbai Metro Project'
                    },
                    {
                        'name': 'Boman Irani',
                        'role': 'Senior VP, Procurement',
                        'email': 'boman.irani@rahee.com',
                        'phone': '+91 9074598939'
                    }
                ],
                'projects': {
                    'current': 'Mumbai Metro Project',
                    'volume': '60 MT (Completed)',
                    'materials': 'TMT Bars, Hot Rolled Plates',
                    'notes': 'Strong relationship with procurement team, successful delivery on Mumbai Metro'
                }
            },
            'larsen & toubro': {
                'contacts': [
                    {'name': 'Arjun Sharma', 'email': 'arjun.sharma@lt.com', 'phone': '+91-9876543210', 'role': 'VP of Procurement'},
                    {'name': 'Priya Patel', 'email': 'priya.patel@lt.com', 'phone': '+91-9988776655', 'role': 'VP of Procurement'}
                ],
                'projects': {
                    'current': 'Mumbai–Ahmedabad High-Speed Rail (MAHSR)',
                    'volume': '150,000 MT (Ongoing)',
                    'materials': 'High-Strength TMT Bars, HR Plates, LRPC',
                    'notes': 'JSW holds >50% market share in steel supply for this project. Strong relationship; exploring opportunities for Delhi–Varanasi HSR project'
                }
            }
        }
        return crm_data
    
    def enrich_project_contacts(self, project_info):
        """Find procurement contacts for a company using CRM data, LinkedIn and ContactOut API"""
        try:
            company_name = project_info.get('company', '')
            if not company_name or company_name == 'Unknown Company':
                return {
                    'status': 'error',
                    'message': 'Invalid company name'
                }
            
            # First check CRM data
            crm_info = self._get_crm_info(company_name)
            if crm_info:
                self.logger.info(f"Found existing contacts in CRM for {company_name}")
                return {
                    'status': 'success',
                    'source': 'CRM',
                    'contacts': crm_info['contacts'],
                    'relationship': {
                        'current_project': crm_info['projects']['current'],
                        'volume': crm_info['projects']['volume'],
                        'materials': crm_info['projects']['materials'],
                        'notes': crm_info['projects']['notes']
                    },
                    'priority': self._determine_priority(project_info)
                }
            
            # Search LinkedIn first
            linkedin_contacts = self._search_linkedin(company_name)
            
            # Try ContactOut API for additional data
            contactout_contacts = self._search_contactout(company_name)
            
            # Merge contacts from both sources
            all_contacts = self._merge_contacts(linkedin_contacts, contactout_contacts)
            
            if all_contacts:
                return {
                    'status': 'success',
                    'source': 'LinkedIn + ContactOut',
                    'contacts': all_contacts,
                    'relationship': {
                        'current_project': 'No existing relationship',
                        'volume': 'N/A',
                        'materials': 'N/A',
                        'notes': 'New potential customer'
                    },
                    'priority': self._determine_priority(project_info)
                }
            
            return {
                'status': 'not_found',
                'message': f"No contacts found for {company_name}"
            }
            
        except Exception as e:
            self.logger.error(f"Error enriching contacts for {company_name}: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }
    
    def _determine_priority(self, project_info):
        """Determine project priority based on various factors"""
        priority = "NORMAL"
        priority_indicators = []
        
        # Check for explicit priority marking
        title = project_info.get('title', '').lower()
        description = project_info.get('description', '').lower()
        full_text = f"{title} {description}"
        
        if '[high priority]' in full_text:
            priority = "HIGH"
            priority_indicators.append("Marked as High Priority")
        
        # Check steel requirement
        steel_req = project_info.get('steel_requirement', 0)
        if steel_req > 1000:
            priority = "HIGH"
            priority_indicators.append(f"Large steel requirement: {steel_req} MT")
        
        # Check timeline
        start_date = project_info.get('start_date')
        if start_date and isinstance(start_date, datetime):
            months_to_start = (start_date - datetime.now()).days / 30
            if months_to_start <= 3:
                priority = "HIGH"
                priority_indicators.append("Starting within 3 months")
        
        # Check for key terms
        key_terms = ['metro', 'railway', 'infrastructure', 'government']
        if any(term in full_text for term in key_terms):
            priority = "HIGH"
            priority_indicators.append("Strategic project type")
        
        return {
            'level': priority,
            'indicators': priority_indicators
        }
    
    def _normalize_company_name(self, name):
        """Normalize company name for matching"""
        # Remove common suffixes and clean the name
        name = name.lower()
        suffixes = ['limited', 'ltd', 'pvt', 'private', 'corporation', 'corp', 'inc', 'infrastructure', 'infra']
        for suffix in suffixes:
            name = name.replace(suffix, '').strip()
        return name.strip()
    
    def _get_crm_info(self, company_name):
        """Get company information from CRM data"""
        # Try exact match first
        if company_name in self.crm_data:
            return self.crm_data[company_name]
        
        # Try partial matches
        for crm_company, data in self.crm_data.items():
            if company_name in crm_company or crm_company in company_name:
                return data
        
        return None
    
    def _search_linkedin(self, company_name):
        """Search for procurement contacts on LinkedIn"""
        try:
            procurement_roles = [
                'procurement',
                'purchasing',
                'supply chain',
                'materials',
                'sourcing',
                'buyer',
                'vendor management'
            ]
            
            # Search for employees with procurement roles
            profiles = self.linkedin.search_company_employees(company_name, procurement_roles)
            
            # Get detailed information for each profile
            detailed_contacts = []
            for profile in profiles:
                if self._is_relevant_role(profile['title']):
                    details = self.linkedin.get_profile_details(profile['profile_url'])
                    if details:
                        detailed_contacts.append({
                            'name': details['name'],
                            'role': details['title'],
                            'location': details.get('location', ''),
                            'profile_url': profile['profile_url'],
                            'experience': details.get('experience', []),
                            'source': 'LinkedIn'
                        })
            
            return detailed_contacts
            
        except Exception as e:
            self.logger.error(f"LinkedIn search failed for {company_name}: {str(e)}")
            return []
    
    def _is_relevant_role(self, title):
        """Check if the role is relevant for procurement"""
        title_lower = title.lower()
        relevant_terms = [
            'procurement', 'purchase', 'purchasing', 'buyer', 'buying',
            'supply chain', 'vendor', 'material', 'sourcing', 'category',
            'contract', 'tender', 'bid'
        ]
        
        relevant_positions = [
            'director', 'head', 'vp', 'manager', 'lead', 'chief'
        ]
        
        return (
            any(term in title_lower for term in relevant_terms) and
            any(pos in title_lower for pos in relevant_positions)
        )
    
    def _merge_contacts(self, linkedin_contacts, contactout_contacts):
        """Merge contacts from LinkedIn and ContactOut, removing duplicates"""
        merged = []
        seen_names = set()
        
        # Add LinkedIn contacts first
        for contact in linkedin_contacts:
            name = contact['name'].lower()
            if name not in seen_names:
                seen_names.add(name)
                merged.append(contact)
        
        # Add ContactOut contacts if they're not duplicates
        for contact in contactout_contacts:
            name = contact['name'].lower()
            if name not in seen_names:
                seen_names.add(name)
                merged.append(contact)
        
        return merged
    
    def _search_contactout(self, company_name):
        """Search for procurement contacts using ContactOut API"""
        try:
            # Clean company name
            clean_company = re.sub(r'[\[\](){}<>]', '', company_name).strip()
            clean_company = re.sub(r'\s+', ' ', clean_company)
            
            headers = {
                'X-API-KEY': Config.CONTACT_OUT_API_KEY,
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # First search for company
            company_response = requests.post(
                'https://api.contactout.com/v2/companies/search',
                headers=headers,
                json={
                    'company_name': clean_company,
                    'limit': 1
                },
                timeout=15
            )
            company_response.raise_for_status()
            company_data = company_response.json()
            
            if not company_data.get('companies'):
                self.logger.warning(f"No company found in ContactOut for {clean_company}")
                return []
            
            company_id = company_data['companies'][0].get('id')
            if not company_id:
                return []
            
            # Search for employees with procurement roles
            employees_response = requests.post(
                'https://api.contactout.com/v2/contacts/bulk-search',
                headers=headers,
                json={
                    'company_id': company_id,
                    'titles': [
                        'procurement',
                        'purchasing',
                        'supply chain',
                        'materials',
                        'sourcing',
                        'buyer',
                        'vendor'
                    ],
                    'seniority_levels': [
                        'director',
                        'vp',
                        'head',
                        'manager',
                        'lead'
                    ],
                    'limit': 10
                },
                timeout=15
            )
            employees_response.raise_for_status()
            employees_data = employees_response.json()
            
            contacts = []
            for contact in employees_data.get('contacts', []):
                # Get detailed contact info
                if contact.get('id'):
                    detail_response = requests.get(
                        f'https://api.contactout.com/v2/contacts/{contact["id"]}',
                        headers=headers,
                        timeout=15
                    )
                    detail_response.raise_for_status()
                    detail_data = detail_response.json()
                    
                    # Extract contact details
                    emails = detail_data.get('emails', [])
                    phones = detail_data.get('phone_numbers', [])
                    
                    contacts.append({
                        'name': detail_data.get('full_name', ''),
                        'role': detail_data.get('current_title', ''),
                        'email': emails[0] if emails else None,
                        'phone': phones[0] if phones else None,
                        'location': detail_data.get('location', ''),
                        'company': detail_data.get('current_company', ''),
                        'source': 'ContactOut'
                    })
            
            return contacts
            
        except Exception as e:
            self.logger.error(f"ContactOut search failed for {company_name}: {str(e)}")
            return []
    
    def _calculate_similarity(self, str1, str2):
        """Calculate string similarity using Levenshtein distance"""
        if not str1 or not str2:
            return 0
        
        # Convert to sets of words for better matching
        set1 = set(str1.lower().split())
        set2 = set(str2.lower().split())
        
        # Calculate Jaccard similarity
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0 