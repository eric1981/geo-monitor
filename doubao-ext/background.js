// Geo Monitor - Doubao background service worker
// Native Messaging bridge: receives geo_query commands, forwards to content script, returns results

let nativePort = null;

function connectNative() {
  try {
    nativePort = chrome.runtime.connectNative('com.geo-monitor.doubao');
    console.log('[GM-DB] Native host connected');

    nativePort.onMessage.addListener(async (msg) => {
      console.log('[GM-DB] Received:', msg.action);
      
      if (msg.action === 'geo_query') {
        const result = await executeQuery(msg.question);
        nativePort.postMessage({
          _id: msg._id,
          success: result.success,
          answer_text: result.answer_text || '',
          citations: result.citations || [],
          model_name: result.model_name || '',
          error: result.error || '',
        });
      } else if (msg.action === 'ping') {
        nativePort.postMessage({ pong: true, tab_count: (await chrome.tabs.query({})).length });
      }
    });

    nativePort.onDisconnect.addListener(() => {
      console.log('[GM-DB] Native host disconnected, reconnect in 5s');
      nativePort = null;
      setTimeout(connectNative, 5000);
    });
  } catch (err) {
    console.warn('[GM-DB] Native host not available:', err.message);
    setTimeout(connectNative, 5000);
  }
}

connectNative();

// ── Query Execution ──

async function executeQuery(question) {
  try {
    // Find or create a doubao chat tab
    let tab = await findDoubaoTab();
    if (!tab) {
      tab = await chrome.tabs.create({ 
        url: 'https://www.doubao.com/chat/', 
        active: false 
      });
      // Wait for page to load
      await sleep(5000);
    } else {
      // Focus existing tab and reload if needed
      await chrome.tabs.update(tab.id, { active: true });
      await sleep(2000);
    }

    const tabId = tab.id;
    
    // Send query to content script
    const response = await sendToTab(tabId, { 
      type: 'GEO_QUERY', 
      question: question 
    });
    
    if (chrome.runtime.lastError) {
      return { success: false, error: chrome.runtime.lastError.message };
    }
    
    return response || { success: false, error: 'no response from content script' };
    
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

async function findDoubaoTab() {
  const tabs = await chrome.tabs.query({});
  return tabs.find(t => t.url && t.url.includes('doubao.com/chat')) || null;
}

function sendToTab(tabId, msg) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, msg, (resp) => {
      resolve(resp);
    });
  });
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
