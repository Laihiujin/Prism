#!/usr/bin/env python3
"""
Get extension error details via DevTools Protocol.
"""
import asyncio
import json
import httpx
import websockets

async def get_extension_errors():
    """Get extension errors from chrome://extensions page."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:9222/json")
        targets = response.json()

    # Find the extensions page
    extensions_page = None
    for target in targets:
        if 'chrome://extensions' in target.get('url', ''):
            extensions_page = target
            break

    if not extensions_page:
        print("Extensions page not found")
        return

    print(f"Found extensions page: {extensions_page['url']}")
    ws_url = extensions_page['webSocketDebuggerUrl']

    async with websockets.connect(ws_url) as websocket:
        # Enable Runtime
        await websocket.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        await websocket.recv()

        # Evaluate JavaScript to get extension errors
        await websocket.send(json.dumps({
            "id": 2,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "document.body.innerText",
                "returnByValue": True
            }
        }))
        response = await websocket.recv()
        data = json.loads(response)

        if 'result' in data and 'result' in data['result']:
            text = data['result']['result'].get('value', '')
            print("\nExtensions page content:")
            print("=" * 80)
            print(text[:2000])  # Print first 2000 chars

if __name__ == "__main__":
    asyncio.run(get_extension_errors())
