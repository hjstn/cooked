/// <reference types="chrome"/>yar

import { storageGet, storageSet } from "./mv-compat";
import { initConfig } from "./utils";

class CookedBackground {
  private ws: WebSocket | null = null;

  constructor() {
  }

  async init(port: number) {
    console.log('[cooked] received init request');

    if (this.ws) this.ws.close();
    
    this.ws = new WebSocket(`ws://localhost:${port}`);

    this.ws.onopen = this._open.bind(this);
    this.ws.onclose = this._close.bind(this);

    chrome.runtime.onMessage.addListener((message: any) => {
      if (message.type === 'cooked') return;

      this.ws?.send(JSON.stringify(message));
    });

    return true;
  }

  async updateConfig(configChange: object) {
    let storedConfig = (await storageGet('config')) || {};
    console.log('storedConfig', storedConfig);

    storedConfig = { ...storedConfig, ...configChange };
    console.log('[cooked] updating config', storedConfig);

    console.log('updated config', storedConfig);
    await storageSet({
        config: storedConfig,
    });
  }

  private _open() {
    console.log('[cooked] WebSocket opened');
  }

  private _close() {
    console.log('[cooked] WebSocket closed');
  }
}

export async function cookedInit() {
  await initConfig();

  const background = new CookedBackground();

  chrome.runtime.onMessage.addListener((message: any, sender: any, sendResponse: any) => {
    if (message.type !== 'cooked') return;

    switch (message.subtype) {
      case 'init':
        return sendResponse(background.init(message.port));
      case 'updateConfig':
        return sendResponse(background.updateConfig(message.configChange));
    }
  });
}