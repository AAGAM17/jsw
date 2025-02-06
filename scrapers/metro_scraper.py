import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import logging
from urllib.parse import urljoin
import urllib3
import certifi

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class MetroScraper:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.base_url = 'https://themetrorailguy.com'
        
        # Configure session to use system CA certificates
        self.session.verify = certifi.where()
        
        # Configure retry strategy
        retry_strategy = urllib3.Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = requests.adapters.HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
    
    def scrape_latest_news(self):
        projects = []
        try:
            # Scrape main page and category pages
            urls = [
                f'{self.base_url}',
                f'{self.base_url}/category/tenders',
                f'{self.base_url}/category/contracts',
                f'{self.base_url}/category/news'
            ]
            
            twenty_days_ago = datetime.now() - timedelta(days=20)
            
            for url in urls:
                try:
                    response = self.session.get(
                        url,
                        timeout=30,
                        allow_redirects=True,
                        headers={
                            'Referer': self.base_url
                        }
                    )
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Find all article links
                    articles = soup.find_all('article')
                    for article in articles:
                        # Check article date
                        date_elem = article.find('time', class_='entry-date')
                        if date_elem and 'datetime' in date_elem.attrs:
                            try:
                                article_date = datetime.fromisoformat(date_elem['datetime'].replace('Z', '+00:00'))
                                if article_date < twenty_days_ago:
                                    continue
                            except Exception as e:
                                self.logger.error(f"Error parsing article date: {str(e)}")
                        
                        title_elem = article.find('h2', class_='entry-title')
                        if not title_elem or not title_elem.find('a'):
                            continue
                            
                        title = title_elem.text.strip()
                        link = title_elem.find('a')['href']
                        
                        # Check if title suggests a contract win or tender
                        keywords = [
                            'contract', 'tender', 'awarded', 'wins', 'selected', 'bidder', 'L1',
                            'order', 'project', 'construction', 'development', 'infrastructure'
                        ]
                        if any(keyword.lower() in title.lower() for keyword in keywords):
                            project = self._scrape_article(link, title)
                            if project:
                                # Add news date for priority calculation
                                project['news_date'] = article_date if date_elem else datetime.now()
                                projects.append(project)
                                
                except requests.exceptions.RequestException as e:
                    self.logger.error(f"Error fetching {url}: {str(e)}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error in scrape_latest_news: {str(e)}")
        
        return projects
    
    def _scrape_article(self, url, title):
        try:
            response = self.session.get(
                url,
                timeout=30,
                allow_redirects=True,
                headers={
                    'Referer': self.base_url
                }
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            content = soup.find('div', class_='entry-content')
            if not content:
                return None
                
            text = content.get_text()
            
            # Extract company name
            company_patterns = [
                r'([A-Za-z\s]+(?:Limited|Ltd|Corporation|Corp|Infrastructure|Infratech|Construction|Constructions|Engineering))',
                r'([A-Za-z\s]+) has been awarded',
                r'([A-Za-z\s]+) wins',
                r'contract to ([A-Za-z\s]+)',
                r'([A-Za-z\s]+) emerges',
                r'([A-Za-z\s]+) bags'
            ]
            
            company = None
            for pattern in company_patterns:
                if match := re.search(pattern, text):
                    company = match.group(1).strip()
                    break
            
            # Extract value
            value_patterns = [
                r'Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
                r'([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
                r'worth\s*Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)',
                r'value\s*of\s*Rs\.?\s*([\d,]+(?:\.\d+)?)\s*(?:cr|crore)'
            ]
            
            value = None
            for pattern in value_patterns:
                if match := re.search(pattern, text, re.IGNORECASE):
                    try:
                        value = float(match.group(1).replace(',', ''))
                        break
                    except ValueError:
                        continue
            
            # Extract dates
            date_patterns = [
                r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
                r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
                r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}'
            ]
            
            dates = []
            for pattern in date_patterns:
                dates.extend(re.findall(pattern, text))
            
            start_date = None
            end_date = None
            
            if dates:
                if len(dates) >= 2:
                    try:
                        start_date = datetime.strptime(dates[0], '%B %Y')
                    except ValueError:
                        try:
                            start_date = datetime.strptime(dates[0], '%d %B %Y')
                        except ValueError:
                            start_date = datetime.strptime(dates[0], '%b %Y')
                            
                    try:
                        end_date = datetime.strptime(dates[1], '%B %Y')
                    except ValueError:
                        try:
                            end_date = datetime.strptime(dates[1], '%d %B %Y')
                        except ValueError:
                            end_date = datetime.strptime(dates[1], '%b %Y')
                            
                elif len(dates) == 1:
                    try:
                        start_date = datetime.strptime(dates[0], '%B %Y')
                    except ValueError:
                        try:
                            start_date = datetime.strptime(dates[0], '%d %B %Y')
                        except ValueError:
                            start_date = datetime.strptime(dates[0], '%b %Y')
                            
                    end_date = start_date.replace(year=start_date.year + 3)  # Assume 3 years for completion
            
            if company and value:
                return {
                    'company': company,
                    'title': title.replace(company, '').strip('. '),
                    'value': value,
                    'start_date': start_date or datetime.now(),
                    'end_date': end_date or datetime.now().replace(year=datetime.now().year + 3),
                    'source_url': url,
                    'description': text[:500]  # First 500 chars as description
                }
            
        except Exception as e:
            self.logger.error(f"Error scraping article {url}: {str(e)}")
        
        return None 