from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re

app = Flask(__name__)
CORS(app)

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.json
        summaries = []
        
        for url in data.get("urls", []):
            try:
                response = requests.get(url, timeout=10)
                text = response.text
                
                # Chercher des mots-clés importants
                points = re.findall(
                    r"(cookies|third parties|data sharing|liability|personal data|gdpr)",
                    text,
                    re.IGNORECASE
                )
                
                unique_points = list(set(points))
                summaries.append(f"• {url}\n  Points clés: {', '.join(unique_points) if unique_points else 'Aucun point détecté'}")
                
            except Exception as e:
                summaries.append(f"• {url}\n  Erreur: {str(e)}")
        
        return jsonify({
            "summary": "\n\n".join(summaries) if summaries else "Aucune analyse disponible"
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(port=5000, debug=True)