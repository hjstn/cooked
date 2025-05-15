import { ContentScriptMessage } from '../lib/messages';
import { storageGet, storageSet } from './mv-compat';
import { initConfig } from './utils';

class CookedProtocol {
    private ws: WebSocket = null;

    connect() {
        if (this.ws) this.ws.close();

        this.ws = new WebSocket('ws://localhost:5630');

        this.ws.onopen = this._open.bind(this);
        this.ws.onclose = this._close.bind(this);
        this.ws.onmessage = this._message.bind(this);
    }

    send(type: string, message: any) {
        this.ws.send(JSON.stringify({ type, message }));
    }

    _open(event: Event) {
        console.log('[cooked] connection opened');
    }

    _close(event: Event) {
        console.log('[cooked] connection closed');
    }

    _message(event: MessageEvent) {
        console.log('[cooked] message:', event.data);

        const data = JSON.parse(event.data);

        if (data.type === 'optChoice') {
            console.log('[cooked] received optChoice:', data.choice);

            updateConfig({ autoAction: data.choice });
        } else {
            console.log('[cooked] unknown message type:', data.type);
        }
    }
}

async function updateConfig(configChange: object) {
    let storedConfig = (await storageGet('config')) || {};
    console.log('storedConfig', storedConfig);

    storedConfig = { ...storedConfig, ...configChange };
    console.log('[cooked] updating config', storedConfig);

    console.log('updated config', storedConfig);
    await storageSet({
        config: storedConfig,
    });
}

export async function cookedInit() {
    await initConfig();

    const protocol = new CookedProtocol();

    protocol.connect();

    chrome.runtime.onMessage.addListener(async (msg: ContentScriptMessage, sender: any) => {
        switch (msg.type) {
            case 'init':
                protocol.send('init', msg);
                break;
            case 'popupFound':
                protocol.send('popupFound', msg);
                break;
            case 'optOutResult':
            case 'optInResult':
                protocol.send('optResult', msg);
                break;
            case 'autoconsentDone':
                protocol.send('autoconsentDone', msg);
                break;
            case 'autoconsentError':
                protocol.send('autoconsentError', msg);
                break;
            case 'report':
                protocol.send('report', msg);
                break;
        }
    });
}