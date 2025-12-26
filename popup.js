document.addEventListener("DOMContentLoaded", async () => {
  const summaryDiv = document.getElementById("summary");
  const refreshBtn = document.getElementById("refreshBtn");
  
  // Fonction pour charger le résumé
  async function loadSummary() {
    try {
      summaryDiv.innerText = "⏳ Chargement...";
      
      const result = await chrome.storage.local.get(["policySummary", "lastUpdate", "policyUrls", "error"]);
      
      if (result.policySummary) {
        let summary = result.policySummary;
        if (result.lastUpdate) {
          const date = new Date(result.lastUpdate);
          summary += `\n\n---\n⏰ Dernière analyse: ${date.toLocaleString('fr-FR')}`;
        }
        summaryDiv.innerText = summary;
      } else {
        summaryDiv.innerText = "ℹ️ Aucune politique analysée pour le moment.\n\n👉 Cliquez sur 'Analyser cette page' pour détecter les politiques de confidentialité et conditions d'utilisation.";
      }
    } catch (error) {
      console.error("Erreur:", error);
      summaryDiv.innerText = "❌ Erreur lors du chargement : " + error.message;
    }
  }
  
  // Fonction pour vérifier si le content script est injecté
  async function isContentScriptInjected(tabId) {
    return new Promise((resolve) => {
      chrome.tabs.sendMessage(tabId, { type: "ping" }, (response) => {
        if (chrome.runtime.lastError) {
          console.log("⚠️ Content script non injecté:", chrome.runtime.lastError.message);
          resolve(false);
        } else {
          console.log("✅ Content script déjà injecté");
          resolve(true);
        }
      });
    });
  }
  
  // Fonction pour injecter le content script
  async function injectContentScript(tabId) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tabId },
        files: ['content.js']
      });
      console.log("✅ Content script injecté");
      
      // Attendre que le script s'initialise
      await new Promise(resolve => setTimeout(resolve, 1000));
      return true;
    } catch (error) {
      console.error("❌ Erreur injection:", error);
      return false;
    }
  }
  
  // Fonction pour analyser la page active
  async function analyzePage() {
    try {
      summaryDiv.innerText = "🔍 Analyse en cours...";
      
      // Obtenir l'onglet actif
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (!tab || !tab.id) {
        throw new Error("Impossible de récupérer l'onglet actif");
      }
      
      // Vérifier si c'est une page chrome:// ou extension://
      if (tab.url.startsWith('chrome://') || tab.url.startsWith('chrome-extension://') || tab.url.startsWith('edge://')) {
        summaryDiv.innerText = "❌ Cette extension ne peut pas analyser les pages internes du navigateur.\n\nVeuillez aller sur un site web normal.";
        return;
      }
      
      console.log("📄 Analyse de:", tab.url);
      
      // Vérifier si le content script est injecté
      const isInjected = await isContentScriptInjected(tab.id);
      
      if (!isInjected) {
        console.log("⚠️ Content script non détecté, injection en cours...");
        summaryDiv.innerText = "⏳ Injection du script d'analyse...";
        
        const injected = await injectContentScript(tab.id);
        if (!injected) {
          summaryDiv.innerText = "❌ Impossible d'injecter le script.\n\n💡 Astuce: Rechargez la page (F5) et réessayez.";
          return;
        }
      }
      
      // Envoyer le message de détection avec gestion d'erreur
      summaryDiv.innerText = "⏳ Détection des politiques...";
      
      chrome.tabs.sendMessage(tab.id, { type: "detectPolicies" }, (response) => {
        if (chrome.runtime.lastError) {
          console.error("Erreur sendMessage:", chrome.runtime.lastError);
          summaryDiv.innerText = "❌ Erreur de communication.\n\n💡 Rechargez la page (F5) et réessayez.";
        } else {
          console.log("✅ Message envoyé avec succès");
          summaryDiv.innerText = "⏳ Analyse en cours...\n\nVeuillez patienter quelques secondes.";
          
          // Attendre puis recharger le résumé
          setTimeout(loadSummary, 3000);
        }
      });
      
    } catch (error) {
      console.error("Erreur:", error);
      summaryDiv.innerText = "❌ Erreur: " + error.message;
    }
  }
  
  // Charger au démarrage
  await loadSummary();
  
  // Bouton pour forcer l'analyse
  if (refreshBtn) {
    refreshBtn.addEventListener("click", analyzePage);
  }
});