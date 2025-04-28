import { EventEmitter } from 'events';
import { WebSocket, WebSocketServer } from 'ws';

export class CookedProtocolHost extends EventEmitter {
    private wss: WebSocketServer;
    private ws: WebSocket;

    constructor() {
        super();

        this.wss = new WebSocketServer({ port: 5630 });

        this.wss.on('connection', this._handleConnection.bind(this));
    }

    public send(type: string, message: any) {
        this.ws.send(JSON.stringify({ ...message, type }));
    }

    private _handleConnection(ws: WebSocket) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            console.log('[ext] connection already exists, ending');
            this.ws.close();
        }

        this.ws = ws;
        this.ws.on('message', this._handleMessage.bind(this));

        console.log('[ext] connected');
        this.emit('connection');
    }

    private _handleMessage(data: WebSocket.RawData, isBinary: boolean) {
        if (isBinary) {
            console.log('[ext] received unexpected binary data');
            return;
        }

        const data_obj = JSON.parse(data as unknown as string);
        const { type, message } = data_obj as { type: string; message: any };

        this.emit(type, message);
    }
}