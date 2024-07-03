import aiohttp
import json
import asyncio
import logging
import ssl
from multidict import MultiDict

class CallComfyUI:
    
    def __init__(self, client_id):
        self.client_id = client_id

    async def upload_image(self, image):
        body = aiohttp.FormData()
        body.add_field('image', image)
        data = {
            "subfolder": "",
            "type": "input"
        }
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"http://localhost:8188/upload/image", data=body, params=data) as response:
                    if response.status != 200:
                        logging.error(f"Failed to upload image: {response.status}")
                        return None
                    info = await response.json()
                    path = info['name']
                    return path
            except Exception as e:
                logging.error(f"Error uploading image: {str(e)}")
                return None

    async def queue_prompt(self, prompt):
        p = {"prompt": prompt, "client_id": self.client_id}
        data = json.dumps(p)
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(f"http://localhost:8188/prompt", data=data) as response:
                    if response.status != 200:
                        logging.error(f"Failed to queue prompt: {response.status}")
                        return None
                    return await response.json()
            except Exception as e:
                logging.error(f"Error queuing prompt: {str(e)}")
                return None
    
    async def get_image(self, filename, subfolder, folder_type):
        data = MultiDict({
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        })
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"http://localhost:8188/view", params=data) as response:
                    if response.status != 200:
                        logging.error(f"Failed to get image: {response.status}")
                        return None
                    return await response.read()
            except Exception as e:
                logging.error(f"Error getting image: {str(e)}")
                return None
    
    async def get_history(self, prompt_id):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(f"http://localhost:8188/history/{prompt_id}") as response:
                    if response.status != 200:
                        logging.error(f"Failed to get history: {response.status}")
                        return None
                    return await response.json()
            except Exception as e:
                logging.error(f"Error getting history: {str(e)}")
                return None
    
    async def get_images(self, ws, prompt):
        prompt_data = await self.queue_prompt(prompt)
        if not prompt_data:
            return None
        output_images = {}

        while True:
            try:
                out = await ws.receive()
                if out.type == aiohttp.WSMsgType.TEXT:
                    message = json.loads(out.data)
                    if message['type'] == 'executed':
                        data = message['data']
                        output = data['output']
                        node_id = data['node']
                        images_output = []
                        for image in output['images']:
                            image_data = await self.get_image(image['filename'], image['subfolder'], image['type'])
                            if image_data:
                                images_output.append(image_data)
                        output_images[node_id] = images_output
                        break
            except Exception as e:
                logging.error(f"Error receiving WebSocket message: {str(e)}")
                break

        return output_images
