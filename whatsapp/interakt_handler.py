"""Interakt WhatsApp handler for sending project notifications."""

import logging
from datetime import datetime, timedelta
from track import Client
from config.settings import Config
import requests

class InteraktHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = Config.INTERAKT_API_KEY
        self.phone_number = Config.INTERAKT_PHONE_NUMBER
        self.base_url = "https://api.interakt.ai/v1/public/message/"
        self.enabled = bool(self.api_key and self.phone_number)
        if self.enabled:
            self.logger.info(f"Interakt WhatsApp notifications enabled. Target number: {self.phone_number}")
        else:
            self.logger.error("Interakt configuration incomplete")
    
    def send_project_opportunities(self, projects):
        """Send project opportunities via WhatsApp using Interakt"""
        if not self.enabled:
            self.logger.error("WhatsApp notifications are not enabled")
            return False
            
        if not projects:
            self.logger.warning("No projects to send notifications for")
            return False
            
        success = True
        try:
            self.logger.info(f"Attempting to send notifications for {len(projects)} projects to {self.phone_number}")
            
            # Send overview message first
            overview = self._format_overview_message(projects)
            if not self._send_whatsapp(overview):
                success = False
            
            # Send detailed messages for each project
            for idx, project in enumerate(projects, 1):
                self.logger.debug(f"Sending project #{idx} details for {project.get('title', 'Unknown Project')}")
                message = self._format_project_message(project, idx)
                if not self._send_whatsapp(message):
                    success = False
                    
        except Exception as e:
            self.logger.error(f"Error sending project opportunities: {str(e)}")
            success = False
            
        self.logger.info(f"Finished sending notifications. Success: {success}")
        return success
    
    def _format_overview_message(self, projects):
        """Format overview message for multiple projects"""
        overview = f"🏗️ *New Project Opportunities*\n\nFound {len(projects)} new projects:\n"
        for idx, project in enumerate(projects, 1):
            overview += f"\n{idx}. {project['company']} - {project['title']}"
            if project.get('value'):
                overview += f" (₹{project['value']:.1f} Cr)"
        return overview
    
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
            steel_reqs = project['steel_requirements']
            if isinstance(steel_reqs, dict):
                for key, value in steel_reqs.items():
                    if isinstance(value, dict):
                        message += f"• {value.get('type', key)}: {value.get('quantity', 0):,} MT\n"
                    else:
                        message += f"• {key}: {value:,} MT\n"
            message += "\n"
        
        # Add contact information
        if project.get('contacts'):
            message += "*Key Contacts:*\n"
            for contact in project['contacts']:
                message += f"• {contact['name']} - {contact['role']}\n"
                if contact.get('email'):
                    message += f"  Email: {contact['email']}\n"
                if contact.get('phone'):
                    message += f"  Phone: {contact['phone']}\n"
            message += "\n"
        
        # Source and additional info
        if project.get('source_url'):
            message += f"*Source:* {project['source_url']}\n"
        if project.get('description'):
            message += f"\n*Description:*\n{project['description'][:300]}..."
            
        return message
    
    def _send_whatsapp(self, message, max_retries=3):
        """Send WhatsApp message using Interakt API"""
        if not self.enabled:
            self.logger.error("Cannot send message: WhatsApp notifications not enabled")
            return False
            
        # Format phone number (remove + and any whitespace)
        phone = self.phone_number.strip().strip('+')
        
        # Prepare headers
        headers = {
            'Authorization': f'Basic {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        # Prepare payload according to Interakt API format
        payload = {
            "countryCode": "+91",  # Assuming Indian numbers
            "phoneNumber": phone,
            "callbackData": "project_notification",
            "type": "Text",  # Changed from Template to Text for direct messages
            "message": message
        }
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"Sending message to {phone} (Attempt {attempt + 1}/{max_retries})")
                
                response = requests.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )
                
                response_data = response.json()
                
                if response.status_code == 200 and response_data.get('status') == 'success':
                    self.logger.info(f"Successfully sent WhatsApp message to {phone}")
                    return True
                else:
                    error_msg = response_data.get('message', 'Unknown error')
                    self.logger.error(f"Failed to send WhatsApp message: {error_msg}")
                    if attempt < max_retries - 1:
                        self.logger.info(f"Will retry in {2 ** attempt} seconds")
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    self.logger.error(f"Failed to send WhatsApp after {max_retries} attempts: {str(e)}")
                else:
                    self.logger.warning(f"Attempt {attempt + 1} failed: {str(e)}, retrying...")
                continue
                
        return False 