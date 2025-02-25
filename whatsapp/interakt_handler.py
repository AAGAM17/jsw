"""Interakt WhatsApp handler for sending project notifications."""

import logging
from datetime import datetime, timedelta
import requests
from config.settings import Config
import time
import base64
import re

class InteraktHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.api_key = Config.INTERAKT_API_KEY
        # List of phone numbers to send notifications to
        self.phone_numbers = ["918484926925", "917715018407"]
        self.base_url = "https://api.interakt.ai/v1/public/message/"
        self.enabled = bool(self.api_key and self.phone_numbers)
        
        # Initialize Perplexity client
        from scrapers.perplexity_client import PerplexityClient
        self.perplexity = PerplexityClient()
        
        # Store project context
        self.project_context = {}
        
        if self.enabled:
            self.logger.info(f"Interakt WhatsApp notifications enabled. Target numbers: {', '.join(self.phone_numbers)}")
            # Validate API key format
            if not self._is_valid_api_key(self.api_key):
                self.logger.error("Invalid API key format")
                self.enabled = False
        else:
            self.logger.error("Interakt configuration incomplete")
    
    def _is_valid_api_key(self, api_key):
        """Validate if the API key is properly base64 encoded"""
        try:
            # Try to decode the API key
            decoded = base64.b64decode(api_key).decode('utf-8')
            return ':' in decoded  # Basic auth typically contains a colon
        except Exception:
            return False
            
    def _format_phone_number(self, phone):
        """Format phone number to match Interakt requirements"""
        # Remove all non-digit characters
        clean_number = ''.join(filter(str.isdigit, phone))
        
        # Validate length (assuming Indian numbers)
        if len(clean_number) < 10 or len(clean_number) > 12:
            self.logger.error(f"Invalid phone number length: {len(clean_number)} digits")
            return None
            
        # Ensure it has country code
        if len(clean_number) == 10:
            clean_number = '91' + clean_number
        elif not clean_number.startswith('91'):
            self.logger.error("Phone number must be an Indian number starting with 91")
            return None
            
        return clean_number
    
    def handle_incoming_message(self, phone_number, message_text):
        """Handle incoming WhatsApp messages using Perplexity AI"""
        try:
            self.logger.info(f"Received message from {phone_number}: {message_text}")
            
            # Get project context for this user
            context = self.project_context.get(phone_number, {})
            
            # Prepare context for AI
            ai_context = ""
            if context:
                ai_context = f"""
                Project Context:
                Title: {context.get('title')}
                Company: {context.get('company')}
                Value: ₹{context.get('value', 0)} Crore
                Description: {context.get('description')}
                Steel Requirements: {context.get('steel_requirements', {})}
                Start Date: {context.get('start_date')}
                End Date: {context.get('end_date')}
                Source: {context.get('source_url')}
                """
            
            # Add system context
            ai_context += """
            You are a helpful AI assistant for JSW Steel's project discovery system. 
            You help users understand project details, steel requirements, and procurement opportunities.
            Keep responses concise and focused on steel/construction aspects.
            If you don't have enough context, ask for clarification.
            """
            
            # Get AI response
            response = self.perplexity.get_project_info(ai_context + "\n\nUser question: " + message_text)
            
            # Send response back via WhatsApp
            self._send_whatsapp_response(phone_number, response)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling incoming message: {str(e)}")
            error_msg = "Sorry, I encountered an error processing your message. Please try again."
            self._send_whatsapp_response(phone_number, error_msg)
            return False
            
    def _send_whatsapp_response(self, phone_number, message):
        """Send WhatsApp response to a specific number"""
        try:
            headers = {
                'Authorization': f'Basic {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "userId": f"chat_{phone_number}",
                "fullPhoneNumber": phone_number,
                "campaignId": "festive_giveaway",
                "type": "Text",
                "data": {
                    "message": message
                }
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.json().get('result') is True:
                self.logger.info(f"Response sent successfully to {phone_number}")
                return True
            else:
                self.logger.error(f"Failed to send response to {phone_number}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending WhatsApp response: {str(e)}")
            return False
    
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
        try:
            message = f"*Project #{idx} Details*\n\n"
            
            # Basic info
            message += f"*Company:* {project.get('company', 'N/A')}\n"
            message += f"*Project:* {project.get('title', 'N/A')}\n\n"
            
            # Value and timeline
            if project.get('value'):
                message += f"*Value:* ₹{float(project['value']):.1f} Crore\n"
            
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
                        elif isinstance(value, (int, float)):
                            message += f"• {key}: {value:,} MT\n"
                message += "\n"
            
            # Add contact information
            if project.get('contacts'):
                message += "*Key Contacts:*\n"
                for contact in project['contacts']:
                    message += f"• {contact.get('name', 'N/A')} - {contact.get('role', 'N/A')}\n"
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
            
        except Exception as e:
            self.logger.error(f"Error formatting project message: {str(e)}")
            return f"Error formatting project #{idx}. Please check the logs."

    def test_project_message(self):
        """Test sending a real project message"""
        test_project = {
            'title': 'Test Project - Metro Construction',
            'company': 'ABC Constructions',
            'value': 850.5,
            'description': 'Major metro construction project in Mumbai',
            'start_date': datetime.now(),
            'end_date': datetime.now() + timedelta(days=365),
            'steel_requirements': {
                'primary': {'type': 'TMT Bars', 'quantity': 12000},
                'secondary': {'type': 'HR Plates', 'quantity': 6000},
                'total': 18000
            },
            'contacts': [{
                'name': 'Rajesh Kumar',
                'role': 'Procurement Manager',
                'email': 'rajesh.k@abcconstructions.com',
                'phone': '+91 98765 43210'
            }],
            'source_url': 'https://example.com/project'
        }
        
        # Format the message
        message = self._format_project_message(test_project, 1)
        
        # Send it using a template message
        payload = {
            "phoneNumber": self.phone_numbers[0],
            "countryCode": "91",
            "type": "Template",
            "template": {
                "name": "project_update",
                "languageCode": "en",
                "bodyValues": [
                    test_project['title'],
                    test_project['company'],
                    f"₹{test_project['value']:.1f} Crore",
                    test_project['description'][:100] + "..."
                ]
            }
        }
        
        headers = {
            'Authorization': f'Basic {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        try:
            self.logger.info("Sending test project message...")
            self.logger.debug(f"Using template with payload:\n{payload}")
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            self.logger.info(f"Response Status: {response.status_code}")
            self.logger.info(f"Response Body: {response.text}")
            
            response_data = response.json()
            if response_data.get('result') is True and response_data.get('id'):
                self.logger.info(f"Project message queued successfully with ID: {response_data['id']}")
                return True
            else:
                self.logger.error(f"Failed to send project message: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending test project message: {str(e)}")
            return False

    def send_project_opportunities(self, projects):
        """Send a batch of project opportunities via WhatsApp.
        
        Args:
            projects (list): List of project dictionaries containing project details
            
        Returns:
            bool: True if all messages were sent successfully, False otherwise
        """
        self.logger.info(f"Sending {len(projects)} project opportunities via WhatsApp")
        
        # JSW filtering terms
        jsw_terms = [
            'jsw', 'jindal', 'js steel', 'jsw steel', 'jindal steel',
            'jsw neosteel', 'jsw trusteel', 'neosteel', 'trusteel',
            'jsw fastbuild', 'jsw galvalume', 'jsw coated'
        ]
        
        success = True
        for project in projects:
            try:
                # Skip JSW-related projects
                title = str(project.get('title', '')).lower()
                desc = str(project.get('description', '')).lower()
                company = str(project.get('company', '')).lower()
                all_text = f"{title} {desc} {company}"
                
                if any(term in all_text for term in jsw_terms):
                    self.logger.info(f"Skipping JSW-related project: {project.get('title')}")
                    continue
                
                result = self._send_whatsapp(
                    template_name="project_update",
                    template_language="en",
                    template_body_values=[
                        project.get("title", "Untitled Project"),
                        project.get("company", "Unknown Company"), 
                        str(project.get("value", "Unknown Value")),
                        project.get("description", "No description available")
                    ]
                )
                if not result:
                    self.logger.error(f"Failed to send project: {project.get('title')}")
                    success = False
            except Exception as e:
                self.logger.error(f"Error sending project {project.get('title')}: {str(e)}")
                success = False
                
        return success
