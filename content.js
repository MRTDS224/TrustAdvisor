// Flag pour éviter les exécutions multiples
if (!window.policyAssistantInitialized) {
  window.policyAssistantInitialized = true;

  console.log("🚀 Trust Advisor initialisé");

  // Définir les types de documents à détecter
  const DOCUMENT_TYPES = {
    privacy: {
      urlKeywords: ['privacy', 'confidentialite', 'donnees-personnelles', 'personal-data'],
      textKeywords: ['privacy policy', 'politique de confidentialité', 'protection des données'],
      emoji: '🔐',
      label: 'Confidentialité'
    },
    terms: {
      urlKeywords: ['terms', 'conditions', 'cgu', 'cgv', 'tos'],
      textKeywords: ["conditions d'utilisation", 'terms of service', 'user agreement'],
      emoji: '📜',
      label: 'Conditions'
    },
    cookies: {
      urlKeywords: ['cookie', 'cookies'],
      textKeywords: ['cookie policy', 'politique de cookies'],
      emoji: '🍪',
      label: 'Cookies'
    },
    legal: {
      urlKeywords: ['legal', 'mentions-legales', 'mentions'],
      textKeywords: ['mentions légales', 'legal notice'],
      emoji: '⚖️',
      label: 'Légal'
    }
  };

  function detectDocumentType(href, text) {
    // Détecte le type de document basé sur l'URL et le texte
    const hrefLower = href.toLowerCase();
    const textLower = text.toLowerCase();
    
    for (const [type, config] of Object.entries(DOCUMENT_TYPES)) {
      // Vérifier l'URL
      const matchUrl = config.urlKeywords.some(kw => hrefLower.includes(kw));
      
      // Vérifier le texte du lien
      const matchText = config.textKeywords.some(kw => textLower.includes(kw));
      
      if (matchUrl || matchText) {
        return {
          type: type,
          emoji: config.emoji,
          label: config.label
        };
      }
    }
    
    return {
      type: 'other',
      emoji: '📄',
      label: 'Autre'
    };
  }

  function detectPolicies() {
    // Détecte les liens vers les politiques
    console.log("🔍 Recherche des politiques...");
    
    // Chercher tous les liens
    const allLinks = Array.from(document.querySelectorAll("a"));
    
    // Filtrer et catégoriser les liens
    const categorizedLinks = [];
    const seenUrls = new Set();
    
    for (const link of allLinks) {
      const href = link.href || "";
      const text = link.textContent || "";
      
      if (!href || href.startsWith('javascript:') || href === '#') {
        continue;
      }
      
      // Détecter le type de document
      const docInfo = detectDocumentType(href, text);
      
      // Ignorer les liens "other" sauf s'ils ont des mots-clés pertinents
      if (docInfo.type === 'other') {
        const hasRelevantKeywords = 
          /policy|privacy|terms|cookie|legal|conditions/i.test(href) ||
          /policy|privacy|terms|cookie|legal|conditions/i.test(text);
        
        if (!hasRelevantKeywords) {
          continue;
        }
      }
      
      // Éviter les doublons
      if (seenUrls.has(href)) {
        continue;
      }
      
      seenUrls.add(href);
      categorizedLinks.push({
        url: href,
        type: docInfo.type,
        emoji: docInfo.emoji,
        label: docInfo.label,
        linkText: text.substring(0, 50)
      });
    }

    if (categorizedLinks.length > 0) {
      // Trier par priorité (privacy > terms > cookies > legal > other)
      const priority = { privacy: 1, terms: 2, cookies: 3, legal: 4, other: 5 };
      categorizedLinks.sort((a, b) => priority[a.type] - priority[b.type]);
      
      // Extraire uniquement les URLs
      const urls = categorizedLinks.map(link => link.url);
      
      // Logger avec détails
      console.log("✅ Politiques détectées:");
      categorizedLinks.forEach(link => {
        console.log(`  ${link.emoji} ${link.label}: ${link.url}`);
      });
      
      // Envoyer au background script
      chrome.runtime.sendMessage({
        type: "foundPolicies",
        urls: urls,
        details: categorizedLinks  // Informations supplémentaires
      }).catch(err => {
        console.error("❌ Erreur envoi message:", err);
      });
    } else {
      console.log("⚠️ Aucune politique détectée sur cette page");
      
      // Envoyer quand même un message pour informer
      chrome.runtime.sendMessage({
        type: "foundPolicies",
        urls: [],
        details: []
      }).catch(err => {
        console.error("❌ Erreur envoi message:", err);
      });
    }
  }

  // Exécuter la détection au chargement
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", detectPolicies);
  } else {
    // Page déjà chargée, exécuter immédiatement
    detectPolicies();
  }

  // Écouter les messages du popup
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("📨 Message reçu:", message.type);
    
    // Répondre au ping
    if (message.type === "ping") {
      console.log("🏓 Pong!");
      sendResponse({ active: true });
      return true;
    }
    
    // Détecter manuellement
    if (message.type === "detectPolicies") {
      console.log("🔍 Détection manuelle déclenchée");
      detectPolicies();
      sendResponse({ success: true });
      return true;
    }
  });

  console.log("✅ Trust Advisor prêt");
}