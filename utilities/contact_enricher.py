import requests
import logging
import json
from config.settings import Config
import re
from datetime import datetime

class ContactEnricher:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = Config.CONTACT_OUT_API_KEY
        self.crm_data = self._load_crm_data()
        
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
        """Find procurement contacts for a company using CRM data and ContactOut API"""
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
            
            # Try ContactOut API
            contacts = self._search_contactout(company_name)
            
            if contacts:
                return {
                    'status': 'success',
                    'source': 'ContactOut',
                    'contacts': contacts,
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
    
    def _search_contactout(self, company_name):
        """Search for procurement contacts using ContactOut API"""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            # Use the correct endpoint and method
            response = requests.get(
                'https://api.contactout.com/v2/companies/search',
                headers=headers,
                params={
                    'company_name': company_name,
                    'limit': 5
                }
            )
            
            response.raise_for_status()
            company_data = response.json()
            
            if not company_data.get('data'):
                return []
            
            # Get company ID from search results
            company_id = company_data['data'][0].get('id')
            if not company_id:
                return []
            
            # Get employees with procurement roles
            response = requests.get(
                f'https://api.contactout.com/v2/companies/{company_id}/employees',
                headers=headers,
                params={
                    'role': ['procurement', 'purchasing', 'supply chain', 'materials'],
                    'seniority': ['director', 'vp', 'head', 'manager'],
                    'limit': 5
                }
            )
            
            response.raise_for_status()
            employees_data = response.json()
            
            contacts = []
            for employee in employees_data.get('data', []):
                contact = {
                    'name': f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
                    'role': employee.get('title', 'Procurement Manager'),
                    'email': employee.get('email', [{}])[0].get('email') if employee.get('email') else None,
                    'phone': employee.get('phone_numbers', [{}])[0].get('number') if employee.get('phone_numbers') else None,
                    'relationship_notes': ''
                }
                if contact['name'] and (contact['email'] or contact['phone']):
                    contacts.append(contact)
            
            # If no procurement contacts found, try CRM data
            if not contacts:
                crm_info = self._get_crm_info(company_name)
                if crm_info and crm_info.get('contacts'):
                    return crm_info['contacts']
            
            return contacts
            
        except Exception as e:
            self.logger.error(f"Error searching ContactOut: {str(e)}")
            # Fallback to CRM data if API fails
            crm_info = self._get_crm_info(company_name)
            return crm_info.get('contacts', []) if crm_info else [] 