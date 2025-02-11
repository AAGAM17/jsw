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
        title_lower = project['title'].lower()
        description = project.get('description', '').lower()
        text = f"{title_lower} {description}"
        
        # Check for specific keywords in order of priority
        for industry, subsectors in Config.PRODUCT_MAPPING.items():
            for subsector, product in subsectors.items():
                if subsector in text:
                    return product
        
        # Default mappings based on broader categories
        if any(word in text for word in ['bridge', 'highway', 'flyover', 'building', 'residential']):
            return 'TMT_BARS'
        elif any(word in text for word in ['metro', 'railway', 'port', 'machinery']):
            return 'HR_CR_PLATES'
        elif any(word in text for word in ['roof', 'shed', 'warehouse']):
            return 'COATED_PRODUCTS'
        elif any(word in text for word in ['ev', 'electric vehicle', 'power', 'energy']):
            return 'HSLA'
        elif any(word in text for word in ['solar', 'renewable']):
            return 'SOLAR'
        
        # Default to TMT_BARS for construction/infrastructure projects
        return 'TMT_BARS'
    
    def calculate_steel_requirement(self, project, product_type):
        """Calculate steel requirement based on project type and value"""
        value_in_cr = project.get('value', 0)
        text = f"{project['title'].lower()} {project.get('description', '').lower()}"
        
        # Get the rates for the product type
        rates = Config.STEEL_RATES.get(product_type, {})
        
        # Find the most specific rate
        rate = rates['default']
        for category, category_rate in rates.items():
            if category != 'default' and category in text:
                rate = category_rate
                break
        
        # Conservative estimation
        steel_tons = value_in_cr * rate * 0.8  # Using 0.8 as conservative factor
        return steel_tons
    
    def calculate_priority_score(self, project):
        """Calculate priority score based on contract value, timeline, and recency"""
        try:
            value_in_cr = project.get('value', 0)
            steel_tons = project.get('steel_requirement', 0)
            
            # Calculate months until project start
            start_date = project.get('start_date', datetime.now() + timedelta(days=730))  # Default 24 months
            months_to_start = max(1, (start_date - datetime.now()).days / 30)
            
            # Calculate recency factor
            news_date = project.get('news_date', datetime.now())
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
        """Analyze project content using Groq to extract better estimates and details"""
        try:
            # Combine all project text for analysis
            full_text = f"""
            Title: {project.get('title', '')}
            Company: {project.get('company', '')}
            Description: {project.get('description', '')}
            Value: {project.get('value', 0)} Crore
            Location: {project.get('location', '')}
            """
            
            # First message to analyze project and generate headline
            headline_messages = [
                {"role": "system", "content": """You are a headline writer for JSW Steel's sales team. Write ONLY a single-line headline about infrastructure projects. Focus on physical characteristics like size, length, area, or volume - not monetary value.

Rules:
- Write ONLY the headline, nothing else
- Use 9-10 words maximum
- Focus on physical size/scope
- Do not explain your thinking
- Do not use quotes or formatting

Examples of good headlines:
L&T to build 65 km Patna road project
Afcons wins Delhi metro extension for 12 stations
Tata wins order for 5000 affordable housing units
MEIL to construct 200-km irrigation canal in Andhra"""},
                {"role": "user", "content": f"Write a single headline for this project: {full_text}"}
            ]
            
            # Second message to analyze steel requirements with new estimation logic
            steel_messages = [
                {"role": "system", "content": """Act as a steel demand estimator for JSW Steel. Analyze project details to:

1. Identify industry and sub-sector
2. Map to TWO most relevant JSW products (Primary and Secondary)
3. Estimate quantities using conservative benchmarks

Product Mapping Rules:
Infrastructure:
- Highways/Bridges → TMT Bars (Primary), HR Plates (Secondary)
- Railways → HR Plates (Primary), TMT Bars (Secondary)
- Ports → HR Plates (Primary), Structural Steel (Secondary)
- Smart Cities → TMT Bars (Primary), Coated Products (Secondary)

Construction:
- Residential/Commercial → TMT Bars (Primary), Coated Products (Secondary)
- Industrial → Coated Products (Primary), HR Plates (Secondary)

Automotive:
- Vehicles → HR/CR Coils (Primary), HSLA Steel (Secondary)
- EVs → HSLA Steel (Primary), CR Coils (Secondary)

Renewable:
- Solar → Solar Solutions (Primary), HR Plates (Secondary)
- Wind/Hydro → HR Plates (Primary), Structural Steel (Secondary)

Industrial:
- Machinery → HR Plates (Primary), Special Alloy Steel (Secondary)
- Equipment → Special Alloy Steel (Primary), HR Plates (Secondary)

Rules:
- Use conservative estimates
- Apply 0.8 adjustment factor
- Format output exactly as:
Primary Product: [Product]: ~[X,XXX]MT
Secondary Product: [Product]: ~[X,XXX]MT"""},
                {"role": "user", "content": f"Analyze this project and provide steel requirements: {full_text}"}
            ]
            
            # Add retry logic with exponential backoff
            max_retries = 3
            retry_delay = 2
            
            headline = None
            primary_product = None
            secondary_product = None
            
            # Get headline
            for attempt in range(max_retries):
                try:
                    completion = self.groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=headline_messages,
                        temperature=0.6,
                        max_completion_tokens=4096,
                        top_p=0.95,
                        stream=False,
                        stop=None
                    )
                    
                    # Clean up the headline response
                    headline = completion.choices[0].message.content.strip()
                    headline = headline.replace('"', '').replace("'", '')
                    headline = headline.split('\n')[0]
                    headline = re.sub(r'^(?:Headline:|Title:)\s*', '', headline)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                    else:
                        self.logger.error(f"Failed to generate headline: {str(e)}")
            
            time.sleep(2)  # Add delay between API calls
            
            # Get steel requirements
            for attempt in range(max_retries):
                try:
                    completion = self.groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=steel_messages,
                        temperature=0.6,
                        max_completion_tokens=4096,
                        top_p=0.95,
                        stream=False,
                        stop=None
                    )
                    
                    steel_analysis = completion.choices[0].message.content
                    
                    # Extract primary and secondary products
                    primary_match = re.search(r'Primary Product:\s*([^:]+):\s*~([\d,]+)MT', steel_analysis)
                    secondary_match = re.search(r'Secondary Product:\s*([^:]+):\s*~([\d,]+)MT', steel_analysis)
                    
                    if primary_match:
                        primary_product = {
                            'type': primary_match.group(1).strip(),
                            'quantity': int(primary_match.group(2).replace(',', ''))
                        }
                    
                    if secondary_match:
                        secondary_product = {
                            'type': secondary_match.group(1).strip(),
                            'quantity': int(secondary_match.group(2).replace(',', ''))
                        }
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)
                        time.sleep(wait_time)
                    else:
                        self.logger.error(f"Failed to analyze steel requirements: {str(e)}")
            
            # Update project with analyzed information
            if headline:
                project['analyzed_title'] = headline
            
            # Set steel requirements
            if primary_product and secondary_product:
                project['steel_requirements'] = {
                    'primary': primary_product,
                    'secondary': secondary_product,
                    'total': primary_product['quantity'] + secondary_product['quantity']
                }
            else:
                # Fallback calculation if AI analysis fails
                value_in_cr = project.get('value', 0)
                project['steel_requirements'] = {
                    'primary': {'type': 'TMT Bars', 'quantity': int(value_in_cr * 12)},
                    'secondary': {'type': 'HR Plates', 'quantity': int(value_in_cr * 8)},
                    'total': int(value_in_cr * 20)
                }
            
            return project
            
        except Exception as e:
            self.logger.error(f"Error analyzing project with Groq: {str(e)}")
            # Ensure we have fallback values
            value_in_cr = project.get('value', 0)
            project['steel_requirements'] = {
                'primary': {'type': 'TMT Bars', 'quantity': int(value_in_cr * 12)},
                'secondary': {'type': 'HR Plates', 'quantity': int(value_in_cr * 8)},
                'total': int(value_in_cr * 20)
            }
            return project
    
    def _prioritize_projects(self, projects):
        """Prioritize projects based on multiple factors"""
        try:
            # First do a basic sort based on initial criteria
            for project in projects:
                # Calculate base priority score without Groq
                value = project.get('value', 0)
                source_boost = 1.2 if project.get('source') == 'exa_web' else 1.0
                size_boost = 1.3 if value < 100 else (1.1 if value < 500 else 1.0)
                
                # Basic priority calculation
                base_score = (value / 1000) * source_boost * size_boost
                project['initial_priority'] = base_score
            
            # Sort by initial priority and take top 7 projects
            pre_sorted = sorted(projects, key=lambda x: x.get('initial_priority', 0), reverse=True)[:7]
            
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
            return sorted(projects, key=lambda x: x.get('value', 0), reverse=True)[:5]
    
    def _format_project_for_email(self, project):
        """Format a single project for HTML email"""
        try:
            # Use analyzed title if available, otherwise clean up original title
            title = project.get('analyzed_title')
            if not title:
                title = project.get('title', 'No title')
                # Clean up title if it's the original one
                title = re.sub(r'\s+is\s+(?:an\s+)?under\s+construction.*$', '', title, flags=re.IGNORECASE)
                title = re.sub(r'\s+by\s+', ' ', title)  # Remove "by" if present
            
            # Determine priority class and text
            priority_score = project.get('final_priority_score', 50)
            priority_class = "high" if priority_score > 70 else "normal"
            priority_text = "High Priority" if priority_score > 70 else "Normal Priority"
            
            # Format dates
            start_date = project.get('start_date')
            if isinstance(start_date, str):
                try:
                    start_date = datetime.strptime(start_date, '%Y-%m-%d')
                except ValueError:
                    start_date = datetime.now()
            elif not isinstance(start_date, datetime):
                start_date = datetime.now()
                
            end_date = project.get('end_date')
            if isinstance(end_date, str):
                try:
                    end_date = datetime.strptime(end_date, '%Y-%m-%d')
                except ValueError:
                    end_date = start_date + timedelta(days=365)
            elif not isinstance(end_date, datetime):
                end_date = start_date + timedelta(days=365)
            
            # Calculate project duration in years
            duration_years = (end_date - start_date).days / 365.0
            duration_str = f"{duration_years:.1f} years"
            
            # Format quarter and year
            quarter = (start_date.month - 1) // 3 + 1
            start_str = f"Q{quarter} {start_date.year}"
            
            # Format work timeline
            work_timeline = f"{start_str} - {duration_str}"
            
            # Get steel requirements
            steel_reqs = project.get('steel_requirements', {
                'primary': {'type': 'TMT Bars', 'quantity': 0},
                'secondary': {'type': 'HR Plates', 'quantity': 0}
            })
            
            primary_req = f"{steel_reqs['primary']['type']}: ~{steel_reqs['primary']['quantity']:,}MT"
            
            # Only show secondary requirements if they exist
            secondary_req = ""
            if 'secondary' in steel_reqs and steel_reqs['secondary'].get('type'):
                secondary_req = f"""
                    <div style="margin-bottom: 12px;">
                        <strong style="color: #1a1a1a;">Secondary:</strong> {steel_reqs['secondary']['type']}: ~{steel_reqs['secondary']['quantity']:,}MT
                    </div>
                """
            
            # Format tags
            tags = project.get('tags', [])
            tags_html = ''.join([
                f'<span style="background: {"#e8f5e9" if "Normal" in tag else "#fde8e8"}; color: {"#2e7d32" if "Normal" in tag else "#dc3545"}; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-right: 8px;">{tag}</span>'
                for tag in tags
            ])
            
            # Format contacts
            contacts = project.get('contacts', [])
            contacts_html = ''
            if contacts:
                contacts_html = '<div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid #eee;">'
                for contact in contacts:
                    contacts_html += f"""
                        <div style="margin-bottom: 10px;">
                            <div style="font-weight: 600; color: #424242;">{contact.get('name', '')}</div>
                            <div style="color: #666; font-size: 14px;">{contact.get('role', '')}</div>
                            <div style="color: #666; font-size: 14px;">
                                <a href="mailto:{contact.get('email', '')}" style="color: #1a73e8; text-decoration: none;">{contact.get('email', '')}</a>
                                <span style="margin: 0 8px;">•</span>
                                <a href="tel:{contact.get('phone', '')}" style="color: #1a73e8; text-decoration: none;">{contact.get('phone', '')}</a>
                            </div>
                        </div>
                    """
                contacts_html += '</div>'
            
            # Create HTML for single project
            html = f"""
            <div class="project" style="margin: 20px 0; padding: 20px; border-radius: 8px; border: 1px solid #e0e0e0; border-left: 4px solid {"#2e7d32" if "Normal Priority" in tags else "#dc3545"};">
                <div style="margin-bottom: 15px;">
                    {tags_html}
                </div>
                    
                <h3 style="margin: 0 0 8px 0; color: #1a1a1a; font-size: 24px;">{project.get('company', '')}</h3>
                <h4 style="margin: 0 0 20px 0; color: #424242; font-size: 20px;">{title}</h4>
                
                <div style="margin-bottom: 20px;">
                    <div style="margin-bottom: 12px;">
                        <strong style="color: #1a1a1a;">Primary:</strong> {primary_req}
                    </div>
                    {secondary_req}
                    <div style="margin-bottom: 12px;">
                        <strong style="color: #1a1a1a;">Work Begins:</strong> {work_timeline}
                    </div>
                </div>
                
                {contacts_html}
                    
                <div style="margin-top: 20px;">
                    <a href="{project.get('source_url', '#')}" style="display: inline-block; background: #1a73e8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-right: 10px;">View Announcement</a>
                    <a href="#" style="display: inline-block; background: #f8f9fa; color: #1a73e8; padding: 10px 20px; text-decoration: none; border-radius: 4px; border: 1px solid #1a73e8;">Get More Info</a>
                </div>
            </div>
            """
            
            return html
            
        except Exception as e:
            self.logger.error(f"Error formatting project: {str(e)}")
            return f"""
            <div style="margin: 20px 0; padding: 20px; border: 1px solid #dc3545; border-radius: 8px;">
                Error formatting project details
            </div>
            """

    def _get_team_emails(self, teams):
        """Get email addresses for teams"""
        try:
            # If teams is a list of strings, use them directly
            if isinstance(teams, list) and all(isinstance(t, str) for t in teams):
                return [self.team_emails.get(team) for team in teams if team in self.team_emails]
            
            # If teams is a string, treat it as a single team
            if isinstance(teams, str):
                return [self.team_emails.get(teams)] if teams in self.team_emails else []
            
            # If teams is a dict with primary/secondary
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
            # Group projects by team
            team_projects = {}
            
            for project in projects:
                try:
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
            
            # Send emails to each team
            for email, team_project_list in team_projects.items():
                try:
                    # Skip prioritization/analysis for test emails - use projects as is
                    msg = MIMEMultipart('alternative')
                    msg['From'] = self.sender_email
                    msg['To'] = email
                    msg['Subject'] = "JSW Steel Project Leads"
                    
                    html_content = f"""
                    <html>
                    <head>
                        <style>
                            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                            .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                            h1 {{ color: #202124; margin-bottom: 30px; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>Leads for the {team_project_list[0]['teams'][0].replace('_', ' ')} team</h1>
                            {''.join(self._format_project_for_email(project) for project in team_project_list)}
                            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 13px;">
                                <p>This is an automated notification from the JSW Steel Project Discovery System.</p>
                                <p>For any questions or support, please contact the sales team.</p>
                            </div>
                        </div>
                    </body>
                    </html>
                    """
                    
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
            
            # Create HTML content
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #28a745;">New Project Opportunities Summary</h2>
                    
                    <p>We found {{len(projects)}} new project opportunities that might interest you:</p>
            """
            
            # Add each project
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