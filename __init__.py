import importlib
import os
import server
import folder_paths
import json
import asyncio
import base64
import uuid
import requests
from io import BytesIO
import subprocess
import aiohttp
from aiohttp import web, ClientSession
from .core.call_comfyui import CallComfyUI
try:
    from psd_tools import PSDImage
except:
    pass

# 导入自定义节点
node_list = [
    "common"
]
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
for module_name in node_list:
    imported_module = importlib.import_module(".nodes.{}".format(module_name), __name__)
    NODE_CLASS_MAPPINGS = {**NODE_CLASS_MAPPINGS, **imported_module.NODE_CLASS_MAPPINGS}
    NODE_DISPLAY_NAME_MAPPINGS = {**NODE_DISPLAY_NAME_MAPPINGS, **imported_module.NODE_DISPLAY_NAME_MAPPINGS}
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

current_dir = os.path.dirname(os.path.abspath(__file__))

# 自定义接口
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
        data = await request.json()
        points = data.get('points')
        client_id = data.get('client_id')
        labels = data.get('labels')
        input_image = data.get('input_image')
        port = data.get('port')
        input_image = base64.b64decode(input_image)
        input_image = BytesIO(input_image)
        image_id = str(uuid.uuid4())
        input_image.name = image_id+'.png'    
        workflow_path = os.path.join(current_dir,'workflows','image_matting.json')
        comfyui  =  CallComfyUI(port,client_id)
        # 上传图片到服务器
        image_name = await comfyui.upload_image(input_image)
        if image_name:
            # 编辑comfyui工作流
            with open(workflow_path,'r') as f:
                prompt = json.load(f)
            prompt['5']['inputs']['image'] = image_name
            prompt['9']['inputs']['points'] = points
            prompt['9']['inputs']['labels'] = labels
            # 使用 WebSocket 连接处理图像生成
            async with ClientSession() as session:
                async with session.ws_connect(f"http://localhost:{port}/ws?clientId={client_id}") as ws:
                    final_images = await comfyui.get_images(ws, prompt)
                    if not final_images or '17' not in final_images or not final_images['17']:
                        return web.json_response({"status": 500, "error": "Failed to process image"}, content_type="application/json")  
                    # 获取最终图像并编码为 base64 返回
                    final_image = final_images['17'][1]
                    final_image_base64 = base64.b64encode(final_image).decode('utf-8')
                    translucent_image = final_images['17'][0]
                    translucent_image_base64 = base64.b64encode(translucent_image).decode('utf-8')
                    return_data = {"status": 200, "final_image": final_image_base64,'translucent_image': translucent_image_base64}
                    return web.json_response(return_data, content_type="application/json")
        else:
            return_data = {"status": 500, "error": "上传图片失败"}
            return web.json_response(return_data, content_type="application/json")

    except Exception as e:
        return web.json_response({"status": 500, "error": str(e)}, content_type="application/json")
    

@server.PromptServer.instance.routes.post("/aigclsp_util/comfy_workflow")
async def comfyui_workflow(request):
    # 通过接口调用执行comfyui工作流
    try:
        data = await request.json()
        client_id= str(uuid.uuid4())
        port = data.get('port','8081')
        prompt = data.get('prompt',{}) # 必传,comfyui工作流,dict格式
        upload_images = data.get('upload_images',{}) # 上传的图片,{图片对应的工作流中的id,图片base64}
        result_id = data.get('result_id','') # 必传,工作流执行时最终结果的id
        pipeline_name = data.get('pipeline_name','aigclsp_util') # 必传,工作流名称
        if prompt:
            comfyui = CallComfyUI(port,client_id)
            if upload_images:
                for image_id, image_base64 in upload_images.items():
                    image_name = await comfyui.upload_image(BytesIO(base64.b64decode(image_base64)))
                    prompt[image_id]['inputs']['image'] = image_name
            async with ClientSession() as session:
                async with session.ws_connect(f"http://localhost:{port}/ws?clientId={client_id}") as ws:
                    result_datas = await comfyui.get_images(ws, prompt,pipeline_name=pipeline_name)
                    # 如果又报错就返回报错信息
                    if isinstance(result_datas, str):
                        return web.json_response({"status": 500, "error": result_datas}, content_type="application/json")   
                    else:
                        result_datas = result_datas.get(result_id,[])
                        if isinstance(result_datas, dict):
                            # 如果最终数据是字典,表示返回结果不是图片,则直接返回
                            return_data = {"status": 200, "result_datas": result_datas}
                            return web.json_response(return_data, content_type="application/json")
                        else:
                            # 将图片数据列表转换为base64列表
                            result_datas = [base64.b64encode(x).decode('utf-8') if isinstance(x, bytes) else x 
                                            for x in result_datas ]

                            return_data = {"status": 200, "result_datas": result_datas}
                            return web.json_response(return_data, content_type="application/json")
        
    except Exception as e:
        return web.json_response({"status": 500, "error": str(e)}, content_type="application/json")

@server.PromptServer.instance.routes.post("/aigclsp_util/png2psd")
async def png2psd(request):
    try:
        data = await request.json()
        pngName_pngBase64:dict = data.get('pngs') # {png_name:png_base64}
        if pngName_pngBase64:
            # 生成临时文件
            temp_uuid = str(uuid.uuid4())
            temp_dir_path = os.path.join(current_dir, 'temp_dir_' + temp_uuid)
            if not os.path.exists(temp_dir_path):
                os.makedirs(temp_dir_path)
            temp_psd_path = os.path.join(temp_dir_path, temp_uuid+'.psd')
            temp_pngs_str = [] # '-label', 'layer0', 'path/layer0.png'
            temp_pngs_path = []
            psd_layer_names = [] # 命令行工具不支持中文,因此需要获取名称列表,通过psd-tools去二次修改
            pngs_num_str = ','.join(str(i) for i in range(len(pngName_pngBase64))) # 如果是3就对应0,1,2 是2就对应0,1
            for png_name,png_data_base64 in pngName_pngBase64.items():
                png_data = base64.b64decode(png_data_base64)
                png_temp_path = os.path.join(temp_dir_path, png_name+'.png')
                with open(png_temp_path, 'wb') as f:
                    f.write(png_data)
                # 每个png图片对应的名字和路径的
                temp_pngs_str.append('-label')
                temp_pngs_str.append(png_name)
                psd_layer_names.append(png_name)
                temp_pngs_str.append(png_temp_path)
                
                temp_pngs_path.append(png_temp_path)
            # png转psd的命令行
            cmd = ['convert'] + temp_pngs_str + ['(', '-clone', pngs_num_str, '-flatten', ')', '-insert', '0', str(temp_psd_path)]
            print(f"[png2psd]:{cmd}")
            subprocess.run(cmd, check=True)
            # 修改psd文件的图层名称
            psd = PSDImage.open(temp_psd_path)
            for index,layer in enumerate(psd):
                # 修改图层名称
                layer.name = psd_layer_names[index]
            psd.save(temp_psd_path)
            # 得到psd文件的base64
            with open(temp_psd_path, 'rb') as f:
                psd_data = f.read()
            psd_base64 = base64.b64encode(psd_data).decode('utf-8')
            # 删除临时文件
            for png_path in temp_pngs_path:
                os.remove(png_path)
            os.remove(temp_psd_path)
            os.rmdir(temp_dir_path)

            return web.json_response({"status": 200, "psd": psd_base64}, content_type="application/json")

    except Exception as e:
        return web.json_response({"status": 500, "error": str(e)}, content_type="application/json")
    
@server.PromptServer.instance.routes.post("/public/SD/get_data")
async def get_data(request):
    data = await request.json()
    url = data.get('url',None)
    json_data = {"url":url}
    # 调用devcloud上的接口
    try:
        response = requests.post(f"http://21.0.5.34:8081/public/SD/get_data",json=json_data)
        print(f"状态码: {response.status_code}")
        # 检查响应状态码
        if response.status_code == 200:
            # 检查内容类型
            content_type = response.headers.get('Content-Type', '')
            if 'image' in content_type:
                # 如果是图片，直接返回图片内容
                print("返回图片")
                return web.Response(body=response.content, content_type=content_type)
            else:
                # 如果是其他类型的数据，尝试解析为 JSON
                try:
                    data_param = response.json()
                    print("返回json")
                    return web.json_response(data_param)  # 返回 JSON 响应
                except ValueError:
                    print("报错")
                    return web.json_response({"error": "响应不是有效的 JSON 格式"}, status=500)
        else:
            return web.json_response({"error": f"请求失败，状态码: {response.status_code}"}, status=response.status_code)

    except requests.exceptions.RequestException as e:
        print(f"请求异常: {e}")
        return web.json_response({"error": str(e)}, status=500)