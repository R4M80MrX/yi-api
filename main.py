from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import json
import os
from dashscope import Generation
import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid
import random

DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
app = FastAPI(title="占卜应用后端")

# 线程池执行器，用于运行同步API调用
executor = ThreadPoolExecutor(max_workers=5)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据模型
class DivinationRequest(BaseModel):
    matter: str
    hexagram: str
    lines: List[str]

class DivinationResponse(BaseModel):
    interpretation: str
    advice: str

class TodoItem(BaseModel):
    title: str
    description: str
    hexagram: Optional[str] = None
    completed: bool = False
    createdAt: str

class TodoItemResponse(BaseModel):
    id: str
    title: str
    description: str
    hexagram: Optional[str] = None
    completed: bool
    createdAt: str

class GenerateHexagramRequest(BaseModel):
    matter: str

class GenerateHexagramResponse(BaseModel):
    id: str
    lines: List[str]
    hexagram: str

class DivinationResultResponse(BaseModel):
    interpretation: str
    advice: str
    is_ready: bool

# 数据存储路径
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TODOS_FILE = os.path.join(DATA_DIR, "todos.json")
DIVINATIONS_FILE = os.path.join(DATA_DIR, "divinations.json")
TRIGRAMS_FILE = os.path.join(DATA_DIR, "trigrams.json")
HEXAGRAMS_FILE = os.path.join(DATA_DIR, "hexagrams.json")

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 加载待办事项数据
def load_todos():
    if os.path.exists(TODOS_FILE):
        with open(TODOS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# 保存待办事项数据
def save_todos(todos):
    with open(TODOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(todos, f, ensure_ascii=False, indent=2)

# 加载占卜记录数据
def load_divinations():
    if os.path.exists(DIVINATIONS_FILE):
        with open(DIVINATIONS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# 保存占卜记录数据
def save_divinations(divinations):
    with open(DIVINATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(divinations, f, ensure_ascii=False, indent=2)

# 加载八卦数据
def load_trigrams() -> Dict[str, Tuple[str, str]]:
    if os.path.exists(TRIGRAMS_FILE):
        with open(TRIGRAMS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {k: tuple(v) for k, v in data.items()}
    return {}

# 加载六十四卦数据
def load_hexagrams() -> Dict[str, Tuple[str, str]]:
    if os.path.exists(HEXAGRAMS_FILE):
        with open(HEXAGRAMS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {k: tuple(v) for k, v in data.items()}
    return {}

# 加载卦象数据
TRIGRAMS = load_trigrams()
HEXAGRAMS = load_hexagrams()

# 存储正在进行的占卜结果
divination_results: Dict[str, Dict] = {}

# 使用DashScope调用大模型API进行占卜解释（同步版本）
def _get_ai_interpretation_sync(matter: str, hexagram: str, lines: List[str]):
    if not DASHSCOPE_API_KEY:
        raise ValueError("DASHSCOPE_API_KEY环境变量未设置")
    
    # 将爻线转换为更易理解的格式
    line_descriptions = []
    for i, line in enumerate(lines):
        position = 6 - i  # 从下往上数
        if line == "yang":
            line_descriptions.append(f"第{position}爻：少阳")
        elif line == "yin":
            line_descriptions.append(f"第{position}爻：少阴")
        elif line == "old-yang":
            line_descriptions.append(f"第{position}爻：老阳（变爻）")
        elif line == "old-yin":
            line_descriptions.append(f"第{position}爻：老阴（变爻）")
    
    lines_text = "\n".join(line_descriptions)
    
    #     爻线情况：
    # {lines_text}
    # 构建提示词
    prompt = f"""
    你是一位精通周易的大师。请根据以下信息进行占卜解读：

    占卜事项：{matter}
    得到的卦象：{hexagram}

    请提供：
    1. 对这个卦象的整体解读
    2. 针对占卜事项的具体分析
    3. 实用的建议和行动指南

    解读要符合中国传统文化，既要有深度，又要通俗易懂，长度在300字左右。
    """
    
    try:
        response = Generation.call(
            model='qwen-max',
            api_key=DASHSCOPE_API_KEY,
            prompt=prompt,
            temperature=0.7,
            max_tokens=800,
            top_p=0.8,
        )
        
        if response.status_code == 200:
            # 解析返回的文本
            interpretation = response.output.text.strip()
            
            # 简单分割建议和解读
            parts = interpretation.split("建议：")
            if len(parts) > 1:
                main_interpretation = parts[0].strip()
                advice = "建议：" + parts[1].strip()
            else:
                main_interpretation = interpretation
                advice = "根据卦象，建议谨慎行事，顺应自然。"
                
            return {
                "interpretation": main_interpretation,
                "advice": advice
            }
        else:
            # 如果API调用失败，返回错误信息
            error_msg = f"API调用失败: {response.status_code}, {response.message}"
            print(error_msg)
            return {
                "interpretation": f"卦象{hexagram}表示...(API调用失败，使用默认解读)",
                "advice": "建议顺应自然，谨慎行事。"
            }
    except Exception as e:
        # 捕获所有异常
        error_msg = f"调用大模型API时发生错误: {str(e)}"
        print(error_msg)
        return {
            "interpretation": f"卦象{hexagram}表示...(API调用失败，使用默认解读)",
            "advice": "建议顺应自然，谨慎行事。"
        }

# 异步包装器，将同步函数转换为异步函数
async def get_ai_interpretation(matter: str, hexagram: str, lines: List[str]):
    # 使用线程池执行同步API调用
    return await asyncio.get_event_loop().run_in_executor(
        executor, 
        _get_ai_interpretation_sync, 
        matter, 
        hexagram, 
        lines
    )

# API路由
@app.post("/api/divination/interpret", response_model=DivinationResponse)
async def interpret_divination(request: DivinationRequest):
    """
    根据用户提供的事项、卦象和爻线进行占卜解读
    """
    try:
        # 异步调用大模型API进行解读
        ai_response = await get_ai_interpretation(
            request.matter, 
            request.hexagram, 
            request.lines
        )
        
        # 保存占卜记录
        divinations = load_divinations()
        divination_record = {
            "id": str(uuid.uuid4()),
            "matter": request.matter,
            "hexagram": request.hexagram,
            "lines": request.lines,
            "interpretation": ai_response["interpretation"],
            "advice": ai_response["advice"],
            "createdAt": datetime.now().isoformat()
        }
        divinations.append(divination_record)
        save_divinations(divinations)
        
        return DivinationResponse(
            interpretation=ai_response["interpretation"],
            advice=ai_response["advice"]
        )
    except Exception as e:
        # 如果发生错误，返回默认解读
        print(f"占卜解读失败: {str(e)}")
        return DivinationResponse(
            interpretation=f"关于'{request.matter}'的卦象解读：{request.hexagram}表示变化与机遇并存。",
            advice="建议您保持平常心，顺应自然变化。"
        )

@app.post("/api/todos", response_model=TodoItemResponse)
async def create_todo(todo: TodoItem):
    """
    创建新的待办事项
    """
    try:
        todos = load_todos()
        
        # 生成唯一ID
        todo_id = str(uuid.uuid4())
        
        # 创建新的待办事项
        new_todo = {
            "id": todo_id,
            "title": todo.title,
            "description": todo.description,
            "hexagram": todo.hexagram,
            "completed": todo.completed,
            "createdAt": todo.createdAt
        }
        
        # 添加到列表
        todos.append(new_todo)
        
        # 保存到文件
        save_todos(todos)
        
        return new_todo
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加待办事项失败: {str(e)}")

# 获取所有待办事项
@app.get("/api/todos", response_model=List[TodoItemResponse])
async def get_todos():
    """
    获取所有待办事项
    """
    return load_todos()

# 更新待办事项状态
@app.put("/api/todos/{todo_id}", response_model=TodoItemResponse)
async def update_todo(todo_id: str, completed: bool):
    """
    更新待办事项的完成状态
    """
    try:
        todos = load_todos()
        
        # 查找并更新待办事项
        for todo in todos:
            if todo["id"] == todo_id:
                todo["completed"] = completed
                save_todos(todos)
                return todo
        
        raise HTTPException(status_code=404, detail="待办事项未找到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新待办事项失败: {str(e)}")

# 删除待办事项
@app.delete("/api/todos/{todo_id}")
async def delete_todo(todo_id: str):
    """
    删除待办事项
    """
    try:
        todos = load_todos()
        
        # 查找并删除待办事项
        for i, todo in enumerate(todos):
            if todo["id"] == todo_id:
                del todos[i]
                save_todos(todos)
                return {"message": "待办事项已删除"}
        
        raise HTTPException(status_code=404, detail="待办事项未找到")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除待办事项失败: {str(e)}")

# 获取占卜历史记录
@app.get("/api/divinations", response_model=List[dict])
async def get_divinations():
    """
    获取所有占卜历史记录
    """
    return load_divinations()

def generate_random_line():
    coin_results = [random.randint(0, 1) for _ in range(3)]
    yang_count = sum(coin_results)
    
    if yang_count == 3:
        return 'old-yang'
    elif yang_count == 2:
        return 'yang'
    elif yang_count == 1:
        return 'yin'
    else:
        return 'old-yin'

def get_trigram(lines: List[str]) -> str:
    """将三个爻转换为三进制字符串"""
    binary = ""
    for line in lines:
        if line in ['yang', 'old-yang']:
            binary += "1"
        else:
            binary += "0"
    return binary

def get_hexagram_name(lines: List[str]) -> str:
    """根据六个爻计算卦象名称"""
    # 将爻线转换为六位二进制字符串
    binary = ""
    for line in lines:
        if line in ['yang', 'old-yang']:
            binary += "1"
        else:
            binary += "0"
    
    # 获取上下卦的三位二进制
    upper = binary[0:3]
    lower = binary[3:6]
    
    # 查找上下卦名称
    upper_trigram = TRIGRAMS.get(upper, ("", ""))[1]
    lower_trigram = TRIGRAMS.get(lower, ("", ""))[1]
    
    # 查找完整卦象名称
    hexagram_data = HEXAGRAMS.get(binary)
    if hexagram_data:
        return hexagram_data[0]
    
    # 如果没有找到完整卦象，使用上下卦组合
    return f"{lower_trigram}{upper_trigram}卦"

def generate_divination_interpretation(divination_id: str, matter: str, hexagram: str, lines: List[str]):
    """在后台生成占卜解读"""
    try:
        result = _get_ai_interpretation_sync(matter, hexagram, lines)
        divination_results[divination_id].update({
            "interpretation": result["interpretation"],
            "advice": result["advice"],
            "is_ready": True
        })
    except Exception as e:
        print(f"生成占卜解读失败: {str(e)}")
        divination_results[divination_id].update({
            "interpretation": f"卦象{hexagram}表示...(生成失败，请重试)",
            "advice": "建议顺应自然，谨慎行事。",
            "is_ready": True
        })

@app.post("/api/divination/generate", response_model=GenerateHexagramResponse)
async def generate_hexagram(request: GenerateHexagramRequest, background_tasks: BackgroundTasks):
    """
    生成卦象和爻线，并在后台开始生成解读
    """
    try:
        # 生成唯一ID
        divination_id = str(uuid.uuid4())
        
        # 生成六个爻
        lines = [generate_random_line() for _ in range(6)]
        
        # 根据爻线计算卦象
        hexagram = get_hexagram_name(lines)
        
        # 初始化结果存储
        divination_results[divination_id] = {
            "interpretation": "",
            "advice": "",
            "is_ready": False
        }
        
        # 在后台开始生成解读
        background_tasks.add_task(
            generate_divination_interpretation,
            divination_id,
            request.matter,
            hexagram,
            lines
        )
        
        return GenerateHexagramResponse(
            id=divination_id,
            lines=lines,
            hexagram=hexagram
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成卦象失败: {str(e)}")

@app.get("/api/divination/result/{divination_id}", response_model=DivinationResultResponse)
async def get_divination_result(divination_id: str):
    """
    获取占卜解读结果
    """
    try:
        result = divination_results.get(divination_id)
        if not result:
            raise HTTPException(status_code=404, detail="占卜结果未找到")
        
        return DivinationResultResponse(
            interpretation=result.get("interpretation", ""),
            advice=result.get("advice", ""),
            is_ready=result.get("is_ready", False)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取占卜结果失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=3002, reload=True)
