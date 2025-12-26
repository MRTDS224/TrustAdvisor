// Flag pour éviter les exécutions multiples
if (!window.policyAssistantInitialized) {
  window.policyAssistantInitialized = true;

  console.log("🚀 Policy Assistant initialisé");

  // Attendre que la page soit complètement chargée
  function detectPolicies() {
    // Cherche les liens contenant "terms", "privacy", "cookies", etc.
    let links = Array.from(document.querySelectorAll("a")).filter(a => {
      const href = (a.href || "").toLowerCase();
      const text = (a.textContent || "").toLowerCase();
      
      return (
        href.includes("terms") ||
        href.includes("privacy") ||
        href.includes("cookies") ||
        href.includes("policy") ||
        href.includes("legal") ||
        href.includes("gdpr") ||
        text.includes("terms") ||
        text.includes("privacy") ||
        text.includes("cookies") ||
        text.includes("policy") ||
        text.includes("confidentialité") ||
        text.includes("conditions")
      );
    });

    if (links.length > 0) {
      const uniqueUrls = [...new Set(links.map(a => a.href))];
      console.log("✅ Politiques détectées:", uniqueUrls);
      
      // Envoyer au background script
      try {
        chrome.runtime.sendMessage({
          type: "foundPolicies",
          urls: uniqueUrls
        });
      } catch (err) {
        console.error("❌ Erreur envoi message:", err);
      }
    } else {
      console.log("⚠️ Aucune politique détectée sur cette page");
    }
  }

  // Exécuter la détection au chargement
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", detectPolicies);
  } else {
    detectPolicies();
  }

  // Écouter les messages du popup
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log("📨 Message reçu:", message.type);
    
    // Répondre au ping pour vérifier que le script est actif
    if (message.type === "ping") {
      console.log("🏓 Pong!");
      sendResponse({ active: true });
      return true;
    }
    
    // Détecter les politiques manuellement
    if (message.type === "detectPolicies") {
      console.log("🔍 Détection manuelle demandée");
      detectPolicies();
      sendResponse({ success: true });
      return true;
    }
  });
}