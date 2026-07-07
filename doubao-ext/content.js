// Geo Monitor - Doubao content script
// Injected into doubao.com/chat. Handles geo_query messages.

console.log('[GM-DB:Content] Loaded on', location.href);

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'GEO_QUERY') {
    handleQuery(msg.question).then(sendResponse);
    return true; // async
  }
});

async function handleQuery(question) {
  try {
    // 1. Wait for page to be ready
    await waitForElement('textarea', 15000);
    
    // 2. Check login state
    const loginBtn = document.querySelector('button:has-text("登录"), [class*="login-btn"]');
    if (loginBtn && loginBtn.offsetParent !== null) {
      return { success: false, error: '未登录豆包，请先在浏览器中登录 https://www.doubao.com/chat/' };
    }
    
    // 3. Get current answer text (to detect new answer)
    const oldAnswer = getAnswerText();
    
    // 4. Type question
    const textarea = document.querySelector('textarea');
    textarea.focus();
    textarea.value = question;
    textarea.dispatchEvent(new Event('input', { bubbles: true }));
    textarea.dispatchEvent(new Event('change', { bubbles: true }));
    
    // Wait a beat for React to register
    await sleep(500);
    
    // 5. Submit - try multiple methods
    // Press Enter in the textarea
    textarea.dispatchEvent(new KeyboardEvent('keydown', { 
      key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true 
    }));
    
    // Also try clicking send button if visible
    const sendBtn = document.querySelector('[class*="send"], button:has(svg)');
    if (sendBtn && !sendBtn.disabled) {
      sendBtn.click();
    }
    
    // 6. Wait for new answer
    const answer = await waitForAnswer(oldAnswer);
    
    // 7. Extract citations
    const citations = extractCitations();
    
    // 8. Get model name
    const modelName = getModelName();
    
    return {
      success: true,
      answer_text: answer,
      citations: citations,
      model_name: modelName,
    };
    
  } catch (err) {
    return { success: false, error: String(err) };
  }
}

function getAnswerText() {
  // Try various selectors for the answer content
  const selectors = [
    '[class*="message"] [class*="content"]',
    '[class*="bubble"] [class*="content"]',
    '[class*="answer"] [class*="content"]',
    '[class*="markdown"]',
    '[class*="message"]:last-child',
  ];
  
  for (const sel of selectors) {
    const els = document.querySelectorAll(sel);
    if (els.length > 0) {
      const last = els[els.length - 1];
      if (last.textContent && last.textContent.trim().length > 10) {
        return last.textContent.trim();
      }
    }
  }
  return '';
}

async function waitForAnswer(oldText) {
  // Wait up to 60 seconds for a new answer
  for (let i = 0; i < 30; i++) {
    await sleep(2000);
    
    const current = getAnswerText();
    if (current && current !== oldText && current.length > 20) {
      // Found new text, now wait for it to stabilize
      let stable = current;
      for (let j = 0; j < 10; j++) {
        await sleep(2000);
        const next = getAnswerText();
        if (next === stable && next.length > 20) {
          return next; // stable
        }
        stable = next;
      }
      return stable;
    }
  }
  
  // Timeout - return whatever we have
  const final = getAnswerText();
  return final || '(no answer)';
}

function extractCitations() {
  const citations = [];
  const seen = new Set();
  
  // Look for reference/source area
  const refAreas = document.querySelectorAll('[class*="reference"], [class*="source"], [class*="citation"]');
  
  let links = [];
  if (refAreas.length > 0) {
    // Get links from reference section
    for (const area of refAreas) {
      links.push(...area.querySelectorAll('a[href^="http"]'));
    }
  } else {
    // Get links from last message
    const messages = document.querySelectorAll('[class*="message"], [class*="bubble"]');
    if (messages.length > 0) {
      links = Array.from(messages[messages.length - 1].querySelectorAll('a[href^="http"]'));
    }
  }
  
  for (const link of links) {
    try {
      const url = link.href;
      if (!url || seen.has(url)) continue;
      if (url.includes('doubao.com')) continue;
      seen.add(url);
      
      const domain = new URL(url).hostname;
      citations.push({
        url: url,
        title: (link.textContent || '').trim().substring(0, 100),
        domain: domain,
        snippet: '',
      });
    } catch {}
  }
  
  return citations;
}

function getModelName() {
  const el = document.querySelector('[class*="model"]');
  return el ? el.textContent.trim() : 'doubao-unknown';
}

function waitForElement(selector, timeout) {
  return new Promise((resolve, reject) => {
    const start = Date.now();
    const check = () => {
      const el = document.querySelector(selector);
      if (el && el.offsetParent !== null) {
        resolve(el);
      } else if (Date.now() - start > timeout) {
        reject(new Error(`timeout waiting for ${selector}`));
      } else {
        setTimeout(check, 500);
      }
    };
    check();
  });
}

function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}
