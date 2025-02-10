import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime, timedelta
from config.settings import Config
import re
import time
from .contact_enricher import ContactEnricher

class EmailHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Load email configuration
        self.smtp_server = Config.EMAIL_SMTP_SERVER
        self.smtp_port = Config.EMAIL_SMTP_PORT
        self.sender_email = Config.EMAIL_SENDER
        self.sender_password = Config.EMAIL_PASSWORD
        self.team_emails = Config.TEAM_EMAILS
        
        # Initialize contact enricher
        self.contact_enricher = ContactEnricher()
        
        # Validate email configuration
        if not all([self.smtp_server, self.smtp_port, self.sender_email, self.sender_password]):
            raise ValueError("Missing email configuration. Please check your .env file.")
            
        self.logger.info(f"Initialized EmailHandler with sender: {self.sender_email}")
        
        # Test SMTP connection during initialization
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()  # Can be omitted
                server.starttls()  # Enable TLS
                server.ehlo()  # Can be omitted
                server.login(self.sender_email, self.sender_password)
                self.logger.info("Successfully connected to SMTP server")
        except Exception as e:
            self.logger.warning(f"Could not establish SMTP connection: {str(e)}")
            # Don't raise the error - allow the instance to be created
            # The error handling will be done in the send methods
        
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
    
    def send_team_email(self, project, team_email):
        """Send project opportunity to specific team"""
        try:
            product_type = self.determine_product_team(project)
            steel_req = self.calculate_steel_requirement(project, product_type)
            priority_score = self.calculate_priority_score(project)
            
            subject = f"JSW Steel Leads"
            
            # Create HTML content
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #1a73e8;">New Project Opportunity</h2>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #202124; margin-top: 0;">{project('company')}</h3>
                        <h4 style="color: #202124;">{project('title')}</h4>
                        
                        <p><strong>Product Type:</strong> {product_type.replace('_', ' ')}</p>
                        <p><strong>Priority Score:</strong> {priority_score:.2f}</p>
                        
                        <p><strong>Timeline:</strong><br>
                        Start: {project.get('start_date', datetime.now()).strftime('%B %Y')}<br>
                        End: {project.get('end_date', datetime.now()).strftime('%B %Y')}</p>
                        
                        <p><strong>Contract Value:</strong> Rs. {project.get('value', 0):,.0f} Cr</p>
                        <p><strong>Estimated Steel Requirement:</strong> {steel_req:,.0f} MT</p>
                        
                        <p><strong>Source:</strong> <a href="{project.get('source_url', '#')}" style="color: #1a73e8;">View Announcement</a></p>
                    </div>
                    
                    <div style="background-color: #e8f0fe; padding: 15px; border-radius: 5px;">
                        <h4 style="color: #1a73e8; margin-top: 0;">Actions Required:</h4>
                        <ul style="list-style-type: none; padding-left: 0;">
                            <li>• Review project details and steel requirements</li>
                            <li>• Contact procurement team if interested</li>
                            <li>• Update CRM with follow-up actions</li>
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
            msg['To'] = team_email
            
            # Add HTML content
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
                
            self.logger.info(f"Successfully sent project opportunity email to {team_email} for {product_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending team email: {str(e)}")
            return False
    
    def send_project_opportunities(self, projects):
        """Send consolidated project opportunities email to all teams"""
        try:
            # Log the number of projects received
            self.logger.info(f"Starting to send {len(projects)} projects via email")
            
            # Test SMTP connection first
            self.logger.info("Testing SMTP connection...")
            try:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    self.logger.info(f"Attempting login with {self.sender_email}")
                    server.login(self.sender_email, self.sender_password)
                    self.logger.info("SMTP connection test successful")
            except Exception as e:
                self.logger.error(f"SMTP connection test failed: {str(e)}")
                raise

            # Group projects by product team
            team_projects = {}
            total_value = 0
            total_steel = 0
            
            for project in projects:
                try:
                    product_type = self.determine_product_team(project)
                    self.logger.info(f"Processing project: {project.get('title')} for team {product_type}")
                    
                    # Calculate and store project metrics
                    project['product_type'] = product_type
                    project['priority_score'] = self.calculate_priority_score(project)
                    project['steel_requirement'] = self.calculate_steel_requirement(project, product_type)
                    
                    if product_type not in team_projects:
                        team_projects[product_type] = []
                    team_projects[product_type].append(project)
                    
                    total_value += project.get('value', 0)
                    total_steel += project['steel_requirement']
                    
                except Exception as e:
                    self.logger.error(f"Error processing project {project.get('title')}: {str(e)}")
                    continue
            
            self.logger.info(f"Projects grouped by team: {', '.join(f'{k}: {len(v)}' for k,v in team_projects.items())}")
            self.logger.info(f"Total portfolio value: Rs. {total_value:,.0f} Cr")
            self.logger.info(f"Total steel requirement: {total_steel:,.0f} MT")
            
            # Send emails to each team
            emails_sent = 0
            for product_type, team_email in Config.TEAM_EMAILS.items():
                team_specific_projects = team_projects.get(product_type, [])
                if team_specific_projects:
                    try:
                        self.logger.info(f"Preparing email for {product_type} team ({len(team_specific_projects)} projects)")
                        team_value = sum(p.get('value', 0) for p in team_specific_projects)
                        team_steel = sum(p.get('steel_requirement', 0) for p in team_specific_projects)
                        
                        # Create email content
                        html_content = self._create_email_content(
                            team_specific_projects, 
                            product_type,
                            team_value,
                            team_steel
                        )
                        
                        # Create message
                        msg = MIMEMultipart('alternative')
                        msg['Subject'] = f"JSW Steel Project Leads - {product_type.replace('_', ' ')}"
                        msg['From'] = self.sender_email
                        msg['To'] = team_email
                        msg.attach(MIMEText(html_content, 'html'))
                        
                        # Send with retry
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                                    server.starttls()
                                    server.login(self.sender_email, self.sender_password)
                                    server.send_message(msg)
                                    self.logger.info(f"Successfully sent email to {team_email} for {product_type}")
                                    emails_sent += 1
                                    break
                            except Exception as e:
                                if attempt < max_retries - 1:
                                    self.logger.warning(f"Attempt {attempt + 1} failed for {team_email}: {str(e)}")
                                    time.sleep(2 ** attempt)  # Exponential backoff
                                else:
                                    self.logger.error(f"Failed to send email to {team_email} after {max_retries} attempts: {str(e)}")
                                    raise
                    
                    except Exception as e:
                        self.logger.error(f"Error sending email to {product_type} team: {str(e)}")
                        continue
            
            self.logger.info(f"Email sending complete. Successfully sent to {emails_sent} teams")
            return emails_sent > 0
            
        except Exception as e:
            self.logger.error(f"Error in send_project_opportunities: {str(e)}")
            return False

    def _create_email_content(self, projects, product_type, team_value, team_steel):
        """Create HTML content for email"""
        # Sort projects by priority score
        sorted_projects = sorted(projects, key=lambda x: x['priority_score'], reverse=True)
        
        html_content = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; }
        .container { max-width: 800px; margin: 20px auto; background: #fff; padding: 30px; border-radius: 10px; }
        .header { margin-bottom: 30px; }
        .header h1 { color: #000; font-size: 24px; }
        .project { background: #fff; border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 20px; }
        .project.urgent { border-left: 4px solid #dc3545; }
        .project.normal { border-left: 4px solid #28a745; }
        .priority-tag { display: inline-block; padding: 4px 12px; border-radius: 4px; font-size: 14px; font-weight: bold; margin-bottom: 10px; }
        .priority-tag.high { color: #dc3545; }
        .priority-tag.normal { color: #28a745; }
        .title { font-size: 18px; color: #202124; margin: 10px 0; }
        .section { margin: 15px 0; }
        .section-title { font-size: 14px; color: #666; margin-bottom: 8px; }
        .info-item { margin: 5px 0; }
        .contact { padding: 10px; background: #f8f9fa; border-radius: 4px; margin: 5px 0; }
        .button-group { margin-top: 20px; display: flex; gap: 10px; }
        .button { display: inline-block; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 500; }
        .button.primary { background: #1a73e8; color: white; }
        .button.secondary { background: #f8f9fa; color: #1a73e8; border: 1px solid #1a73e8; }
        .button:hover { opacity: 0.9; }
        .footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; color: #666; font-size: 13px; }
    </style>
</head>
<body>
    <div class="container">
"""
        
        for project in sorted_projects:
            priority_score = project.get('priority_score', 0)
            is_urgent = priority_score > 0.7
            priority_class = "high" if is_urgent else "normal"
            priority_text = "High Priority" if is_urgent else "Normal Priority"
            
            company = project.get('company', '')
            title = project.get('title', '')
            value = project.get('value', 0)
            project_id = f"{company}_{title}".lower().replace(" ", "_")
            
            html_content += f"""
        <div class="project {priority_class}">
            <span class="priority-tag {priority_class}">{priority_text}</span>
            
            <div class="title">
                <strong>{company}</strong> awarded {title} project worth <strong>₹{value:.1f} Crore</strong>
            </div>
            
            <div class="section">
                <div class="section-title">Possible Requirements</div>"""
            
            if project.get('steel_requirements'):
                for i, (steel_type, amount) in enumerate(project['steel_requirements'].items()):
                    html_content += f"""
                <div class="info-item">
                    <strong>{steel_type}- {amount}MT</strong>
                    <span style="color: #666">({'Primary' if i==0 else 'Secondary'})</span>
                </div>"""
            elif project.get('steel_requirement'):
                total_req = project['steel_requirement']
                html_content += f"""
                <div class="info-item">
                    <strong>TMT Bars- {total_req * 0.8:.0f}MT</strong>
                    <span style="color: #666">(Primary)</span>
                </div>
                <div class="info-item">
                    <strong>Hot Rolled plates- {total_req * 0.2:.0f}MT</strong>
                    <span style="color: #666">(Secondary)</span>
                </div>"""
            
            if project.get('start_date'):
                start_date = project['start_date']
                quarter = (start_date.month-1)//3 + 1
                year = start_date.strftime('%Y')
                duration = project.get('duration', '3 years')
                html_content += f"""
            </div>
            <div class="section">
                <div class="section-title">Timeline</div>
                <div class="info-item">
                    Work begins: <strong>Q{quarter}, {year} - {duration}</strong>
                </div>"""
            
            if project.get('contacts'):
                html_content += """
            </div>
            <div class="section">
                <div class="section-title">Key Personnel</div>"""
                for contact in project['contacts']:
                    html_content += f"""
                <div class="contact">
                    <strong>{contact['name']}</strong> - {contact['role']}<br>
                    <span style="color: #666">
                        {contact.get('phone', '')}, {contact.get('email', '')}
                    </span>"""
                    if contact.get('notes'):
                        html_content += f"""
                    <div style="font-style: italic; color: #666; margin-top: 5px;">
                        {contact['notes']}
                    </div>"""
                    html_content += """
                </div>"""
            
            html_content += f"""
            </div>
            <div class="button-group">
                <a href="{project.get('source_url', '#')}" class="button primary">View Announcement</a>
                <a href="https://jsw-projects.com/chat/{project_id}" class="button secondary">Get More Info</a>
            </div>
        </div>"""
        
        html_content += """
        <div class="footer">
            This is an automated message from JSW Steel Project Bot.
        </div>
    </div>
</body>
</html>"""
        
        return html_content

    def send_project_opportunity(self, project, recipient_email):
        """Send a single project opportunity via email"""
        try:
            subject = f"JSW Steel Leads"
            
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #202124; margin-top: 0;">{project('company')}</h3>
                        <h4 style="color: #202124;">{project('title')}</h4>
                        
                        <p><strong>Timeline:</strong><br>
                        Start: {project.get('start_date', datetime.now()).strftime('%B %Y')}<br>
                        End: {project.get('end_date', datetime.now()).strftime('%B %Y')}</p>
                        
                        <p><strong>Contract Value:</strong> Rs. {project.get('value', 0):,.0f} Cr</p>
                        
                        <p><strong>Estimated Steel Requirement:</strong> {project.get('steel_requirement', 0):,.0f} MT</p>
                        
                        <p><strong>Source:</strong> <a href="{project.get('source_url', '#')}" style="color: #1a73e8;">View Announcement</a></p>
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
                
            self.logger.info(f"Successfully sent project opportunity email to {recipient_email}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email: {str(e)}")
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
                    
                    <p>We found {len(projects)} new project opportunities that might interest you:</p>
            """
            
            # Add each project
            for idx, project in enumerate(projects, 1):
                html_content += f"""
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #202124; margin-top: 0;">#{idx}: {project('company')}</h3>
                        <h4 style="color: #202124;">{project('title')}</h4>
                        
                        <p><strong>Timeline:</strong><br>
                        Start: {project.get('start_date', datetime.now()).strftime('%B %Y')}<br>
                        End: {project.get('end_date', datetime.now()).strftime('%B %Y')}</p>
                        
                        <p><strong>Contract Value:</strong> Rs. {project.get('value', 0):,.0f} Cr</p>
                        <p><strong>Estimated Steel Requirement:</strong> {project.get('steel_requirement', 0):,.0f} MT</p>
                        
                        <p><a href="{project.get('source_url', '#')}" style="color: #1a73e8;">View Announcement</a></p>
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
                
            self.logger.info(f"Successfully sent project summary email to {recipient_email}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email: {str(e)}")
            return False 