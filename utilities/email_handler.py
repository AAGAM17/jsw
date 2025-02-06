import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime, timedelta
from config.settings import Config
import re
import time

class EmailHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Load email configuration
        self.smtp_server = Config.EMAIL_SMTP_SERVER
        self.smtp_port = Config.EMAIL_SMTP_PORT
        self.sender_email = Config.EMAIL_SENDER
        self.sender_password = Config.EMAIL_PASSWORD
        
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
            
            if months_old < 6:
                recency_factor = 1.0
            elif months_old < 12:
                recency_factor = 0.7
            else:
                recency_factor = 0.3
            
            # Calculate priority score
            priority_score = (value_in_cr + steel_tons) / (months_to_start ** 2) * recency_factor
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
            
            subject = f"[Priority Score: {priority_score:.2f}] New {product_type.replace('_', ' ')} Opportunity: {project['company']}"
            
            # Create HTML content
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #1a73e8;">New Project Opportunity</h2>
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #202124; margin-top: 0;">{project['company']}</h3>
                        <h4 style="color: #202124;">{project['title']}</h4>
                        
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
                product_type = self.determine_product_team(project)
                project['product_type'] = product_type
                project['priority_score'] = self.calculate_priority_score(project)
                project['steel_requirement'] = self.calculate_steel_requirement(project, product_type)
                
                if product_type not in team_projects:
                    team_projects[product_type] = []
                team_projects[product_type].append(project)
                
                total_value += project.get('value', 0)
                total_steel += project['steel_requirement']
            
            # Create consolidated email for each team
            for product_type, team_email in Config.TEAM_EMAILS.items():
                team_specific_projects = team_projects.get(product_type, [])
                if team_specific_projects:
                    team_value = sum(p.get('value', 0) for p in team_specific_projects)
                    team_steel = sum(p['steel_requirement'] for p in team_specific_projects)
                    
                    # Create informative subject line
                    subject = (
                        f"JSW Steel Opportunities: {len(team_specific_projects)} New Projects "
                        f"(₹{team_value:.1f}Cr, {team_steel:.0f}MT) - {product_type.replace('_', ' ')}"
                    )
                    
                    # Create message
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = subject
                    msg['From'] = self.sender_email
                    msg['To'] = team_email
                    
                    # Create HTML content
                    html_content = self._create_email_content(team_specific_projects, product_type, team_value, team_steel)
                    msg.attach(MIMEText(html_content, 'html'))
                    
                    # Send email with retries
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                                server.ehlo()
                                server.starttls()
                                server.ehlo()
                                server.login(self.sender_email, self.sender_password)
                                server.send_message(msg)
                                self.logger.info(f"Successfully sent consolidated email to {team_email} for {product_type}")
                                break
                        except Exception as e:
                            if attempt == max_retries - 1:
                                self.logger.error(f"Failed to send email after {max_retries} attempts: {str(e)}")
                                raise
                            self.logger.warning(f"Attempt {attempt + 1} failed, retrying...")
                            time.sleep(2 ** attempt)  # Exponential backoff
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending project opportunities: {str(e)}")
            return False

    def _create_email_content(self, projects, product_type, team_value, team_steel):
        """Create HTML content for email"""
        # Sort projects by priority score
        sorted_projects = sorted(projects, key=lambda x: x['priority_score'], reverse=True)
        
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 800px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #1a73e8;">New Project Opportunities - {product_type.replace('_', ' ')}</h2>
                
                <div style="background-color: #e8f0fe; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                    <h3 style="color: #1a73e8; margin-top: 0;">Summary</h3>
                    <p><strong>Total Projects:</strong> {len(projects)}</p>
                    <p><strong>Total Contract Value:</strong> ₹{team_value:.1f} Cr</p>
                    <p><strong>Total Steel Requirement:</strong> {team_steel:.0f} MT</p>
                </div>
        """
        
        # Add each project
        for idx, project in enumerate(sorted_projects, 1):
            html_content += f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
                    <h3 style="color: #202124; margin-top: 0;">
                        {idx}. {project['company']}
                        <span style="float: right; font-size: 0.9em; color: #1a73e8;">
                            Priority Score: {project['priority_score']:.2f}
                        </span>
                    </h3>
                    <h4 style="color: #202124;">{project['title']}</h4>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                        <div>
                            <p><strong>Timeline:</strong><br>
                            Start: {project.get('start_date', datetime.now()).strftime('%B %Y')}<br>
                            End: {project.get('end_date', datetime.now()).strftime('%B %Y')}</p>
                        </div>
                        <div>
                            <p><strong>Value:</strong> ₹{project.get('value', 0):.1f} Cr</p>
                            <p><strong>Steel Requirement:</strong> {project['steel_requirement']:.0f} MT</p>
                        </div>
                    </div>
                    
                    <p><strong>Description:</strong><br>
                    {project.get('description', '')[:300]}...</p>
                    
                    <p><a href="{project.get('source_url', '#')}" 
                          style="color: #1a73e8; text-decoration: none;">
                        View Announcement →
                    </a></p>
                </div>
            """
        
        # Add action items and footer
        html_content += """
                
                <div style="margin-top: 20px; font-size: 12px; color: #666;">
                    <p>This is an automated message from JSW Steel Project Bot. 
                    For support, please contact the IT team.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_content

    def send_project_opportunity(self, project, recipient_email):
        """Send a single project opportunity via email"""
        try:
            subject = f"New Project Opportunity: {project['company']} - {project['title']}"
            
            # Create HTML content
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #202124; margin-top: 0;">{project['company']}</h3>
                        <h4 style="color: #202124;">{project['title']}</h4>
                        
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
                
            self.logger.info(f"Successfully sent project opportunity email to {recipient_email}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending email: {str(e)}")
            return False
            
    def send_project_summary(self, projects, recipient_email):
        """Send a summary of multiple project opportunities"""
        try:
            subject = f"JSW Steel - New Project Opportunities Summary"
            
            # Create HTML content
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #1a73e8;">New Project Opportunities Summary</h2>
                    
                    <p>We found {len(projects)} new project opportunities that might interest you:</p>
            """
            
            # Add each project
            for idx, project in enumerate(projects, 1):
                html_content += f"""
                    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                        <h3 style="color: #202124; margin-top: 0;">#{idx}: {project['company']}</h3>
                        <h4 style="color: #202124;">{project['title']}</h4>
                        
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