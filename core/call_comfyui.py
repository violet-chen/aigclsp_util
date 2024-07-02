import aiohttp
import json
import asyncio
import logging
from multidict import MultiDict

class CallComfyUI:
    
    def __init__(self, server_address, client_id):
        self.server_address = server_address
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
                async with session.post(f"http://{self.server_address}/upload/image", data=body, params=data) as response:
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
                async with session.post(f"http://{self.server_address}/prompt", data=data) as response:
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
                async with session.get(f"http://{self.server_address}/view", params=data) as response:
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
                async with session.get(f"http://{self.server_address}/history/{prompt_id}") as response:
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
        
        prompt_id = prompt_data['prompt_id']
        output_images = {}

        while True:
            try:
                out = await ws.receive()
                if out.type == aiohttp.WSMsgType.TEXT:
                    message = json.loads(out.data)
                    if message['type'] == 'executing':
                        data = message['data']
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            break  # 执行完成
                else:
                    continue  # 预览是二进制数据
            except Exception as e:
                logging.error(f"Error receiving WebSocket message: {str(e)}")
                break

        history_data = await self.get_history(prompt_id)
        if not history_data:
            return None
        
        history = history_data[prompt_id]
        for node_id, node_output in history['outputs'].items():
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = await self.get_image(image['filename'], image['subfolder'], image['type'])
                    if image_data:
                        images_output.append(image_data)
                output_images[node_id] = images_output

        return output_images
