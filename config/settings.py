import os
from dotenv import load_dotenv
from fake_useragent import UserAgent

load_dotenv()

class Config:
    # API Keys
    PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
    
    # Email Configuration
    EMAIL_SMTP_SERVER = os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
    EMAIL_SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', '587'))
    EMAIL_SENDER = os.getenv('EMAIL_SENDER')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    
    # Team Email Configuration
    TEAM_EMAILS = {
        'TMT_BARS': 'chaudhariharsh86@gmail.com',
        'HR_CR_PLATES': 'harsh@meresu.in',
        'COATED_PRODUCTS': 'chaudhariharsh86@icloud.com',
        'HSLA': 'chaudhariharsh220@gmail.com',
        'SOLAR': 'harshchaudhari1990@gmail.com',
        'WIRE_RODS': 'chaudhariharshrealtac@gmail.com'
    }
    
    # Product Mapping Rules
    PRODUCT_MAPPING = {
        'infrastructure': {
            'highways': 'TMT_BARS',
            'bridges': 'TMT_BARS',
            'railways': 'HR_CR_PLATES',
            'metro': 'HR_CR_PLATES',
            'ports': 'HR_CR_PLATES',
            'smart_cities': 'TMT_BARS'
        },
        'construction': {
            'residential': 'TMT_BARS',
            'commercial': 'TMT_BARS',
            'industrial': 'COATED_PRODUCTS',
            'warehouse': 'COATED_PRODUCTS'
        },
        'automotive': {
            'passenger': 'HR_CR_PLATES',
            'commercial_vehicles': 'HR_CR_PLATES',
            'ev': 'HSLA'
        },
        'renewable': {
            'solar': 'SOLAR',
            'wind': 'HR_CR_PLATES',
            'hydro': 'HR_CR_PLATES'
        },
        'industrial': {
            'machinery': 'HR_CR_PLATES',
            'equipment': 'HSLA'
        }
    }
    
    # Steel Requirement Estimation (tons per crore)
    STEEL_RATES = {
        'TMT_BARS': {
            'highways': 30,
            'bridges': 40,
            'smart_cities': 15,
            'residential': 10,
            'commercial': 15,
            'default': 20
        },
        'HR_CR_PLATES': {
            'railways': 20,
            'metro': 25,
            'ports': 25,
            'automotive': 8,
            'wind': 10,
            'machinery': 15,
            'default': 15
        },
        'COATED_PRODUCTS': {
            'industrial': 5,
            'warehouse': 8,
            'default': 5
        },
        'HSLA': {
            'ev': 6,
            'equipment': 10,
            'default': 8
        },
        'SOLAR': {
            'solar': 4,
            'default': 4
        },
        'WIRE_RODS': {
            'default': 5
        }
    }
    
    # Project discovery settings
    PROJECT_DISCOVERY = {
        'max_age_days': 45,
        'min_project_value': 50,  # crores
        'focus_areas': [
            'infrastructure and construction projects in India',
            'metro rail and railway projects',
            'steel-intensive construction',
            'large industrial projects',
            'government infrastructure tenders'
        ]
    }
    
    # Project prioritization weights
    PRIORITY_WEIGHTS = {
        'time_factor': 0.7,  # Weight for project start time
        'value_factor': 0.3,  # Weight for project value
        'urgency_thresholds': {
            'urgent': 90,      # Days - Urgent if starting within 90 days
            'upcoming': 180    # Days - Upcoming if starting within 180 days
        }
    }
    
    # Steel requirement estimation factors
    STEEL_FACTORS = {
        'metro': 0.15,        # 15% of project value for metro projects
        'building': 0.12,     # 12% for building projects
        'bridge': 0.20,       # 20% for bridge projects
        'default': 0.10       # 10% default for other projects
    }
    
    # Database path for existing projects
    EXISTING_PROJECTS_DB = 'data/existing_projects.json'