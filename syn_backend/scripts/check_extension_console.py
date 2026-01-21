#!/usr/bin/env python3
"""
Check Chrome extension console for errors via DevTools Protocol.
"""
import asyncio
import json
import websockets

async def check_extension_console():
    """Connect to extension service worker and check console."""
    # Get list of targets
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:9222/json")
        targets = response.json()

    # Find extension service worker
    extension_worker = None
    for target in targets:
        if target['type'] == 'service_worker':
            url = target.get('url', '')
            if 'chrome-extension://' in url or 'background' in url.lower():
                extension_worker = target
                break

    if not extension_worker:
        print("No extension service worker found")
        print("\nAvailable targets:")
        for target in targets:
            print(f"  {target['type']}: {target.get('url', target.get('title', 'N/A'))}")
        return

    print(f"Found extension worker: {extension_worker.get('title', 'N/A')}")
    print(f"URL: {extension_worker.get('url', 'N/A')}")
    print(f"WebSocket: {extension_worker['webSocketDebuggerUrl']}")

    # Connect to WebSocket and get console logs
    ws_url = extension_worker['webSocketDebuggerUrl']
    print(f"\nConnecting to {ws_url}...")

    try:
        async with websockets.connect(ws_url) as websocket:
            # Enable Runtime domain
            await websocket.send(json.dumps({
                "id": 1,
                "method": "Runtime.enable"
            }))
            response = await websocket.recv()
            print(f"Runtime enabled: {response}")

            # Enable Log domain
            await websocket.send(json.dumps({
                "id": 2,
                "method": "Log.enable"
            }))
            response = await websocket.recv()
            print(f"Log enabled: {response}")

            # Listen for console messages
            print("\nListening for console messages (Ctrl+C to stop)...")
            for _ in range(10):  # Listen for 10 messages or timeout
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    data = json.loads(message)
                    if 'method' in data:
                        print(f"\n{data['method']}:")
                        print(json.dumps(data.get('params', {}), indent=2))
                except asyncio.TimeoutError:
                    break

    except Exception as e:
        print(f"Error connecting to WebSocket: {e}")

if __name__ == "__main__":
    asyncio.run(check_extension_console())
