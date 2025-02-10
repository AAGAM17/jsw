from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import logging
from config.settings import Config
from datetime import datetime
import time

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
        if not self.enabled or not projects:
            return False
            
        success = True
        for recipient in self.recipients:
            try:
                # Format recipient number
                to_number = recipient.strip().strip('+')
                
                # Send overview message first
                overview = f"🏗️ *New Project Opportunities*\n\nFound {len(projects)} new projects:\n"
                for idx, project in enumerate(projects, 1):
                    overview += f"\n{idx}. {project['company']} - {project['title']}"
                    if project.get('value'):
                        overview += f" (₹{project['value']:.1f} Cr)"
                
                if not self._send_whatsapp(overview, to_number):
                    success = False
                    continue
                
                # Send detailed messages for each project
                for idx, project in enumerate(projects, 1):
                    message = self._format_project_message(project, idx)
                    if not self._send_whatsapp(message, to_number):
                        success = False
                        break
                    time.sleep(1)  # Add delay between messages
                    
            except Exception as e:
                self.logger.error(f"Error sending WhatsApp to {recipient}: {str(e)}")
                success = False
                
        return success
    
    def _format_project_message(self, project, idx):
        """Format a single project message"""
        message = f"*Project #{idx} Details*\n\n"
        
        # Basic info
        message += f"*Company:* {project['company']}\n"
        message += f"*Project:* {project['title']}\n\n"
        
        # Value and timeline
        if project.get('value'):
            message += f"*Value:* ₹{project['value']:.1f} Crore\n"
        
        if project.get('start_date'):
            message += f"*Start Date:* {project['start_date'].strftime('%B %Y')}\n"
        if project.get('end_date'):
            message += f"*End Date:* {project['end_date'].strftime('%B %Y')}\n"
        message += "\n"
        
        # Steel requirements if available
        if project.get('steel_requirements'):
            message += "*Steel Requirements:*\n"
            for steel_type, amount in project['steel_requirements'].items():
                message += f"• {steel_type}: {amount} MT\n"
            message += "\n"
        
        # Source and additional info
        if project.get('source_url'):
            message += f"*Source:* {project['source_url']}\n"
        if project.get('description'):
            message += f"\n*Description:*\n{project['description'][:300]}..."
        
        return message
    
    def _send_whatsapp(self, message, to_number, max_retries=3):
        """Send WhatsApp message with retries"""
        if not self.enabled:
            return False
            
        for attempt in range(max_retries):
            try:
                # Format WhatsApp numbers
                from_number = self.whatsapp_from.strip('+')
                
                # Send message
                response = self.client.messages.create(
                    from_=f"whatsapp:+{from_number}",
                    body=message,
                    to=f"whatsapp:+{to_number}"
                )
                
                self.logger.info(f"Sent WhatsApp message to {to_number} (SID: {response.sid})")
                return True
                
            except TwilioRestException as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to send WhatsApp to {to_number} after {max_retries} attempts: {str(e)}")
                else:
                    self.logger.warning(f"Attempt {attempt + 1} failed for {to_number}, retrying in 2 seconds...")
                    time.sleep(2)  # Wait before retry
                    continue
            except Exception as e:
                self.logger.error(f"Unexpected error sending WhatsApp to {to_number}: {str(e)}")
                return False
                
        return False 