from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from groq import Groq
from dotenv import load_dotenv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import hashlib
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Cache des résultats (évite de re-analyser les mêmes URLs)
analysis_cache = {}
CACHE_DURATION = timedelta(hours=24)

# Catégories de mots-clés optimisées avec scoring
KEYWORD_CATEGORIES = {
    "🍪 Cookies & Tracking": {
        "keywords": ["cookie", "tracking pixel", "web beacon", "analytics", "local storage", 
                    "session storage", "fingerprint", "identifier"],
        "weight": 1.5,
        "critical": ["tracking pixel", "fingerprint"]
    },
    "🔐 Données Personnelles": {
        "keywords": ["personal data", "personal information", "personally identifiable", 
                    "sensitive data", "biometric", "health data", "financial data",
                    "données personnelles", "informations personnelles"],
        "weight": 2.0,
        "critical": ["sensitive data", "biometric", "health data", "financial data"]
    },
    "👥 Partage & Vente": {
        "keywords": ["third part", "share", "disclose", "transfer", "sell your", 
                    "sell personal", "partners", "affiliates", "vendors"],
        "weight": 2.5,
        "critical": ["sell your", "sell personal"]
    },
    "✅ Droits Utilisateur": {
        "keywords": ["right to access", "right to delete", "right to opt-out", 
                    "withdraw consent", "data portability", "right to object",
                    "droit d'accès", "droit de suppression"],
        "weight": 1.8,
        "critical": ["right to delete", "opt-out"]
    },
    "⏰ Conservation": {
        "keywords": ["retain", "retention period", "keep your data", "store for",
                    "delete after", "data retention"],
        "weight": 1.5,
        "critical": ["indefinitely", "permanent"]
    },
    "🔒 Sécurité": {
        "keywords": ["encrypt", "encryption", "secure", "ssl", "https", "tls",
                    "security measures", "protect your data"],
        "weight": 1.2,
        "critical": []
    },
    "📢 Marketing": {
        "keywords": ["marketing", "advertisement", "promotional", "targeted ads",
                    "email marketing", "newsletter"],
        "weight": 1.3,
        "critical": ["targeted ads"]
    },
    "🌍 Transferts Internationaux": {
        "keywords": ["transfer", "international", "outside", "european union",
                    "united states", "data transfer", "cross-border"],
        "weight": 2.0,
        "critical": ["outside european union"]
    },
    "⚖️ Conformité Légale": {
        "keywords": ["gdpr", "ccpa", "privacy shield", "data protection act",
                    "regulation", "compliance"],
        "weight": 1.8,
        "critical": ["gdpr", "ccpa"]
    }
}

# Patterns pour extraire des informations structurées
EXTRACTION_PATTERNS = {
    "retention_periods": r"(?:retain|store|keep).*?(?:for|during)\s+(\d+\s+(?:days|months|years))",
    "data_types": r"(?:collect|gather|obtain).*?(email|name|address|phone|ip address|location|payment)",
    "sharing_entities": r"(?:share|disclose|transfer).*?(?:with|to)\s+([\w\s]+?)(?:,|\.|\s+to)",
}

def get_cache_key(url):
    """Génère une clé de cache pour l'URL"""
    return hashlib.md5(url.encode()).hexdigest()

def is_cache_valid(cache_entry):
    """Vérifie si le cache est encore valide"""
    if not cache_entry:
        return False
    timestamp = cache_entry.get("timestamp")
    if not timestamp:
        return False
    return datetime.now() - timestamp < CACHE_DURATION

@lru_cache(maxsize=100)
def fetch_page_content(url):
    """Récupère le contenu d'une page avec cache"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        
        response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        response.raise_for_status()
        
        # Parser avec BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Supprimer les éléments non pertinents
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe']):
            element.decompose()
        
        # Extraire le texte
        text = soup.get_text(separator=' ', strip=True)
        
        # Nettoyer le texte
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[\r\n]+', '\n', text)
        
        return text[:15000]  # Limiter à 15k caractères
        
    except requests.Timeout:
        print(f"⏱️ Timeout pour {url}")
        return ""
    except requests.RequestException as e:
        print(f"❌ Erreur réseau pour {url}: {e}")
        return ""
    except Exception as e:
        print(f"❌ Erreur inattendue pour {url}: {e}")
        return ""

def score_keyword_match(text_lower, keyword):
    """Calcule un score de pertinence pour un mot-clé"""
    count = text_lower.count(keyword)
    
    # Bonus si le mot-clé apparaît dans un contexte important
    context_patterns = [
        rf"we\s+\w+\s+{keyword}",
        rf"your\s+{keyword}",
        rf"{keyword}\s+(?:is|are)\s+(?:collected|used|shared)",
    ]
    
    context_bonus = sum(1 for pattern in context_patterns if re.search(pattern, text_lower))
    
    return count + (context_bonus * 0.5)

def analyze_keywords_advanced(text):
    """Analyse avancée par mots-clés avec scoring"""
    text_lower = text.lower()
    results = {}
    risk_score = 0
    
    for category, config in KEYWORD_CATEGORIES.items():
        keywords = config["keywords"]
        weight = config["weight"]
        critical = config["critical"]
        
        found_items = []
        category_score = 0
        
        for keyword in keywords:
            score = score_keyword_match(text_lower, keyword)
            if score > 0:
                is_critical = keyword in critical
                found_items.append({
                    "keyword": keyword,
                    "count": int(score),
                    "critical": is_critical
                })
                
                # Calculer le score de risque
                item_risk = score * weight
                if is_critical:
                    item_risk *= 2
                category_score += item_risk
        
        if found_items:
            # Trier par pertinence
            found_items.sort(key=lambda x: (x["critical"], x["count"]), reverse=True)
            results[category] = {
                "items": found_items[:5],  # Top 5
                "score": category_score
            }
            risk_score += category_score
    
    return results, risk_score

def extract_structured_data(text):
    """Extrait des données structurées du texte"""
    extracted = {}
    
    # Périodes de rétention
    retention_matches = re.findall(EXTRACTION_PATTERNS["retention_periods"], text, re.IGNORECASE)
    if retention_matches:
        extracted["retention_periods"] = list(set(retention_matches[:3]))
    
    # Types de données
    data_matches = re.findall(EXTRACTION_PATTERNS["data_types"], text, re.IGNORECASE)
    if data_matches:
        extracted["data_types"] = list(set(data_matches[:5]))
    
    # Entités de partage
    sharing_matches = re.findall(EXTRACTION_PATTERNS["sharing_entities"], text, re.IGNORECASE)
    if sharing_matches:
        # Nettoyer les résultats
        cleaned = [s.strip() for s in sharing_matches if len(s.strip()) > 3]
        extracted["sharing_entities"] = list(set(cleaned[:5]))
    
    return extracted

def extract_critical_sentences(text):
    """Extrait les phrases les plus importantes"""
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    
    # Patterns de phrases critiques
    critical_patterns = [
        (r"we\s+(?:may\s+)?sell", 3.0),  # Vente de données
        (r"share.*?with.*?third part", 2.5),  # Partage avec tiers
        (r"you.*?right to", 2.0),  # Droits utilisateur
        (r"we\s+(?:collect|gather|obtain)", 1.8),  # Collection de données
        (r"(?:retain|store|keep).*?(?:for|until)", 1.5),  # Rétention
        (r"(?:encrypt|security|protect)", 1.3),  # Sécurité
    ]
    
    scored_sentences = []
    
    for sentence in sentences:
        if len(sentence) < 40 or len(sentence) > 400:
            continue
        
        score = 0
        for pattern, weight in critical_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                score += weight
        
        if score > 0:
            scored_sentences.append((sentence, score))
    
    # Trier par score et retourner les meilleures
    scored_sentences.sort(key=lambda x: x[1], reverse=True)
    return [s[0] for s in scored_sentences[:5]]

def summarize_with_groq(text, url):
    """Génère un résumé avec Groq"""
    if not groq_client:
        return None
    
    try:
        domain = url.split('/')[2] if '/' in url else url
        
        prompt = f"""Analyse cette politique de confidentialité et fournis un résumé en français.

Politique de {domain}:
{text[:3000]}

Fournis un résumé structuré avec:
1. 🎯 Objectif principal de la politique (1 ligne)
2. ⚠️ Points d'attention (2-3 points critiques maximum)
3. ✅ Points positifs (si pertinents, 1-2 maximum)

Sois concis, précis et direct. Utilise un langage simple."""

        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Tu es un expert en protection des données qui analyse les politiques de confidentialité de manière critique et objective."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"❌ Erreur Groq: {e}")
        return None

def calculate_privacy_score(risk_score, has_gdpr, has_encryption, has_deletion_rights):
    """Calcule un score de confidentialité (0-100, 100 = meilleur)"""
    base_score = 100
    
    # Pénalités basées sur le risque
    penalty = min(risk_score * 2, 60)
    score = base_score - penalty
    
    # Bonus pour les bonnes pratiques
    if has_gdpr:
        score += 10
    if has_encryption:
        score += 5
    if has_deletion_rights:
        score += 5
    
    return max(0, min(100, int(score)))

def detect_document_type(url, content):
    """Détecte le type de document analysé"""
    url_lower = url.lower()
    content_lower = content[:2000].lower()
    
    # Vérifications par URL
    if any(x in url_lower for x in ['privacy', 'confidentialite', 'donnees-personnelles']):
        return "🔐 Politique de Confidentialité"
    elif any(x in url_lower for x in ['terms', 'conditions', 'cgu', 'cgv']):
        return "📜 Conditions d'Utilisation"
    elif any(x in url_lower for x in ['cookie', 'cookies']):
        return "🍪 Politique de Cookies"
    elif any(x in url_lower for x in ['legal', 'mentions-legales']):
        return "⚖️ Mentions Légales"
    elif any(x in url_lower for x in ['content', 'guidelines', 'community']):
        return "📝 Règles de Contenu"
    
    # Vérifications par contenu
    privacy_keywords = ['personal data', 'données personnelles', 'privacy policy', 'we collect']
    terms_keywords = ['terms of service', 'conditions générales', 'user agreement', 'you agree']
    cookie_keywords = ['cookie policy', 'we use cookies', 'tracking technologies']
    
    privacy_score = sum(1 for k in privacy_keywords if k in content_lower)
    terms_score = sum(1 for k in terms_keywords if k in content_lower)
    cookie_score = sum(1 for k in cookie_keywords if k in content_lower)
    
    max_score = max(privacy_score, terms_score, cookie_score)
    
    if max_score == privacy_score and privacy_score > 0:
        return "🔐 Politique de Confidentialité"
    elif max_score == terms_score and terms_score > 0:
        return "📜 Conditions d'Utilisation"
    elif max_score == cookie_score and cookie_score > 0:
        return "🍪 Politique de Cookies"
    
    return "📄 Document Légal"

def generate_comprehensive_summary(url, content, keyword_analysis, risk_score, structured_data, critical_sentences, ai_summary):
    """Génère un résumé complet et structuré"""
    domain = url.split('/')[2] if '/' in url else url
    doc_type = detect_document_type(url, content)
    
    # Extraire le chemin pour plus de contexte
    path_parts = url.split('/')
    path_hint = ""
    if len(path_parts) > 3:
        # Prendre les 2 derniers segments du chemin (ex: /content/privacy.html)
        relevant_path = '/'.join(path_parts[-2:])
        if len(relevant_path) > 40:
            relevant_path = relevant_path[-40:]
        path_hint = f" ({relevant_path})"
    
    # Calculer le score de confidentialité
    text_lower = content.lower()
    has_gdpr = "gdpr" in text_lower
    has_encryption = "encrypt" in text_lower
    has_deletion = "right to delete" in text_lower or "right to erasure" in text_lower
    
    privacy_score = calculate_privacy_score(risk_score, has_gdpr, has_encryption, has_deletion)
    
    # Déterminer le niveau de risque
    if privacy_score >= 70:
        risk_level = "🟢 FAIBLE"
        risk_emoji = "✅"
    elif privacy_score >= 40:
        risk_level = "🟡 MODÉRÉ"
        risk_emoji = "⚠️"
    else:
        risk_level = "🔴 ÉLEVÉ"
        risk_emoji = "⛔"
    
    lines = [
        f"{'='*70}",
        f"{doc_type.upper()}",
        f"🌐 Site: {domain}{path_hint}",
        f"{'='*70}",
        f"",
        f"{risk_emoji} SCORE DE CONFIDENTIALITÉ: {privacy_score}/100 - Risque {risk_level}",
        f""
    ]
    
    # Résumé IA si disponible
    if ai_summary:
        lines.append(f"🤖 RÉSUMÉ INTELLIGENT:")
        lines.append(f"{ai_summary}")
        lines.append(f"")
    
    # Analyse par catégories
    if keyword_analysis:
        lines.append(f"🔍 ANALYSE DÉTAILLÉE:")
        lines.append(f"")
        
        # Trier les catégories par score (plus risqué en premier)
        sorted_categories = sorted(
            keyword_analysis.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )
        
        for category, data in sorted_categories[:5]:  # Top 5 catégories
            items = data["items"]
            lines.append(f"{category}")
            
            for item in items[:3]:  # Top 3 items par catégorie
                critical_marker = "⚠️ " if item["critical"] else ""
                lines.append(f"  • {critical_marker}{item['keyword']} ({item['count']}x)")
            
            lines.append(f"")
    
    # Données structurées extraites
    if structured_data:
        lines.append(f"📊 INFORMATIONS CLÉS:")
        lines.append(f"")
        
        if "data_types" in structured_data:
            lines.append(f"  Données collectées: {', '.join(structured_data['data_types'])}")
        
        if "retention_periods" in structured_data:
            lines.append(f"  Durées de rétention: {', '.join(structured_data['retention_periods'])}")
        
        if "sharing_entities" in structured_data:
            lines.append(f"  Partage avec: {', '.join(structured_data['sharing_entities'][:3])}")
        
        lines.append(f"")
    
    # Phrases critiques
    if critical_sentences:
        lines.append(f"⚠️ EXTRAITS IMPORTANTS:")
        lines.append(f"")
        
        for i, sentence in enumerate(critical_sentences[:3], 1):
            # Tronquer si trop long
            display = sentence[:250] + "..." if len(sentence) > 250 else sentence
            lines.append(f"{i}. \"{display}\"")
            lines.append(f"")
    
    return "\n".join(lines)

def analyze_single_url(url):
    """Analyse une seule URL (utilisé pour le threading)"""
    cache_key = get_cache_key(url)
    
    # Vérifier le cache
    if cache_key in analysis_cache and is_cache_valid(analysis_cache[cache_key]):
        print(f"💾 Cache hit pour {url}")
        return analysis_cache[cache_key]["result"]
    
    print(f"🔍 Analyse de {url}")
    
    # Récupérer le contenu
    content = fetch_page_content(url)
    
    if not content or len(content) < 500:
        return {
            "url": url,
            "error": "❌ Contenu insuffisant ou inaccessible",
            "summary": None
        }
    
    # Analyses en parallèle (conceptuellement - Python GIL limite le vrai parallélisme)
    keyword_analysis, risk_score = analyze_keywords_advanced(content)
    structured_data = extract_structured_data(content)
    critical_sentences = extract_critical_sentences(content)
    ai_summary = summarize_with_groq(content, url)
    
    # Générer le résumé complet
    summary = generate_comprehensive_summary(
        url, content, keyword_analysis, risk_score,
        structured_data, critical_sentences, ai_summary
    )
    
    result = {
        "url": url,
        "summary": summary,
        "error": None,
        "risk_score": risk_score
    }
    
    # Mettre en cache
    analysis_cache[cache_key] = {
        "timestamp": datetime.now(),
        "result": result
    }
    
    return result

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        urls = data.get("urls", [])
        
        if not urls:
            return jsonify({"error": "Aucune URL fournie"}), 400
        
        # Limiter à 3 URLs pour ne pas surcharger
        urls = urls[:3]
        
        # Analyser les URLs en parallèle avec ThreadPoolExecutor
        results = []
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_url = {executor.submit(analyze_single_url, url): url for url in urls}
            
            for future in as_completed(future_to_url):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    url = future_to_url[future]
                    print(f"❌ Erreur lors de l'analyse de {url}: {e}")
                    results.append({
                        "url": url,
                        "error": f"Erreur: {str(e)}",
                        "summary": None
                    })
        
        # Compiler le résumé final avec index de documents
        final_summary_parts = []
        total_risk = 0
        analyzed_count = 0
        document_types = []
        
        # Ajouter un en-tête si plusieurs documents
        if len([r for r in results if r.get("summary")]) > 1:
            final_summary_parts.append(
                f"{'='*70}\n"
                f"📚 ANALYSE DE {len([r for r in results if r.get('summary')])} DOCUMENTS\n"
                f"{'='*70}\n"
            )
        
        for i, result in enumerate(results, 1):
            if result.get("summary"):
                # Ajouter un séparateur entre les documents
                if i > 1:
                    final_summary_parts.append(f"\n{'─'*70}\n")
                
                final_summary_parts.append(result["summary"])
                total_risk += result.get("risk_score", 0)
                analyzed_count += 1
                
                # Extraire le type de document pour le résumé
                summary_lines = result["summary"].split('\n')
                for line in summary_lines[:5]:
                    if any(emoji in line for emoji in ['🔐', '📜', '🍪', '⚖️', '📝', '📄']):
                        doc_type = line.split('🌐')[0].strip()
                        document_types.append(doc_type)
                        break
            elif result.get("error"):
                final_summary_parts.append(f"\n❌ {result['error']}: {result['url']}\n")
        
        final_summary = "\n".join(final_summary_parts)
        
        # Ajouter un footer global avec résumé
        if analyzed_count > 0:
            avg_risk = total_risk / analyzed_count
            
            final_summary += f"\n\n{'='*70}\n"
            final_summary += f"📊 RÉSUMÉ GLOBAL\n"
            final_summary += f"{'='*70}\n"
            final_summary += f"📁 Documents analysés: {analyzed_count}\n"
            
            if document_types:
                final_summary += f"📋 Types de documents:\n"
                for doc_type in document_types:
                    final_summary += f"   • {doc_type}\n"
            
            final_summary += f"\n🎯 Score de risque moyen: {avg_risk:.1f}\n"
            
            # Ajouter une recommandation basée sur le score
            if avg_risk < 30:
                recommendation = "✅ Ces politiques semblent relativement transparentes et protectrices."
            elif avg_risk < 60:
                recommendation = "⚠️ Attention modérée recommandée. Vérifiez les points sensibles."
            else:
                recommendation = "🚨 Niveau de risque élevé. Lisez attentivement avant d'accepter."
            
            final_summary += f"💬 {recommendation}\n"
        
        final_summary += f"\n💡 Conseil: Lisez toujours les documents complets avant d'accepter.\n"
        final_summary += f"🕒 Analyse effectuée le {datetime.now().strftime('%d/%m/%Y à %H:%M')}\n"
        final_summary += f"🔗 Source: {len(urls)} URL(s) analysée(s)\n"
        
        return jsonify({
            "summary": final_summary,
            "analyzed_count": analyzed_count,
            "has_ai": groq_client is not None
        })
        
    except Exception as e:
        print(f"❌ Erreur serveur: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "summary": f"❌ Erreur lors de l'analyse: {str(e)}"
        }), 500

@app.route("/health", methods=["GET"])
def health():
    """Endpoint de santé"""
    return jsonify({
        "status": "✅ Serveur actif",
        "mode": "🤖 IA + Analyse avancée" if groq_client else "🔍 Analyse avancée seule",
        "cache_size": len(analysis_cache),
        "version": "2.0"
    })

@app.route("/clear-cache", methods=["POST"])
def clear_cache():
    """Vide le cache"""
    analysis_cache.clear()
    fetch_page_content.cache_clear()
    return jsonify({"status": "✅ Cache vidé"})

if __name__ == "__main__":
    print("="*70)
    print("🚀 TRUST ADVISOR - Analyseur de Politiques de Confidentialité")
    print("="*70)
    print(f"📊 Mode: {'🤖 IA activée (Groq)' if groq_client else '🔍 Analyse par mots-clés uniquement'}")
    print(f"🌐 Serveur: http://127.0.0.1:5000")
    print(f"💾 Cache: {CACHE_DURATION.total_seconds()/3600}h")
    print(f"🧵 Threading: Activé (3 workers)")
    print("="*70)
    app.run(host="127.0.0.1", port=5000, debug=True)