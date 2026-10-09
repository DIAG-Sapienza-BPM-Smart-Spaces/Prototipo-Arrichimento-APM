import re

# Known typos in the data (extracted from the 300-row dataset)
TYPO_MAP = {
    "EFFETTURARE": "EFFETTUARE",
    "EFFETTURATO": "EFFETTUATO",
    "DIPSONIBILITA": "DISPONIBILITA",
    "MANICOTO": "MANICOTTO",
    "PENUMATICO": "PNEUMATICO",
    "RISCONTATO": "RISCONTRATO",
    "NESUNA": "NESSUNA",
    "RIRPSITINO": "RIPRISTINO",
}

# Known abbreviations
ABBREVIATION_MAP = {
    r'\bSOST\.': 'SOSTITUZIONE ',
    r'\bSOST\b': 'SOSTITUZIONE',
    r'\bRIP\.': 'RIPARAZIONE ',
    r'\bCONT\.': 'CONTROLLO ',
    r'\bMANUT\.': 'MANUTENZIONE ',
    r'POSIZIONAM\.': 'POSIZIONAMENTO ',
    r'\bS/R\b': 'SMONTAGGIO RIMONTAGGIO',
}


def clean_text(text: str) -> str:
    """
    Formats the raw text so the LLM can understand it better.
    Fixes typos, expands abbreviations, removes unnecessary information.
    """
    if not isinstance(text, str) or text.strip() == "" or text.lower() == "nan":
        return ""
    
    # 1. Convert to uppercase
    text = text.upper()
    
    # 2. Tabs and line breaks → space
    text = text.replace("\t", " ").replace("\n", " ").replace("\r", " ")
    
    # 3. Leading activity codes (6-digit number, e.g., 200310)
    text = re.sub(r'^\d{6}\s*', '', text)
    
    # 4. Clean URLs
    text = re.sub(r'HTTP\S+', '', text)
    
    # 5. Clean duration information (0.5 H or 1.30 ORE)
    text = re.sub(r'\d+[,.]\d+\s*(?:H|ORE)\b', '', text)
    
    # 6. Fix typos
    for wrong, right in TYPO_MAP.items():
        text = text.replace(wrong, right)
    
    # 7. Expand abbreviations (with regex)
    for pattern, replacement in ABBREVIATION_MAP.items():
        text = re.sub(pattern, replacement, text)
    
    # 8. Clean unnecessary special characters but keep commas, dots, dashes, slashes
    text = re.sub(r'[^\w\s\.\/,-]', ' ', text)
    
    # 9. Multiple spaces → single space
    text = " ".join(text.split())
    
    return text
