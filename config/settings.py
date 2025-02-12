import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    load_dotenv()
    
    # Default User Agent string instead of using fake-useragent
    USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    
    PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY')
    CONTACT_OUT_API_KEY = os.getenv('CONTACT_OUT_API_KEY', '')
    EXA_API_KEY = os.getenv('EXA_API_KEY')
    FIRECRAWL_API_KEY = os.getenv('FIRECRAWL_API_KEY')
    
    EMAIL_SMTP_SERVER = os.getenv('EMAIL_SMTP_SERVER', 'smtp.gmail.com')
    EMAIL_SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', '587'))
    EMAIL_SENDER = os.getenv('EMAIL_SENDER')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    WHATSAPP_FROM = os.getenv('WHATSAPP_FROM')
    WHATSAPP_TO = [num.strip() for num in os.getenv('WHATSAPP_TO', '').split(',') if num.strip()]
    
    # LinkedIn settings
    LINKEDIN_EMAIL = os.getenv('LINKEDIN_EMAIL', '')
    LINKEDIN_PASSWORD = os.getenv('LINKEDIN_PASSWORD', '')
    
    if not all([PERPLEXITY_API_KEY, EMAIL_SENDER, EMAIL_PASSWORD, EXA_API_KEY, FIRECRAWL_API_KEY]):
        raise ValueError(
            "Missing required environment variables. Please check your .env file:\n"
            "- PERPLEXITY_API_KEY\n"
            "- EMAIL_SENDER\n"
            "- EMAIL_PASSWORD\n"
            "- EXA_API_KEY\n"
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
        'TMT_BARS': 'rajashree.mahanty@jsw.in, siddhartha.mandal@jsw.in, chaudhariharsh86@gmail.com, aagamcshah172005@gmail.com',
        'HR_CR_PLATES': 'rajashree.mahanty@jsw.in, siddhartha.mandal@jsw.in, chaudhariharsh86@gmail.com',
        'COATED_PRODUCTS': 'rajashree.mahanty@jsw.in, siddhartha.mandal@jsw.in, chaudhariharsh86@gmail.com',
        'HSLA': 'rajashree.mahanty@jsw.in, siddhartha.mandal@jsw.in, chaudhariharsh86@gmail.com',
        'SOLAR': 'rajashree.mahanty@jsw.in, siddhartha.mandal@jsw.in,chaudhariharsh86@gmail.com',
        'WIRE_RODS': 'rajashree.mahanty@jsw.in, siddhartha.mandal@jsw.in, chaudhariharsh86@gmail.com'
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
            'highways': {'primary': 'TMT_BARS', 'secondary': 'HR_PLATES'},
            'bridges': {'primary': 'TMT_BARS', 'secondary': 'HR_PLATES'},
            'railways': {'primary': 'HR_PLATES', 'secondary': 'TMT_BARS'},
            'metro': {'primary': 'HR_PLATES', 'secondary': 'TMT_BARS'},
            'ports': {'primary': 'HR_PLATES', 'secondary': 'STRUCTURAL_STEEL'},
            'smart_cities': {'primary': 'TMT_BARS', 'secondary': 'COATED_PRODUCTS'}
        },
        'construction': {
            'residential': {'primary': 'TMT_BARS', 'secondary': 'COATED_PRODUCTS'},
            'commercial': {'primary': 'TMT_BARS', 'secondary': 'COATED_PRODUCTS'},
            'industrial': {'primary': 'COATED_PRODUCTS', 'secondary': 'HR_PLATES'}
        },
        'automotive': {
            'passenger': {'primary': 'HR_CR_COILS', 'secondary': 'HSLA'},
            'commercial_vehicles': {'primary': 'HR_CR_COILS', 'secondary': 'HSLA'},
            'ev': {'primary': 'HSLA', 'secondary': 'CR_COILS'}
        },
        'renewable': {
            'solar': {'primary': 'SOLAR_SOLUTIONS', 'secondary': 'HR_PLATES'},
            'wind': {'primary': 'HR_PLATES', 'secondary': 'STRUCTURAL_STEEL'},
            'hydro': {'primary': 'HR_PLATES', 'secondary': 'STRUCTURAL_STEEL'}
        },
        'industrial': {
            'machinery': {'primary': 'HR_PLATES', 'secondary': 'SPECIAL_ALLOY'},
            'equipment': {'primary': 'SPECIAL_ALLOY', 'secondary': 'HR_PLATES'},
            'manufacturing': {'primary': 'HR_PLATES', 'secondary': 'SPECIAL_ALLOY'}
        }
    }
    
    # Steel Requirement Estimation (tons per crore) - Updated with conservative rates
    STEEL_RATES = {
        'TMT_BARS': {
            'highways': 25,
            'bridges': 35,
            'railways': 20,
            'smart_cities': 12,
            'residential': 8,
            'commercial': 10,
            'default': 15
        },
        'HR_PLATES': {
            'railways': 18,
            'metro': 22,
            'ports': 20,
            'industrial': 15,
            'wind': 8,
            'machinery': 12,
            'default': 12
        },
        'COATED_PRODUCTS': {
            'industrial': 4,
            'commercial': 6,
            'residential': 5,
            'default': 4
        },
        'HSLA': {
            'ev': 5,
            'automotive': 4,
            'equipment': 8,
            'default': 6
        },
        'SOLAR_SOLUTIONS': {
            'solar': 3,
            'default': 3
        },
        'STRUCTURAL_STEEL': {
            'ports': 15,
            'wind': 12,
            'default': 10
        },
        'SPECIAL_ALLOY': {
            'machinery': 8,
            'equipment': 10,
            'default': 6
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
                # Main content selectors
                'article',
                '.entry-content',
                '.project-details',
                '.tender-details',
                '.news-content',
                '.project-description',
                
                # BidDetail.com selectors
                '.procurement-news-content',
                '.tender-content',
                '.bid-details',
                
                # NewsOnProjects.com selectors
                '.project-news-item',
                '.news-content',
                '.project-info',
                
                # ConstructionOpportunities.in selectors
                '.opportunity-details',
                '.project-content',
                '.tender-info',
                
                # ProjectsToday.com selectors
                '.project-description',
                '.project-info',
                '.project-details-content',
                
                # MetroRailToday.com selectors
                '.metro-project-details',
                '.news-article',
                '.tender-details',
                
                # ProjectXIndia.com selectors
                '.project-details-content',
                '.news-details',
                '.tender-info'
            ],
            'contact_info': [
                # Contact selectors
                '.contact-details',
                '.procurement-team',
                '.project-contact',
                '.contact-information',
                
                # Company-specific selectors
                '.bidder-contact',
                '.company-contact',
                '.procurement-details',
                '.tender-contact',
                
                # Role-specific selectors
                '.project-manager',
                '.procurement-head',
                '.site-engineer',
                '.technical-contact'
            ],
            'dates': [
                # Timeline selectors
                '.project-timeline',
                '.schedule',
                '.dates',
                '.completion-date',
                
                # Tender-specific dates
                '.tender-dates',
                '.project-schedule',
                '.timeline-details',
                '.bid-dates',
                '.submission-deadline',
                
                # Milestone dates
                '.construction-start',
                '.foundation-date',
                '.completion-target'
            ],
            'specifications': [
                # General specs
                '.specifications',
                '.requirements',
                '.steel-specs',
                '.material-requirements',
                
                # Detailed specs
                '.technical-specs',
                '.project-requirements',
                '.tender-specifications',
                '.material-details',
                
                # Steel-specific specs
                '.steel-requirement',
                '.tmt-requirement',
                '.hr-plates-specs',
                '.steel-grades'
            ]
        },
        'site_specific_rules': {
            'biddetail.com': {
                'main_content': '.procurement-news',
                'list_items': '.news-item',
                'pagination': '.pagination',
                'date_format': '%d %b %Y',
                'steel_specs': '.material-requirements'
            },
            'newsonprojects.com': {
                'main_content': '.project-news',
                'list_items': '.news-article',
                'pagination': '.page-numbers',
                'date_format': '%B %d, %Y',
                'steel_specs': '.project-specifications'
            },
            'constructionopportunities.in': {
                'main_content': '.opportunities-list',
                'list_items': '.opportunity-item',
                'pagination': '.pagination-links',
                'date_format': '%Y-%m-%d',
                'steel_specs': '.material-specs'
            },
            'projectstoday.com': {
                'main_content': '.projects-list',
                'list_items': '.project-item',
                'pagination': '.page-navigation',
                'date_format': '%d-%m-%Y',
                'steel_specs': '.requirements'
            },
            'metrorailtoday.com': {
                'main_content': '.metro-news',
                'list_items': '.news-item',
                'pagination': '.page-numbers',
                'date_format': '%B %d, %Y',
                'steel_specs': '.material-requirements'
            },
            'projectxindia.com': {
                'main_content': '.project-news',
                'list_items': '.news-item',
                'pagination': '.pagination',
                'date_format': '%d/%m/%Y',
                'steel_specs': '.project-specs'
            }
        },
        'extraction_options': {
            'clean_html': True,
            'remove_ads': True,
            'extract_tables': True,
            'follow_links': False,
            'max_depth': 2,
            'wait_for_selectors': [
                '.project-details',
                '.news-content',
                '.opportunity-details',
                '.material-requirements',
                '.steel-specs'
            ],
            'scroll_to_bottom': True,
            'handle_dynamic_content': True,
            'extract_metadata': True,
            'timeout': 15000
        },
        'regex_patterns': {
            'project_value': [
                r'(?:Rs\.?|INR)\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)',
                r'worth\s*(?:Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)',
                r'value\s*of\s*(?:Rs\.?|INR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:cr|crore)'
            ],
            'steel_requirement': [
                r'(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)',
                r'steel\s*requirement\s*(?:of|:)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)',
                r'(?:TMT|HR)\s*requirement\s*(?:of|:)?\s*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)'
            ],
            'email': r'[\w\.-]+@[\w\.-]+\.\w+',
            'phone': r'(?:\+91|0)?[789]\d{9}',
            'dates': [
                r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}',
                r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
                r'(?:start|begin|commence).*?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                r'(?:complete|finish|end).*?(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})'
            ],
            'steel_products': {
                'tmt': r'TMT[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)',
                'hr_plates': r'(?:HR|Hot Rolled)\s*plates?[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)',
                'hsla': r'HSLA[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)',
                'coated': r'(?:Coated|Galvanized)[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)',
                'solar': r'(?:Solar|PV)\s*steel[^\d]*(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:MT|ton)'
            },
            'tender_details': {
                'id': r'(?:Tender|Bid)\s*(?:No|ID|Reference)[:.]?\s*([A-Z0-9-_/]+)',
                'submission': r'(?:Last|Due)\s*Date\s*:?\s*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
                'duration': r'(?:Duration|Period|Completion Time)\s*:?\s*(\d+)\s*(?:months|years|days)',
                'contractor': r'(?:Contractor|Company|Bidder|Winner)\s*:?\s*([A-Za-z\s&]+)(?:Ltd|Limited|Pvt|Private|Corp|Corporation)?'
            }
        }
    }
    
    # Exa API Configuration (replacing SERP_SETTINGS)
    EXA_SETTINGS = {
        'search_parameters': {
            'max_characters': 1000,
            'max_results': 50,
            'include_domains': [
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
            'exclude_domains': [
                'facebook.com',
                'twitter.com',
                'linkedin.com',
                'youtube.com'
            ]
        },
        'search_queries': [
            'infrastructure contract won india',
            'infrastructure project awarded india',
            'construction contract win india',
            'metro contract awarded india',
            'highway project awarded india',
            'railway contract won india',
            'infrastructure development contract india',
            'construction tender result india'
        ]
    }