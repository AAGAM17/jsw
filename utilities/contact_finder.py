"""Contact finder utility for project contacts."""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class ContactFinder:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Initialize static CRM data
        self.crm_data = {
            'nhai': {
                'contacts': [
                    {
                        'name': 'Rajat Mehta',
                        'email': 'rajath.mehta@nhai.gov.in',
                        'phone': '+91-9876543210',
                        'role': 'Chief Procurement Officer',
                        'notes': 'Led procurement for the Delhi-Mumbai Expressway; collaborated with Larsen & Toubro for geosynthetic materials'
                    },
                    {
                        'name': 'Ananya Reddy',
                        'email': 'ananya.reddy@nhai.gov.in',
                        'phone': '+91-8765432109',
                        'role': 'Head of Procurement'
                    }
                ]
            },
            'msrfc': {
                'contacts': [
                    {
                        'name': 'Vikram Singhania',
                        'email': 'vikram.singhania@msrfc.com',
                        'phone': '+91-9988776655',
                        'role': 'Director of Procurement',
                        'notes': 'Partnered with Tata Steel for structural components in the Chennai Port expansion'
                    },
                    {
                        'name': 'Priya Khurana',
                        'email': 'priya.khurana@msrfc.com',
                        'phone': '+91-8877665544',
                        'role': 'Senior Procurement Manager'
                    }
                ]
            },
            'kec international': {
                'contacts': [
                    {
                        'name': 'Vivek Sharma',
                        'email': 'vivek.sharma@kec.com',
                        'phone': '+91-9876543320',
                        'role': 'Director of Procurement',
                        'notes': 'Partnered with JSW Steel\'s team led by Nikhil Kapoor for transmission tower steel in the Rajasthan Power Grid project'
                    },
                    {
                        'name': 'Riya Patel',
                        'email': 'riya.patel@kec.com',
                        'phone': '+91-8765432091',
                        'role': 'Head of Procurement'
                    }
                ]
            },
            'ncc limited': {
                'contacts': [
                    {
                        'name': 'Rajat Reddy',
                        'email': 'rajat.reddy@ncc.co.in',
                        'phone': '+91-9876543319',
                        'role': 'Chief Procurement Officer',
                        'notes': 'Collaborated with JSW Steel\'s team led by Ritu Sharma for steel in the Hyderabad Metro Phase 2'
                    },
                    {
                        'name': 'Ananya Khanna',
                        'email': 'ananya.khanna@ncc.co.in',
                        'phone': '+91-7766554110',
                        'role': 'VP of Procurement'
                    }
                ]
            },
            'adani group': {
                'contacts': [
                    {
                        'name': 'Amit Desai',
                        'email': 'amit.desai@adani.com',
                        'phone': '+91-9876543318',
                        'role': 'Head of Procurement',
                        'notes': 'Worked with JSW Steel\'s team led by Rajesh Nair for steel in the Dhamra Port expansion'
                    },
                    {
                        'name': 'Priya Menon',
                        'email': 'priya.menon@adani.com',
                        'phone': '+91-8765432092',
                        'role': 'Senior Procurement Manager'
                    }
                ]
            },
            'tata projects': {
                'contacts': [
                    {
                        'name': 'Rohan Iyer',
                        'email': 'rohan.iyer@tataprojects.com',
                        'phone': '+91-9876543317',
                        'role': 'VP of Procurement',
                        'notes': 'Partnered with JSW Steel\'s team led by Arvind Reddy for steel in the Mumbai Coastal Road project'
                    },
                    {
                        'name': 'Kavita Rao',
                        'email': 'kavita.rao@tataprojects.com',
                        'phone': '+91-7766554109',
                        'role': 'Chief Procurement Officer'
                    }
                ]
            },
            'cidco': {
                'contacts': [
                    {
                        'name': 'Vikram Singh',
                        'email': 'vikram.singh@cidco.in',
                        'phone': '+91-9876543316',
                        'role': 'Director of Procurement',
                        'notes': 'Collaborated with JSW Steel\'s team led by Nandini Patel for steel in the Navi Mumbai Airport project'
                    },
                    {
                        'name': 'Anaya Desai',
                        'email': 'anaya.desai@cidco.in',
                        'phone': '+91-8765432093',
                        'role': 'Senior Procurement Manager'
                    }
                ]
            },
            'rvnl': {
                'contacts': [
                    {
                        'name': 'Rajiv Kapoor',
                        'email': 'rajiv.kapoor@rvnl.org',
                        'phone': '+91-9876543315',
                        'role': 'Chief Supply Chain Officer',
                        'notes': 'Worked with JSW Steel\'s team led by Aditya Rao for rail steel in the Delhi-Meerut RRTS project'
                    },
                    {
                        'name': 'Shruti Menon',
                        'email': 'shruti.menon@rvnl.org',
                        'phone': '+91-7766554108',
                        'role': 'Head of Procurement'
                    }
                ]
            },
            'patel engineering': {
                'contacts': [
                    {
                        'name': 'Rakesh Sharma',
                        'email': 'rakesh.sharma@patelengineering.com',
                        'phone': '+91-9876543314',
                        'role': 'VP of Procurement',
                        'notes': 'Partnered with JSW Steel\'s team led by Vikram Choudhary for tunnel steel in the Chenab Railway Bridge'
                    },
                    {
                        'name': 'Anita Reddy',
                        'email': 'anita.reddy@patelengineering.com',
                        'phone': '+91-8765432094',
                        'role': 'Senior Procurement Manager'
                    }
                ]
            },
            'larsen & toubro': {
                'contacts': [
                    {
                        'name': 'Rajiv Mehta',
                        'email': 'rajiv.mehta@larsentoubro.com',
                        'phone': '+91-9876543301',
                        'role': 'Chief Procurement Officer',
                        'notes': 'Collaborated with JSW Steel\'s team led by Vikram Singh for high-grade steel in the Mumbai-Ahmedabad Bullet Train project'
                    },
                    {
                        'name': 'Ananya Sharma',
                        'email': 'ananya.sharma@larsentoubro.com',
                        'phone': '+91-7766554101',
                        'role': 'VP of Procurement'
                    }
                ]
            },
            'dilip buildcon': {
                'contacts': [
                    {
                        'name': 'Rohan Verma',
                        'email': 'rohan.verma@dilipbuildcon.com',
                        'phone': '+91-9876543302',
                        'role': 'Director of Procurement',
                        'notes': 'Partnered with JSW Steel\'s team led by Sameer Joshi for structural steel in the Indore Metro project'
                    },
                    {
                        'name': 'Priya Kapoor',
                        'email': 'priya.kapoor@dilipbuildcon.com',
                        'phone': '+91-8765432100',
                        'role': 'Head of Procurement'
                    }
                ]
            }
        }
        
        # Common variations of company names
        self.company_variations = {
            'nhai': ['national highways authority of india', 'nhai', 'national highways'],
            'msrfc': ['msrfc', 'maharashtra state road development corporation', 'msrdc'],
            'kec international': ['kec international', 'kec', 'kec international limited'],
            'ncc limited': ['ncc limited', 'ncc', 'nagarjuna construction company'],
            'adani group': ['adani group', 'adani', 'adani enterprises', 'adani infrastructure'],
            'tata projects': ['tata projects', 'tata projects limited', 'tpl'],
            'cidco': ['cidco', 'city and industrial development corporation'],
            'rvnl': ['rvnl', 'rail vikas nigam limited', 'rail vikas nigam'],
            'patel engineering': ['patel engineering', 'patel engineering ltd', 'patel'],
            'larsen & toubro': ['larsen & toubro', 'l&t', 'l & t', 'larsen and toubro', 'l and t'],
            'dilip buildcon': ['dilip buildcon', 'dilip buildcon limited', 'dbl']
        }

    def _normalize_company_name(self, company_name: str) -> str:
        """Normalize company name for matching."""
        if not company_name:
            return ''
        
        # Convert to lowercase and strip whitespace
        company_name = company_name.lower().strip()
        
        # Log original and cleaned company name
        self.logger.debug(f"Original company name: {company_name}")
        
        # Remove common prefixes
        prefixes = ['m/s', 'm/s.', 'messrs.', 'messrs']
        for prefix in prefixes:
            if company_name.startswith(prefix):
                company_name = company_name[len(prefix):].strip()
        
        # Remove common suffixes
        suffixes = [
            'limited', 'ltd', 'ltd.', 
            'pvt', 'private', 'public',
            'corporation', 'corp', 'corp.',
            'infrastructure', 'infra',
            'construction', 'constructions',
            'engineering', 'engineers',
            'projects', 'project',
            'builders', 'industries',
            'enterprises', 'company'
        ]
        
        # Split into words and filter out suffixes
        words = company_name.split()
        filtered_words = []
        for word in words:
            # Keep words that are not in suffixes and not just single characters
            if word not in suffixes and len(word) > 1:
                filtered_words.append(word)
        
        company_name = ' '.join(filtered_words)
        self.logger.debug(f"After suffix removal: {company_name}")
        
        # Check for variations
        for standard_name, variations in self.company_variations.items():
            # Try exact match first
            if company_name in variations:
                self.logger.debug(f"Found exact variation match: {standard_name}")
                return standard_name
                
            # Try partial matches
            for variation in variations:
                if variation in company_name or company_name in variation:
                    self.logger.debug(f"Found partial variation match: {standard_name}")
                    return standard_name
                    
            # Try word-by-word matching
            company_words = set(company_name.split())
            for variation in variations:
                variation_words = set(variation.split())
                # If there's significant word overlap
                common_words = company_words & variation_words
                if common_words and len(common_words) >= min(len(company_words), len(variation_words)) * 0.5:
                    self.logger.debug(f"Found word overlap match: {standard_name}")
                    return standard_name
        
        self.logger.debug(f"No variation matches found, returning cleaned name: {company_name}")
        return company_name

    def get_company_contacts(self, company_name: str) -> List[Dict]:
        """Get contacts for a company from CRM data."""
        normalized_name = self._normalize_company_name(company_name)
        company_data = self.crm_data.get(normalized_name, {})
        return company_data.get('contacts', [])
    
    def enrich_project_contacts(self, project: Dict) -> Dict:
        """Enrich project with contact information."""
        try:
            company_name = project.get('company', '')
            if not company_name:
                self.logger.warning(f"No company name found in project: {project.get('title', 'Unknown')}")
                return project
            
            self.logger.info(f"Looking up contacts for company: {company_name}")
            normalized_name = self._normalize_company_name(company_name)
            self.logger.info(f"Normalized company name: {normalized_name}")
            
            # Use normalized name to get contacts
            contacts = self.get_company_contacts(normalized_name)
            if contacts:
                project['contacts'] = contacts
                self.logger.info(f"Found {len(contacts)} contacts for {company_name}")
                
                # Log relationship notes if present
                for contact in contacts:
                    if 'notes' in contact:
                        project.setdefault('relationship_notes', []).append(contact['notes'])
                        self.logger.info(f"Added relationship note from {contact['name']}: {contact['notes']}")
            else:
                self.logger.warning(f"No contacts found in CRM for {company_name} (normalized: {normalized_name})")
            
            return project
            
        except Exception as e:
            self.logger.error(f"Error enriching project contacts: {str(e)}")
            return project 