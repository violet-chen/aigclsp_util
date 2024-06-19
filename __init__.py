import os
import server
import folder_paths
import time
import json
import requests
import aiohttp
import asyncio
from aiohttp import web
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

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