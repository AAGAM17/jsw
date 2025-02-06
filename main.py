import logging
from apscheduler.schedulers.blocking import BlockingScheduler # type: ignore
from scrapers.perplexity_client import PerplexityClient
from scrapers.metro_scraper import MetroScraper
from whatsapp.twilio_client import TwilioClient
from utilities.email_handler import EmailHandler
from utilities.logger import configure_logging
from datetime import datetime
from config.settings import Config

configure_logging()

def run_pipeline():
    """Main data processing pipeline"""
    logger = logging.getLogger(__name__)
    logger.info("Starting AI-powered project discovery pipeline...")
    
    try:
        # Initialize components
        perplexity = PerplexityClient()
        metro_scraper = MetroScraper()
        whatsapp = TwilioClient()
        email_handler = EmailHandler()
        
        # Get projects from both sources
        logger.info("Scraping themetrorailguy.com...")
        metro_projects = metro_scraper.scrape_latest_news()
        logger.info(f"Found {len(metro_projects)} projects from Metro Rail Guy")
        
        logger.info("Discovering projects using Perplexity AI...")
        ai_projects = perplexity.research_infrastructure_projects()
        logger.info(f"Found {len(ai_projects)} projects from Perplexity")
        
        # Combine projects and remove duplicates
        all_projects = []
        seen_titles = set()
        
        for project in metro_projects + ai_projects:
            # Create a normalized title for comparison
            norm_title = ' '.join(project['title'].lower().split())
            if norm_title not in seen_titles:
                seen_titles.add(norm_title)
                # Add news date for priority calculation
                project['news_date'] = datetime.now()
                all_projects.append(project)
        
        logger.info(f"Total unique projects found: {len(all_projects)}")
        
        if not all_projects:
            logger.warning("No projects found - check sources")
            return
        
        # Sort projects by priority
        def priority_score(project):
            now = datetime.now()
            start_date = project.get('start_date', now)
            days_to_start = max((start_date - now).days, 1)  # Ensure minimum 1 day
            
            time_score = (1 / days_to_start) * Config.PRIORITY_WEIGHTS['time_factor']
            value_score = (project.get('value', 0) / 1000) * Config.PRIORITY_WEIGHTS['value_factor']
            
            return time_score + value_score
        
        sorted_projects = sorted(all_projects, key=priority_score, reverse=True)
        
        # Send notifications
        logger.info("Sending notifications...")
        
        # Send WhatsApp messages to general recipients
        if Config.RECIPIENTS:
            for project in sorted_projects:
                if project.get('company') and project.get('value'):
                    project_message = (
                        f"*{project['company']} wins {project['title']}*\n\n"
                        f"Project is going to start from {project.get('start_date', datetime.now()).strftime('%B %Y')} "
                        f"and end by {project.get('end_date', datetime.now()).strftime('%B %Y')}.\n\n"
                        f"Contract Value: Rs. {project.get('value', 0):,.0f} Cr\n"
                        f"Est. Steel Requirement: {project.get('steel_requirement', 0):,.0f} MT\n\n"
                    )
                    
                    if project.get('source_url'):
                        project_message += f"Source: {project['source_url']}"
                    elif project.get('announcement_url'):
                        project_message += f"Source: {project['announcement_url']}"
                    
                    whatsapp.send_whatsapp(project_message)
                    logger.info("Sent WhatsApp message")
        
        # Send team-specific emails
        logger.info("Sending team-specific emails...")
        email_handler.send_project_opportunities(sorted_projects)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)

if __name__ == "__main__":
    scheduler = BlockingScheduler()
    # Run immediately when starting
    run_pipeline()
    # Then schedule future runs
    scheduler.add_job(run_pipeline, 'interval', hours=6, misfire_grace_time=3600)
    print("Starting scheduler... (Ctrl+C to exit)")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print("Scheduler stopped")