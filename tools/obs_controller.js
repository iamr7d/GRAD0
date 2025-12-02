#!/usr/bin/env node
/**
 * obs_controller.js
 *
 * Connects to OBS via obs-websocket, polls the run_of_show queue, and updates
 * OBS sources when the currently playing item changes.
 *
 * Usage:
 *   1) npm install obs-websocket-js@4 node-fetch
 *   2) Configure constants below (OBS address/password and source names)
 *   3) node tools/obs_controller.js
 *
 * Notes:
 * - This script targets obs-websocket v4 API (common with OBS <= 28/29).
 * - If you're using obs-websocket v5+, either install the v4 compatibility plugin
 *   or adapt the code to the v5 API (client libraries differ).
 */

const fs = require('fs');
const path = require('path');
const OBSWebSocket = require('obs-websocket-js');
const obs = new OBSWebSocket();

// ===== Configuration =====
const OBS_ADDRESS = process.env.OBS_ADDRESS || 'localhost:4444';
const OBS_PASSWORD = process.env.OBS_PASSWORD || '';
const POLL_INTERVAL_MS = 2000;

// Names of the sources in your OBS scene to update
const SCENE_NAME = process.env.OBS_SCENE || 'Broadcast';
const HEADLINE_SOURCE = process.env.OBS_HEADLINE_SOURCE || 'Headline_Text'; // Text (GDI+) source name
const SUMMARY_SOURCE = process.env.OBS_SUMMARY_SOURCE || 'Summary_Text';
const BG_BROWSER_SOURCE = process.env.OBS_BG_BROWSER_SOURCE || 'BG_Browser'; // Browser source name pointing to background video (we update URL)

// Run-of-show path
const RUN_OF_SHOW = process.env.RUN_OF_SHOW_PATH || path.join(__dirname, '..', 'bucket', 'news', 'queue', 'run_of_show.json');

let lastItemId = null;

async function connectObs() {
  try {
    await obs.connect({ address: OBS_ADDRESS, password: OBS_PASSWORD });
    console.log('Connected to OBS at', OBS_ADDRESS);
  } catch (err) {
    console.error('Failed to connect to OBS:', err.message || err);
    setTimeout(connectObs, 3000);
  }
}

async function updateObsForItem(item) {
  if (!item) return;
  try {
    // Update headline text (Text GDI+)
    if (HEADLINE_SOURCE) {
      await obs.send('SetTextGDIPlusProperties', { source: HEADLINE_SOURCE, text: item.main_heading || '' });
    }

    // Update summary
    if (SUMMARY_SOURCE) {
      await obs.send('SetTextGDIPlusProperties', { source: SUMMARY_SOURCE, text: item.content_text || '' });
    }

    // Update browser source URL to proxied video (if present)
    if (BG_BROWSER_SOURCE) {
      const video = (item.extra_data && item.extra_data.video_url) ? item.extra_data.video_url : '';
      let newUrl = video || '';
      if (newUrl && newUrl.startsWith('http')) {
        // route through local proxy to avoid CORS/hotlink issues
        const prox = 'http://127.0.0.1:8000/proxy_video?url=' + encodeURIComponent(newUrl);
        newUrl = prox;
      }
      // For Browser source, the setting key is usually 'url'
      await obs.send('SetSourceSettings', { sourceName: BG_BROWSER_SOURCE, sourceSettings: { url: newUrl } });
    }

    // Optionally ensure scene is active
    if (SCENE_NAME) {
      await obs.send('SetCurrentScene', { 'scene-name': SCENE_NAME });
    }

    console.log('OBS updated for item:', item.id || '(no id)');
  } catch (err) {
    console.error('Error updating OBS for item', err.message || err);
  }
}

function readCurrentItem() {
  try {
    if (!fs.existsSync(RUN_OF_SHOW)) return null;
    const data = JSON.parse(fs.readFileSync(RUN_OF_SHOW, 'utf8'));
    if (!Array.isArray(data) || data.length === 0) return null;
    return data[0];
  } catch (err) {
    console.error('Failed to read run_of_show.json:', err.message || err);
    return null;
  }
}

async function pollLoop() {
  try {
    const item = readCurrentItem();
    if (item && item.id && item.id !== lastItemId) {
      lastItemId = item.id;
      console.log('New item detected:', item.id, item.main_heading);
      await updateObsForItem(item);
    }
  } catch (err) {
    console.error('Poll error:', err.message || err);
  } finally {
    setTimeout(pollLoop, POLL_INTERVAL_MS);
  }
}

// Ensure graceful shutdown
process.on('SIGINT', async () => { console.log('Shutting down...'); try { await obs.disconnect(); } catch (e) {} process.exit(0); });

// Start
connectObs().then(() => pollLoop()).catch(err => { console.error(err); pollLoop(); });
