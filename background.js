// Stocker les politiques par onglet
let policiesByTab = {};

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "foundPolicies") {
    const tabId = sender.tab?.id;
    console.log("📋 Politiques détectées dans l'onglet", tabId, ":", message.urls);
    
    // Sauvegarder pour cet onglet
    if (tabId) {
      policiesByTab[tabId] = message.urls;
    }

    // Envoyer au backend Python
    console.log("🌐 Envoi au serveur Flask...");
    fetch("http://127.0.0.1:5000/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ urls: message.urls })
    })
    .then(res => {
      console.log("📥 Réponse serveur reçue:", res.status);
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      return res.json();
    })
    .then(data => {
      console.log("✅ Résumé reçu :", data.summary);
      chrome.storage.local.set({ 
        policySummary: data.summary,
        lastUpdate: new Date().toISOString(),
        policyUrls: message.urls
      }, () => {
        console.log("💾 Résumé sauvegardé dans le storage");
      });
    })
    .catch(error => {
      console.error("❌ Erreur lors de l'analyse :", error);
      
      // Sauvegarder quand même les URLs détectées
      const offlineSummary = `⚠️ Serveur d'analyse non disponible\n\nPolitiques détectées sur cette page:\n\n${message.urls.map((url, i) => `${i + 1}. ${url}`).join('\n')}\n\n💡 Conseil: Vérifiez que le serveur Flask tourne (python main.py)\nErreur: ${error.message}`;
      
      chrome.storage.local.set({ 
        policySummary: offlineSummary,
        lastUpdate: new Date().toISOString(),
        policyUrls: message.urls,
        error: error.message
      });
    });
  }
  
  // Demande du popup pour l'onglet actif
  if (message.type === "getPolicies") {
    sendResponse({ urls: policiesByTab[message.tabId] || [] });
  }
});

// Nettoyer quand un onglet est fermé
chrome.tabs.onRemoved.addListener((tabId) => {
  delete policiesByTab[tabId];
});

console.log("🎯 Background script chargé");