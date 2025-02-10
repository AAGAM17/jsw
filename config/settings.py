import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    load_dotenv()
    
    # Default User Agent string instead of using fake-useragent
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    
    PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
    CONTACT_OUT_API_KEY = os.getenv('CONTACT_OUT')
    SERP_API_KEY = os.getenv('SERP_API_KEY')
    FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
    
    EMAIL_SMTP_SERVER = os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
    EMAIL_SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', '587'))
    EMAIL_SENDER = os.getenv('EMAIL_SENDER')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    WHATSAPP_FROM = os.getenv('WHATSAPP_FROM')
    WHATSAPP_TO = [num.strip() for num in os.getenv('WHATSAPP_TO', '').split(',') if num.strip()]
    
    if not all([PERPLEXITY_API_KEY, EMAIL_SENDER, EMAIL_PASSWORD, SERP_API_KEY, FIRECRAWL_API_KEY]):
        raise ValueError(
            "Missing required environment variables. Please check your .env file:\n"
            "- PERPLEXITY_API_KEY\n"
            "- EMAIL_SENDER\n"
            "- EMAIL_PASSWORD\n"
            "- SERP_API_KEY\n"
            "- FIRECRAWL_API_KEY"
        )
    
    if any([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, WHATSAPP_FROM]) and not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, WHATSAPP_FROM, WHATSAPP_TO]):
        raise ValueError(
            "Incomplete Twilio configuration. If using WhatsApp, all these are required:\n"
            "- TWILIO_ACCOUNT_SID\n"
            "- TWILIO_AUTH_TOKEN\n"
            "- WHATSAPP_FROM\n"
            "- WHATSAPP_TO"
        )
    
    TEAM_EMAILS = {
        'TMT_BARS': 'chaudhariharsh86@gmail.com',
        'HR_CR_PLATES': 'harsh@meresu.in',
        'COATED_PRODUCTS': 'chaudhariharsh86@icloud.com',
        'HSLA': 'chaudhariharsh220@gmail.com',
        'SOLAR': 'harshchaudhari1990@gmail.com',
        'WIRE_RODS': 'chaudhariharshrealtac@gmail.com'
    }
    
    PROJECT_DISCOVERY = {
        'min_project_value': 5,  
        'min_steel_requirement': 50, 
        'max_procurement_months': 6,  
        'search_period_days': 7,  
        'priority_sectors': [
            'metro rail',
            'railway',
            'road infrastructure',
            'commercial real estate',
            'industrial parks',
            'port development'
        ],
        'target_companies': {
            'construction': [
                {
                    'name': 'Larsen & Toubro',
                    'aliases': ['L&T', 'L&T Construction', 'Larsen and Toubro'],
                    'announcement_urls': [
                        'https://www.larsentoubro.com/corporate/news-and-resources/',
                        'https://www.lntconstruction.com/news-and-media.aspx'
                    ]
                },
                {
                    'name': 'Dilip Buildcon',
                    'announcement_urls': ['https://www.dilipbuildcon.com/news-media']
                },
                {
                    'name': 'PNC Infratech',
                    'announcement_urls': ['https://www.pncinfratech.com/news-and-media']
                },
                {
                    'name': 'HG Infra Engineering',
                    'announcement_urls': ['https://www.hginfra.com/news-media.html']
                },
                {
                    'name': 'IRB Infrastructure',
                    'announcement_urls': ['https://www.irb.co.in/media-center']
                },
                {
                    'name': 'Cube Highways',
                    'announcement_urls': ['https://www.cubehighways.com/news']
                },
                {
                    'name': 'GR Infraprojects',
                    'announcement_urls': ['https://grinfra.com/news-media']
                },
                {
                    'name': 'Afcons Infrastructure',
                    'announcement_urls': ['https://www.afcons.com/news-media']
                },
                {
                    'name': 'Rail Vikas Nigam Limited',
                    'aliases': ['RVNL'],
                    'announcement_urls': ['https://rvnl.org/news']
                },
                {
                    'name': 'J Kumar Infraprojects',
                    'announcement_urls': ['https://www.jkumar.com/news-media']
                },
                {
                    'name': 'Megha Engineering',
                    'aliases': ['MEIL'],
                    'announcement_urls': ['https://meil.in/media']
                },
                {
                    'name': 'Ashoka Buildcon',
                    'announcement_urls': ['https://www.ashokabuildcon.com/news-media.html']
                }
            ],
            'power_infrastructure': [
                {
                    'name': 'Torrent Power',
                    'announcement_urls': ['https://www.torrentpower.com/newsroom.php']
                },
                {
                    'name': 'Genus Power',
                    'announcement_urls': ['https://www.genuspower.com/news-media']
                }
            ],
            'government_agencies': [
                {
                    'name': 'National Highways Authority of India',
                    'aliases': ['NHAI'],
                    'announcement_urls': ['https://nhai.gov.in/tenders']
                },
                {
                    'name': 'National High Speed Rail Corporation',
                    'aliases': ['NHSRCL'],
                    'announcement_urls': ['https://nhsrcl.in/en/tenders']
                },
                {
                    'name': 'Maharashtra State Road Development Corporation',
                    'aliases': ['MSRDC'],
                    'announcement_urls': ['https://www.msrdc.org/Site/Home/Tenders']
                },
                {
                    'name': 'Rail System Integration India Limited',
                    'aliases': ['RSIIL'],
                    'announcement_urls': ['https://rsiil.indianrailways.gov.in/']
                }
            ]
        },
        'search_domains': [
            'constructionworld.in',
            'themetrorailguy.com',
            'epc.gov.in',
            'nhai.gov.in',
            'nseindia.com',
            'biddetail.com',
            'newsonprojects.com',
            'constructionopportunities.in',
            'projectstoday.com',
            'metrorailtoday.com',
            'projectxindia.com'
        ],
        'steel_calculation_rates': {
            'high_rise': 60,  # kg/sqft
            'infrastructure': 125,  # kg/lane-km (average of 100-150)
            'metro': 175,  # kg/meter (average of 150-200)
            'industrial': 90  # kg/sqft (average of 80-100)
        }
    }
    
    # Product Mapping Rules - Enhanced with more specific categories
    PRODUCT_MAPPING = {
        'infrastructure': {
            'highways': 'TMT_BARS',
            'bridges': 'TMT_BARS',
            'flyover': 'TMT_BARS',
            'railways': 'HR_CR_PLATES',
            'metro': 'HR_CR_PLATES',
            'monorail': 'HR_CR_PLATES',
            'ports': 'HR_CR_PLATES',
            'smart_cities': 'TMT_BARS',
            'airport': 'HR_CR_PLATES'
        },
        'construction': {
            'residential': 'TMT_BARS',
            'commercial': 'TMT_BARS',
            'mall': 'TMT_BARS',
            'hospital': 'TMT_BARS',
            'school': 'TMT_BARS',
            'industrial': 'COATED_PRODUCTS',
            'warehouse': 'COATED_PRODUCTS',
            'factory': 'COATED_PRODUCTS',
            'shed': 'COATED_PRODUCTS'
        },
        'automotive': {
            'passenger': 'HR_CR_PLATES',
            'commercial_vehicles': 'HR_CR_PLATES',
            'ev': 'HSLA',
            'battery': 'HSLA',
            'charging': 'HSLA'
        },
        'renewable': {
            'solar': 'SOLAR',
            'solar_panel': 'SOLAR',
            'solar_mount': 'SOLAR',
            'wind': 'HR_CR_PLATES',
            'hydro': 'HR_CR_PLATES',
            'power_plant': 'HSLA'
        },
        'industrial': {
            'machinery': 'HR_CR_PLATES',
            'equipment': 'HSLA',
            'manufacturing': 'HR_CR_PLATES',
            'processing': 'HR_CR_PLATES',
            'storage': 'COATED_PRODUCTS'
        }
    }
    
    # Steel Requirement Estimation (tons per crore) - Updated with more specific rates
    STEEL_RATES = {
        'TMT_BARS': {
            'highways': 30,
            'bridges': 40,
            'flyover': 35,
            'smart_cities': 15,
            'residential': 10,
            'commercial': 15,
            'mall': 12,
            'hospital': 14,
            'school': 10,
            'default': 20
        },
        'HR_CR_PLATES': {
            'railways': 20,
            'metro': 25,
            'monorail': 22,
            'ports': 25,
            'airport': 20,
            'automotive': 8,
            'wind': 10,
            'machinery': 15,
            'manufacturing': 12,
            'default': 15
        },
        'COATED_PRODUCTS': {
            'industrial': 5,
            'warehouse': 8,
            'factory': 7,
            'shed': 6,
            'storage': 5,
            'default': 5
        },
        'HSLA': {
            'ev': 6,
            'battery': 5,
            'charging': 4,
            'equipment': 10,
            'power_plant': 8,
            'default': 8
        },
        'SOLAR': {
            'solar': 4,
            'solar_panel': 3,
            'solar_mount': 5,
            'default': 4
        },
        'WIRE_RODS': {
            'default': 5
        }
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
    
    # Firecrawl Configuration
    FIRECRAWL_SETTINGS = {
        'extraction_rules': {
            'project_details': [
                'article',
                '.entry-content',
                '.project-details',
                '.tender-details',
                # BidDetail.com selectors
                '.procurement-news-content',
                '.tender-content',
                # NewsOnProjects.com selectors
                '.project-news-item',
                '.news-content',
                # ConstructionOpportunities.in selectors
                '.opportunity-details',
                '.project-content',
                # ProjectsToday.com selectors
                '.project-description',
                '.project-info',
                # MetroRailToday.com selectors
                '.metro-project-details',
                '.news-article',
                # ProjectXIndia.com selectors
                '.project-details-content',
                '.news-details'
            ],
            'contact_info': [
                '.contact-details',
                '.procurement-team',
                '.project-contact',
                # New site-specific contact selectors
                '.bidder-contact',
                '.company-contact',
                '.procurement-details',
                '.contact-information'
            ],
            'dates': [
                '.project-timeline',
                '.schedule',
                '.dates',
                # New site-specific date selectors
                '.tender-dates',
                '.project-schedule',
                '.timeline-details',
                '.bid-dates'
            ],
            'specifications': [
                '.specifications',
                '.requirements',
                '.steel-specs',
                # New site-specific specification selectors
                '.material-requirements',
                '.technical-specs',
                '.project-requirements',
                '.tender-specifications'
            ]
        },
        'site_specific_rules': {
            'biddetail.com': {
                'main_content': '.procurement-news',
                'list_items': '.news-item',
                'pagination': '.pagination',
                'date_format': '%d %b %Y'
            },
            'newsonprojects.com': {
                'main_content': '.project-news',
                'list_items': '.news-article',
                'pagination': '.page-numbers',
                'date_format': '%B %d, %Y'
            },
            'constructionopportunities.in': {
                'main_content': '.opportunities-list',
                'list_items': '.opportunity-item',
                'pagination': '.pagination-links',
                'date_format': '%Y-%m-%d'
            },
            'projectstoday.com': {
                'main_content': '.projects-list',
                'list_items': '.project-item',
                'pagination': '.page-navigation',
                'date_format': '%d-%m-%Y'
            },
            'metrorailtoday.com': {
                'main_content': '.metro-news',
                'list_items': '.news-item',
                'pagination': '.page-numbers',
                'date_format': '%B %d, %Y'
            },
            'projectxindia.com': {
                'main_content': '.project-news',
                'list_items': '.news-item',
                'pagination': '.pagination',
                'date_format': '%d/%m/%Y'
            }
        },
        'extraction_options': {
            'clean_html': True,
            'remove_ads': True,
            'extract_tables': True,
            'follow_links': False,
            'max_depth': 2,
            'wait_for_selectors': ['.project-details', '.news-content', '.opportunity-details'],
            'scroll_to_bottom': True,
            'handle_dynamic_content': True
        },
        'regex_patterns': {
            'project_value': r'(?:Rs\.?|INR)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)',
            'steel_requirement': r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)',
            'email': r'[\w\.-]+@[\w\.-]+\.\w+',
            'phone': r'(?:\+91|0)?[789]\d{9}',
            'dates': r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}',
            'tmt_steel': r'TMT[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)',
            'hr_plates': r'HR[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)',
            # New patterns for tender/bid extraction
            'tender_id': r'(?:Tender|Bid)\s*(?:No|ID|Reference)[:.]?\s*([A-Z0-9-_/]+)',
            'submission_deadline': r'(?:Last|Due)\s*Date\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            'contract_duration': r'(?:Duration|Period|Completion Time)\s*:?\s*(\d+)\s*(?:months|years|days)',
            'contractor_name': r'(?:Contractor|Company|Bidder|Winner)\s*:?\s*([A-Za-z\s&]+)(?:Ltd|Limited|Pvt|Private|Corp|Corporation)?'
        }
    }
    
    # SERP API Configuration
    SERP_SETTINGS = {
        'search_parameters': {
            'engine': 'google',
            'gl': 'in',  # Restrict to Indian results
            'hl': 'en',  # English language
            'tbs': 'qdr:d',  # Last 24 hours (can be h1 for last hour, d1 for last day)
            'num': 100,  # Maximum results
            'google_domain': 'google.co.in'
        },
        'news_parameters': {
            'engine': 'google_news',
            'gl': 'in',
            'hl': 'en',
            'tbs': 'qdr:d',
            'num': 100,
            'google_domain': 'google.co.in'
        },
        'search_queries': [
            'infrastructure contract won',
            'infrastructure project awarded',
            'construction contract win',
            'metro contract awarded',
            'highway project awarded',
            'railway contract won',
            'infrastructure development contract',
            'construction tender result'
        ]
    }