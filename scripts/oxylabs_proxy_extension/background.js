chrome.runtime.onStartup.addListener(setupProxy);
chrome.runtime.onInstalled.addListener(setupProxy);

async function setupProxy() {
  try {
    // Load configuration
    const response = await fetch(chrome.runtime.getURL('config.json'));
    const config = await response.json();
    
    // Set proxy configuration
    const proxyConfig = {
      value: {
        mode: "fixed_servers",
        rules: {
          singleProxy: {
            scheme: config.protocol || "http",
            host: config.host,
            port: parseInt(config.port)
          }
        }
      },
      scope: "regular"
    };
    
    await chrome.proxy.settings.set(proxyConfig);
    console.log('Oxylabs proxy configured:', config.host + ':' + config.port);
    
  } catch (error) {
    console.error('Failed to setup proxy:', error);
  }
}

// Handle proxy authentication
chrome.webRequest.onAuthRequired.addListener(
  function(details) {
    return new Promise(async (resolve) => {
      try {
        const response = await fetch(chrome.runtime.getURL('config.json'));
        const config = await response.json();
        
        resolve({
          authCredentials: {
            username: config.username_full,
            password: config.password
          }
        });
      } catch (error) {
        console.error('Auth failed:', error);
        resolve({});
      }
    });
  },
  { urls: ["<all_urls>"] },
  ["blocking"]
);

// Initialize on startup
setupProxy();
