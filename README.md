# TrustAdvisor 🔍🛡️

**TrustAdvisor** est une extension de navigateur conçue pour aider les utilisateurs à comprendre rapidement les **conditions d’utilisation**, **politiques de confidentialité** et **politiques de cookies** des sites web.  
Plutôt que d’accepter aveuglément des documents longs et complexes, TrustAdvisor extrait et résume les points clés afin que chacun puisse prendre une décision éclairée.

---

## ✨ Fonctionnalités
- 🔎 **Détection automatique** des liens vers les politiques légales (Terms, Privacy, Cookies).
- 📑 **Analyse du contenu** pour identifier les clauses sensibles (partage de données, cookies, responsabilité, etc.).
- ⚠️ **Résumé clair et concis** affiché dans un popup avant l’acceptation.
- 🌐 **Compatibilité multi-navigateurs** (Chrome, Edge, Firefox).
- 🐍 **Support Python (Flask/NLP)** pour une analyse avancée côté serveur.

---

## 🛠️ Installation en mode développeur

### Chrome
1. Ouvrir `chrome://extensions`.
2. Activer le **Mode développeur**.
3. Cliquer sur **Charger l’extension non empaquetée**.
4. Sélectionner le dossier contenant `manifest.json`.

### Edge
1. Ouvrir `edge://extensions`.
2. Activer le **Mode développeur**.
3. Cliquer sur **Charger l’extension**.
4. Sélectionner le dossier contenant `manifest.json`.

---

## 📂 Structure du projet
TrustAdvisor/
│── manifest.json         # Configuration de l’extension
│── background.js         # Logique principale (communication avec backend)
│── content.js            # Détection des liens sur les pages
│── popup.html            # Interface utilisateur
│── popup.js              # Affichage du résumé
│── icons/               # Icônes de l’extension
│── backend/             # Code Python (Flask + NLP)


## 🚀 Backend Python (optionnel)
TrustAdvisor peut utiliser un backend Python pour une analyse plus poussée (NLP avec spaCy ou transformers).

### Exemple de lancement
```bash
cd backend
pip install flask flask-cors requests spacy
python app.py

🤝 Contribution
Les contributions sont les bienvenues !
Forkez le projet, créez une branche et proposez vos améliorations via une Pull Request.
