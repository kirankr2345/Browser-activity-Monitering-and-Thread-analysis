import json
from channels.generic.websocket import AsyncWebsocketConsumer


class TelemetryConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_group_name = 'telemetry_stream'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'status': 'connected',
            'message': 'Connected to Smart Browser Monitoring Real-time WebSocket'
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')
            if action == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong', 'timestamp': data.get('timestamp')}))
            elif action == 'broadcast_event':
                # Re-broadcast to all connected dashboards
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'telemetry_update',
                        'data': data.get('data', {})
                    }
                )
        except Exception as e:
            await self.send(text_data=json.dumps({'type': 'error', 'message': str(e)}))

    async def telemetry_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'telemetry_event',
            'data': event.get('data')
        }))
