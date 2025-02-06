from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging
from config.settings import Config
from datetime import datetime

class WhatsAppHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
        # Initialize Twilio client if configuration exists
        if all([Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN, Config.WHATSAPP_FROM, Config.WHATSAPP_TO]):
            try:
                self.client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
                self.whatsapp_from = Config.WHATSAPP_FROM
                self.recipients = Config.WHATSAPP_TO
                self.enabled = True
                self.logger.info("WhatsApp notifications enabled")
            except Exception as e:
                self.logger.error(f"Failed to initialize Twilio client: {str(e)}")
                self.enabled = False
        else:
            self.enabled = False
            self.logger.info("WhatsApp notifications disabled (missing configuration)")
    
    def send_project_opportunities(self, projects):
        """Send project opportunities via WhatsApp"""
        if not self.enabled:
            return False
            
        try:
            # Group projects by product type
            team_projects = {}
            for project in projects:
                product_type = project.get('product_type', 'UNKNOWN')
                if product_type not in team_projects:
                    team_projects[product_type] = []
                team_projects[product_type].append(project)
            
            # Create and send summary message for each team
            for product_type, product_projects in team_projects.items():
                total_value = sum(p.get('value', 0) for p in product_projects)
                total_steel = sum(p.get('steel_requirement', 0) for p in product_projects)
                
                message = f"""🏗️ *New {product_type.replace('_', ' ')} Projects*

📊 *Summary:*
• Projects: {len(product_projects)}
• Total Value: ₹{total_value:.1f}Cr
• Steel Required: {total_steel:.0f}MT

*Top Projects:*"""
                
                # Add top 3 projects by priority
                sorted_projects = sorted(product_projects, key=lambda x: x.get('priority_score', 0), reverse=True)
                for idx, project in enumerate(sorted_projects[:3], 1):
                    message += f"""

{idx}. *{project['company']}*
• {project['title']}
• Value: ₹{project.get('value', 0):.1f}Cr
• Steel: {project.get('steel_requirement', 0):.0f}MT
• Start: {project.get('start_date', datetime.now()).strftime('%b %Y')}"""
                
                message += """

💡 Check your email for complete details and links."""
                
                self._send_whatsapp(message)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending WhatsApp notifications: {str(e)}")
            return False
    
    def _send_whatsapp(self, message):
        """Send WhatsApp message with retries"""
        if not self.enabled:
            return False
            
        max_retries = 3
        for recipient in self.recipients:
            for attempt in range(max_retries):
                try:
                    # Format WhatsApp numbers
                    from_number = self.whatsapp_from.strip('+')
                    to_number = recipient.strip().strip('+')
                    
                    # Send message
                    response = self.client.messages.create(
                        body=message,
                        from_=f"whatsapp:+{from_number}",
                        to=f"whatsapp:+{to_number}"
                    )
                    
                    self.logger.info(f"Sent WhatsApp message to {to_number} (SID: {response.sid})")
                    break
                    
                except TwilioRestException as e:
                    if attempt == max_retries - 1:
                        self.logger.error(f"Failed to send WhatsApp to {recipient} after {max_retries} attempts: {str(e)}")
                    else:
                        self.logger.warning(f"Attempt {attempt + 1} failed for {recipient}, retrying...")
                        continue 