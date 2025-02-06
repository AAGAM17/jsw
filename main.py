import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from scrapers.perplexity_client import PerplexityClient
from scrapers.metro_scraper import MetroScraper
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
        email_handler = EmailHandler()
        
        # Get projects from both sources
        logger.info("Scraping themetrorailguy.com...")
        metro_projects = metro_scraper.scrape_latest_news()
        logger.info(f"Found {len(metro_projects)} projects from Metro Rail Guy")
        
        logger.info("Discovering projects using Perplexity AI...")
        ai_projects = perplexity.research_infrastructure_projects()
        logger.info(f"Found {len(ai_projects)} projects from Perplexity")
        
        # Combine all projects
        all_projects = metro_projects + ai_projects
        
        # Add news date for priority calculation
        for project in all_projects:
            project['news_date'] = datetime.now()
        
        logger.info(f"Total projects found: {len(all_projects)}")
        
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
        
        # Send consolidated email with all projects
        logger.info("Sending consolidated project opportunities email...")
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