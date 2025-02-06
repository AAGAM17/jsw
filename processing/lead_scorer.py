from datetime import datetime
from config.settings import Config

class LeadScorer:
    def __init__(self):
        self.current_year = datetime.now().year
        
    def score_lead(self, project):
        """Calculate lead score 0-100 based on multiple factors"""
        score = 0
        
        # Budget scoring
        if project['budget'] >= Config.BUDGET_THRESHOLD:
            score += Config.BUDGET_WEIGHT * 100
            
        # Timeline scoring
        years_diff = project['start_date'].year - self.current_year
        if years_diff <= 1:
            score += Config.TIMELINE_WEIGHT * (100 - (years_diff * 30))
            
        # Phase scoring
        phase_score = self._calculate_phase_score(project['description'])
        score += Config.PHASE_WEIGHT * phase_score
        
        # Keyword scoring
        keyword_score = len(project['keywords']) * 10
        score += Config.KEYWORD_WEIGHT * keyword_score
        
        return min(100, max(0, round(score)))

    def _calculate_phase_score(self, description):
        """Score based on project phase mentioning steel requirements"""
        phase_keywords = {
            'initial': ['foundation', 'excavation', 'structural'],
            'mid': ['concrete', 'cement', 'formwork'],
            'final': ['painting', 'finishing']
        }
        
        if any(kw in description.lower() for kw in phase_keywords['initial']):
            return 80  # Highest score for steel-relevant phases
        elif any(kw in description.lower() for kw in phase_keywords['mid']):
            return 40
        else:
            return 20