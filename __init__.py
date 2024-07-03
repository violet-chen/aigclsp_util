import os
import server
import folder_paths
import json
import asyncio
import base64
import uuid
import ssl
from io import BytesIO

from aiohttp import web, ClientSession, WSMsgType
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from .core.call_comfyui import CallComfyUI
current_dir = os.path.dirname(os.path.abspath(__file__))

@server.PromptServer.instance.routes.get("/aigclsp_util/send_status")
async def get_status(request):
    # 实例id
    if os.environ.get('INSTANCE_ID'):
        INSTANCE_ID = str(os.environ.get('INSTANCE_ID'))
    else:
        INSTANCE_ID = ""
        print(f"Send_Status|ERROR|Cannot find env INSTANCE_ID")
    # 用户ID
    if os.environ.get('USER_ID'):
        USER_ID = str(os.environ.get('USER_ID'))
    else:
        USER_ID = ""
        print(f"Send_Status|ERROR|Cannot find env USER_ID")
    # 团队名称
    if os.environ.get('PROJECT_NAME'):
        PROJECT_NAME = str(os.environ.get('PROJECT_NAME'))
    else:
        PROJECT_NAME = ""
        print(f"Send_Status|ERROR|Cannot find env PROJECT_NAME|It is private mode")
    # OBS产品名称, 历史原因用了PRODUCT_ID
    if os.environ.get('PRODUCT_ID'):
        PRODUCT_NAME = str(os.environ.get('PRODUCT_ID'))
    else:
        PRODUCT_NAME = ""
        print(f"Send_Status|ERROR|Cannot find env PRODUCT_ID name|It is private mode")
    # OBS项目ID
    if os.environ.get('PRODUCT_FIXED_ID'):
        PRODUCT_ID = str(os.environ.get('PRODUCT_FIXED_ID'))
    else:
        PRODUCT_ID = ""
        print(f"Send_Status|ERROR|Cannot find env PRODUCT_FIXED_ID|It is private mode")
    # 应用的镜像名称
    if os.environ.get('APP_NAME'):
        APP_NAME = str(os.environ.get('APP_NAME'))
    else:
        APP_NAME = "comfyui"
        print(f"Send_Status|ERROR|Cannot find env APP_NAME|DEFAULT comfyui")
    # 实例状态上报的地址
    if os.environ.get('ReportStatus_URL'):
        ReportStatus_URL = str(os.environ.get('ReportStatus_URL'))
    else:
        ReportStatus_URL = "http://aidrawing.ultrongw.woa.com/cluster/report_status"
        print(f"Send_Status|ERROR|Cannot find env ReportStatus_URL, use {ReportStatus_URL}")
    
    data = {
            "business_id": "aidrawing",
            "product_id":PRODUCT_NAME, # 历史原因这里报的是name
            "product_name":PRODUCT_NAME, # 用于纠正
            "product_fixed_id":PRODUCT_ID,
            "project_id":PROJECT_NAME,
            "group_id":"",
            "user_id":USER_ID,
            "instance_id": INSTANCE_ID,
            "gpu_usage":50,
            "set":22,
            "app_name":APP_NAME
            }
    async with aiohttp.ClientSession() as session:
        for i in range(4):
            try:
                async with session.post(ReportStatus_URL, json=json.loads(json.dumps(data))) as resp:
                    print(f'Send_Status|ERROR|send_status rsp: {await resp.text()}|data:{data}')
                    status = resp.status
                    if status == 200:
                        message = {'message':'OK','status':200,'data':data}
                        return web.json_response(message, content_type='application/json')
            except aiohttp.ClientError as e:
                print(f'Send_Status|ERROR|report_status err: {e}')
                if i < 3:
                    await asyncio.sleep(1)
                    continue
                else:
                    message = {'message':'ERROR','status':500,'error':str(e)}
                    return web.json_response(message, content_type='application/json')


@server.PromptServer.instance.routes.get("/aigclsp_util/productid")
async def get_product_id(request):

    PRODUCT_ID = ""
    if os.environ.get('PRODUCT_ID'):
        PRODUCT_ID = str(os.environ.get('PRODUCT_ID'))
    else:
        print(f"Cannot find env PRODUCT_ID")
    return web.json_response({"productid":PRODUCT_ID}, content_type='application/json')

@server.PromptServer.instance.routes.get("/aigclsp_util/env/{addr}")
async def get_env_value(request):
    addr = request.match_info['addr']
    print(addr)
    Value = ""
    if os.environ.get(addr):
        Value = str(os.environ.get(addr))
    else:
        print(f"Cannot find env {addr}")
    return web.json_response({addr:Value}, content_type='application/json')

@server.PromptServer.instance.routes.get("/aigclsp_util/get_info/{addr}")
async def get_checkpoints(request):
    addr = request.match_info['addr']
    checkpoints = folder_paths.get_filename_list(addr)
    return web.json_response({addr:checkpoints}, content_type='application/json')

@server.PromptServer.instance.routes.post("/aigclsp_util/comfy_workflow/image_matting")
async def image_matting(request):
    try:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        data = await request.json()
        server_address = data.get('server_address')
        points = data.get('points')
        client_id = data.get('client_id')
        labels = data.get('labels')
        input_image = data.get('input_image')
        input_image = base64.b64decode(input_image)
        input_image = BytesIO(input_image)
        image_id = str(uuid.uuid4())
        input_image.name = image_id+'.png'    
        workflow_path = os.path.join(current_dir,'workflows','image_matting.json')
        comfyui  =  CallComfyUI(server_address,client_id,ssl_context)
        print("开始上传图片")
        image_name = await comfyui.upload_image(input_image)
        print("上传的图片的名字为: " + image_name)
        if image_name:
            with open(workflow_path,'r') as f:
                prompt = json.load(f)
            prompt['5']['inputs']['image'] = image_name
            prompt['9']['inputs']['points'] = points
            prompt['9']['inputs']['labels'] = labels
            # 使用 WebSocket 连接处理图像生成
            async with ClientSession() as session:
                async with session.ws_connect(f"{server_address}/ws?clientId={client_id}",ssl=False) as ws:
                    final_images = await comfyui.get_images(ws, prompt)
                    if not final_images or '17' not in final_images or not final_images['17']:
                        return web.json_response({"status": 500, "error": "Failed to process image"}, content_type="application/json")  
                    # 获取最终图像并编码为 base64 返回
                    final_image = final_images['17'][0]
                    final_image_base64 = base64.b64encode(final_image).decode('utf-8')
                    return_data = {"status": 200, "final_image": final_image_base64}
                    return web.json_response(return_data, content_type="application/json")
        else:
            return_data = {"status": 500, "error": "上传图片失败"}
            return web.json_response(return_data, content_type="application/json")

    except Exception as e:
        return web.json_response({"status": 500, "error": str(e)}, content_type="application/json")
