"""
Menu content analyzer for detecting menu types and temporal patterns.
Analyzes scraped menu content to determine if menus are daily, weekly, static, or mixed.
"""

import re
from typing import Dict, List, Any
from datetime import datetime


def detect_menu_type(content: str) -> Dict[str, Any]:
    """
    Analyze menu content to detect menu type and temporal patterns.
    
    Args:
        content: Raw scraped menu text content
        
    Returns:
        Dict containing:
            - menu_type: str (daily/weekly/static/mixed/unknown)
            - detected_days: List[str] of day names found
            - confidence: float (0.0-1.0)
            - indicators: Dict of detected patterns
    """
    if not content or len(content.strip()) < 50:
        return {
            "menu_type": "unknown",
            "detected_days": [],
            "confidence": 0.0,
            "indicators": {"reason": "insufficient_content"}
        }
    
    content_lower = content.lower()
    
    # Day name patterns (English and German)
    day_patterns = {
        "monday": [r'\bmonday\b', r'\bmontag\b', r'\bmo\b'],
        "tuesday": [r'\btuesday\b', r'\bdienstag\b', r'\bdi\b', r'\btue\b'],
        "wednesday": [r'\bwednesday\b', r'\bmittwoch\b', r'\bmi\b', r'\bwed\b'],
        "thursday": [r'\bthursday\b', r'\bdonnerstag\b', r'\bdo\b', r'\bthu\b'],
        "friday": [r'\bfriday\b', r'\bfreitag\b', r'\bfr\b', r'\bfri\b'],
        "saturday": [r'\bsaturday\b', r'\bsamstag\b', r'\bsa\b', r'\bsat\b'],
        "sunday": [r'\bsunday\b', r'\bsonntag\b', r'\bso\b', r'\bsun\b']
    }
    
    # Detect which days are mentioned
    detected_days = []
    day_mention_count = 0
    
    for day, patterns in day_patterns.items():
        for pattern in patterns:
            if re.search(pattern, content_lower):
                if day not in detected_days:
                    detected_days.append(day)
                day_mention_count += len(re.findall(pattern, content_lower))
                break
    
    # Daily menu indicators
    daily_indicators = [
        r'\bdaily\b', r'\btäglich\b', r'\btoday\b', r'\bheute\b',
        r'\bdaily special\b', r'\btagesgericht\b', r'\btagesmenü\b',
        r'\btageskarte\b', r'\bspecial of the day\b'
    ]
    daily_count = sum(len(re.findall(pattern, content_lower)) for pattern in daily_indicators)
    
    # Weekly menu indicators
    weekly_indicators = [
        r'\bweekly\b', r'\bwöchentlich\b', r'\bwoche\b', r'\bweek\b',
        r'\bwochenkarte\b', r'\bweekly menu\b', r'\bthis week\b',
        r'\bdiese woche\b', r'\bkw\s*\d+\b'  # Calendar week
    ]
    weekly_count = sum(len(re.findall(pattern, content_lower)) for pattern in weekly_indicators)
    
    # Static menu indicators
    static_indicators = [
        r'\bmenu\b', r'\bspeisekarte\b', r'\bour dishes\b',
        r'\bappetizers\b', r'\bmain courses\b', r'\bdesserts\b',
        r'\bvorspeisen\b', r'\bhauptspeisen\b', r'\bnachspeisen\b'
    ]
    static_count = sum(len(re.findall(pattern, content_lower)) for pattern in static_indicators)
    
    # Date patterns (indicates temporal menus)
    date_patterns = [
        r'\d{1,2}\.\d{1,2}\.\d{2,4}',  # DD.MM.YYYY or DD.MM.YY
        r'\d{1,2}/\d{1,2}/\d{2,4}',    # MM/DD/YYYY
        r'\d{4}-\d{2}-\d{2}',           # YYYY-MM-DD
        r'\b\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',  # 15 Jan
        r'\b\d{1,2}\.\s*(?:januar|februar|märz|april|mai|juni|juli|august|september|oktober|november|dezember)'
    ]
    date_count = sum(len(re.findall(pattern, content_lower)) for pattern in date_patterns)
    
    # Analyze patterns and determine menu type
    indicators = {
        "daily_mentions": daily_count,
        "weekly_mentions": weekly_count,
        "static_mentions": static_count,
        "date_mentions": date_count,
        "days_found": len(detected_days),
        "day_mention_count": day_mention_count
    }
    
    # Decision logic
    confidence = 0.0
    menu_type = "unknown"
    
    # Strong daily indicators
    if daily_count >= 3 or (daily_count >= 1 and date_count >= 2):
        menu_type = "daily"
        confidence = min(0.9, 0.5 + (daily_count * 0.1) + (date_count * 0.05))
    
    # Strong weekly indicators
    elif len(detected_days) >= 5 or weekly_count >= 2:
        menu_type = "weekly"
        confidence = min(0.95, 0.6 + (len(detected_days) * 0.05) + (weekly_count * 0.1))
    
    # Mixed indicators (both daily specials and regular menu)
    elif (daily_count >= 1 or len(detected_days) >= 3) and static_count >= 3:
        menu_type = "mixed"
        confidence = 0.7
    
    # Moderate weekly indicators
    elif len(detected_days) >= 3:
        menu_type = "weekly"
        confidence = 0.5 + (len(detected_days) * 0.05)
    
    # Static menu (no temporal indicators)
    elif static_count >= 2 and daily_count == 0 and len(detected_days) <= 1:
        menu_type = "static"
        confidence = min(0.8, 0.4 + (static_count * 0.1))
    
    # Fallback to unknown if confidence is too low
    if confidence < 0.3:
        menu_type = "unknown"
        confidence = 0.2
    
    return {
        "menu_type": menu_type,
        "detected_days": detected_days,
        "confidence": round(confidence, 2),
        "indicators": indicators
    }


def extract_menu_metadata(content: str) -> Dict[str, Any]:
    """
    Extract comprehensive metadata from menu content.
    
    Args:
        content: Raw scraped menu text content
        
    Returns:
        Dict containing menu_type, detected_days, and other metadata
    """
    analysis = detect_menu_type(content)
    
    # Additional metadata
    word_count = len(content.split())
    char_count = len(content)
    
    # Detect price indicators (helps determine if it's a real menu)
    price_patterns = [r'€\s*\d+', r'\d+[,\.]\d{2}\s*€', r'\$\s*\d+', r'\d+[,\.]\d{2}\s*\$']
    price_count = sum(len(re.findall(pattern, content)) for pattern in price_patterns)
    
    return {
        "menu_type": analysis["menu_type"],
        "detected_days": analysis["detected_days"],
        "confidence": analysis["confidence"],
        "word_count": word_count,
        "char_count": char_count,
        "has_prices": price_count > 0,
        "price_count": price_count,
        "analysis_timestamp": datetime.utcnow().isoformat(),
        "indicators": analysis["indicators"]
    }
