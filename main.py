import os
import json
import torch
import numpy as np
import pandas as pd
from PIL import Image
import cv2
import logging
from pathlib import Path
from typing import List, Dict, Union, Tuple, Optional
import chromadb
from chromadb.config import Settings
import clip
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import hashlib
import base64
from io import BytesIO
import requests
import pymysql
from urllib.parse import urlparse
import warnings
import time
import re

# 忽略一些警告
warnings.filterwarnings("ignore", category=UserWarning)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 设备配置
device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"使用设备: {device}")

class OpenRouterProcessor:
    """OpenRouter大语言模型处理器"""
    
    def __init__(self, api_key: str, model: str = "anthropic/claude-3-haiku"):
        """
        初始化OpenRouter处理器
        Args:
            api_key: OpenRouter API密钥
            model: 使用的模型名称
        """
        self.api_key = api_key
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-repo",  # 可选
            "X-Title": "CLIP Image Search System"  # 可选
        }
        
        # 测试连接
        self._test_connection()
    
    def _test_connection(self):
        """测试API连接"""
        try:
            test_response = self.analyze_query(
                "测试连接", 
                ["测试"], 
                max_tokens=10,
                timeout=5
            )
            logger.info("✅ OpenRouter连接测试成功")
        except Exception as e:
            logger.warning(f"⚠️ OpenRouter连接测试失败: {e}")
    
    def analyze_query(self, user_query: str, available_tags: List[str], 
                     max_tokens: int = 500, timeout: int = 10) -> Dict:
        """
        分析用户查询并提取相关标签和关键词
        Args:
            user_query: 用户的自然语言查询
            available_tags: 可用的标签列表
            max_tokens: 最大token数
            timeout: 超时时间
        """
        try:
            # 构建提示词
            prompt = self._build_analysis_prompt(user_query, available_tags)
            
            payload = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一个专业的汽车图片搜索助手，擅长理解用户的自然语言描述并提取相关的视觉特征和标签。"
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3,
                "top_p": 0.9
            }
            
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # 解析LLM的回复
                analysis = self._parse_llm_response(content)
                
                logger.info(f"OpenRouter分析完成: {analysis.get('summary', '')}")
                return analysis
                
            else:
                logger.error(f"OpenRouter API错误: {response.status_code} - {response.text}")
                return self._fallback_analysis(user_query, available_tags)
                
        except Exception as e:
            logger.error(f"OpenRouter分析失败: {e}")
            return self._fallback_analysis(user_query, available_tags)
    
    def _build_analysis_prompt(self, user_query: str, available_tags: List[str]) -> str:
        """构建分析提示词"""
        
        # 将标签按类别组织（基于您提供的tag_keywords结构）
        tag_categories = {
            "色彩": ["单色系", "对比色", "黑白", "金属色", "哑光色", "鲜艳色彩", "柔和色彩", "复古色彩", "梦幻色彩"],
            "色调":["冷色调", "暖色调", "中性色调", "高对比度", "低对比度", "明亮色调", "暗黑色调", "黄昏色调", "褪色效果", "夜景色调", "饱和色调"],
            "光线":["自然光线", "人工光线", "柔和光线", "强烈光线", "侧光", "逆光", "顺光", "漫射光", "光影对比", "黄金时刻光线", "蓝调时刻光线", "夜晚光线"],
            "构图":["中心构图", "对称构图", "三分法构图", "前景框架", "引导线构图", "重复元素", "负空间构图", "对角线构图", "层次构图", "最小化构图", "黄金比例构图"],
            "质感":["金属质感", "光滑质感", "哑光质感", "粗糙质感", "反光质感", "皮革质感", "科技质感", "奢华质感", "复古质感", "自然质感"],
            "人车互动":["生活", "家庭", "休闲", "街拍", "城市", "风景", "建筑", "驾驶场景", "家庭出游", "商务出行", "休闲旅行", "户外探险", "城市通勤", "社交聚会", "展示场景", "试驾场景", "儿童互动", "宠物互动", "情侣场景"],
            "画面风格":["摄影", "CG", "极简", "商业风格", "生活纪实", "复古风格", "未来风格", "艺术创意", "工业风格", "运动风格", "奢华风格", "科技风格", "电影感"],
            "拍摄视角":["特写","正面视角", "侧面视角", "45度角", "后视图", "俯视图", "仰视角", "车内视角", "全景视角", "鸟瞰视角",],
            "车型": ["轿车", "SUV", "越野", "房车", "MPV", "紧凑型轿车", "中型轿车", "豪华轿车", "跑车", "皮卡", "古典车", "电动车"],
        }
        
        # 从可用标签中筛选每个类别的标签
        available_by_category = {}
        for category, category_tags in tag_categories.items():
            available_by_category[category] = [tag for tag in category_tags if tag in available_tags]
        
        prompt = f"""
用户查询："{user_query}"

请分析这个查询，并以JSON格式返回以下信息：

1. **summary**: 用1-2句话总结用户想要找什么样的汽车图片
2. **key_concepts**: 提取3-5个核心概念
3. **visual_keywords**: 适合CLIP视觉搜索的英文关键词（3-5个）
4. **matched_tags**: 从下面的标签库中选择最相关的标签（每个类别最多3个）
5. **scene_type**: 主要场景类型
6. **style_preference**: 风格偏好
7. **search_strategy**: 建议的搜索策略（"tag_focused"、"visual_focused"或"balanced"）

可用标签库：
{json.dumps(available_by_category, ensure_ascii=False, indent=2)}

请返回标准的JSON格式，确保所有字段都存在。如果某个类别没有匹配的标签，返回空列表。

示例输出格式：
{{
    "summary": "用户想要寻找家庭温馨场景的汽车图片",
    "key_concepts": ["家庭", "温馨", "休闲"],
    "visual_keywords": ["family car", "warm lighting", "casual scene"],
    "matched_tags": {{
            "色彩": [],
            "色调":[],
            "光线":["自然光线"],
            "构图":["中心构图"],
            "质感":[],
            "人车互动":["生活"],
            "画面风格":["极简"],
            "拍摄视角":["正面视角"],
            "车型": ["轿车"],
    }},
    "scene_type": "家庭生活",
    "style_preference": "温馨自然",
    "search_strategy": "balanced"
}}
"""
        return prompt
    
    def _parse_llm_response(self, content: str) -> Dict:
        """解析LLM返回的内容"""
        try:
            # 尝试直接解析JSON
            if content.strip().startswith('{') and content.strip().endswith('}'):
                return json.loads(content)
            
            # 尝试提取JSON部分
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                return json.loads(json_str)
            
            # 如果无法解析JSON，返回基础分析
            logger.warning("无法解析LLM返回的JSON，使用文本解析")
            return self._parse_text_response(content)
            
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            return self._create_default_analysis(content)
    
    def _parse_text_response(self, content: str) -> Dict:
        """解析文本形式的响应"""
        analysis = {
            "summary": "",
            "key_concepts": [],
            "visual_keywords": [],
            "matched_tags": {},
            "scene_type": "",
            "style_preference": "",
            "search_strategy": "balanced"
        }
        
        # 简单的文本解析逻辑
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if 'summary' in line.lower() or '总结' in line:
                current_section = 'summary'
            elif 'key_concepts' in line.lower() or '核心概念' in line:
                current_section = 'key_concepts'
            elif 'visual_keywords' in line.lower() or '视觉关键词' in line:
                current_section = 'visual_keywords'
            elif current_section and ':' in line:
                value = line.split(':', 1)[1].strip()
                if current_section == 'summary':
                    analysis['summary'] = value
                elif current_section in ['key_concepts', 'visual_keywords']:
                    # 分割并清理
                    items = [item.strip() for item in value.replace(',', '，').split('，') if item.strip()]
                    analysis[current_section] = items
        
        return analysis
    
    def _create_default_analysis(self, content: str) -> Dict:
        """创建默认分析结果"""
        return {
            "summary": content[:100] if content else "无法解析查询",
            "key_concepts": [],
            "visual_keywords": [],
            "matched_tags": {},
            "scene_type": "未知",
            "style_preference": "未知", 
            "search_strategy": "balanced"
        }
    
    def _fallback_analysis(self, user_query: str, available_tags: List[str]) -> Dict:
        """备用分析方法（不依赖LLM）"""
        logger.info("使用备用分析方法")
        
        # 简单的关键词匹配
        query_lower = user_query.lower()
        matched_tags = []
        
        for tag in available_tags:
            if tag.lower() in query_lower:
                matched_tags.append(tag)
        
        # 基础场景识别
        scene_keywords = {
            "家庭": ["家庭", "亲子", "家人", "温馨"],
            "商务": ["商务", "办公", "工作", "正式"],
            "休闲": ["休闲", "放松", "度假", "娱乐"],
            "城市": ["城市", "都市", "街道", "市区"],
            "自然": ["自然", "风景", "户外", "山", "海"]
        }
        
        detected_scene = "未知"
        for scene, keywords in scene_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_scene = scene
                break
        
        return {
            "summary": f"查询: {user_query}",
            "key_concepts": user_query.split()[:5],
            "visual_keywords": user_query.split()[:3],
            "matched_tags": {"通用": matched_tags[:5]},
            "scene_type": detected_scene,
            "style_preference": "未指定",
            "search_strategy": "balanced"
        }

class CLIPImageEncoder:
    """CLIP图像和文本编码器 - 增强版"""
    
    SUPPORTED_MODELS = [
        "ViT-B/32", "ViT-B/16", "ViT-L/14", "ViT-L/14@336px",
        "RN50", "RN101", "RN50x4", "RN50x16", "RN50x64"
    ]
    
    def __init__(self, model_name: str = "ViT-B/32"):
        """
        初始化CLIP模型
        Args:
            model_name: CLIP模型名称
        """
        if model_name not in self.SUPPORTED_MODELS:
            logger.warning(f"模型 {model_name} 可能不受支持，支持的模型: {self.SUPPORTED_MODELS}")
        
        self.model_name = model_name
        self.device = device
        
        try:
            self.model, self.preprocess = clip.load(model_name, device=self.device)
            self.model.eval()
            logger.info(f"CLIP模型 {model_name} 已加载到 {self.device}")
            
            # 获取特征维度
            with torch.no_grad():
                dummy_image = torch.randn(1, 3, 224, 224).to(self.device)
                dummy_features = self.model.encode_image(dummy_image)
                self.feature_dim = dummy_features.shape[1]
            
            logger.info(f"特征维度: {self.feature_dim}")
            
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise
    
    def encode_image_from_path(self, image_path: str) -> Optional[np.ndarray]:
        """
        从本地文件路径编码图片
        Args:
            image_path: 图片的绝对路径
        Returns:
            图片特征向量
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(image_path):
                logger.warning(f"图片文件不存在: {image_path}")
                return None
            
            # 加载和预处理图片
            image = Image.open(image_path).convert('RGB')
            image_input = self.preprocess(image).unsqueeze(0).to(self.device)
            
            # 编码图片
            with torch.no_grad():
                image_features = self.model.encode_image(image_input)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                
            return image_features.cpu().numpy()[0]
            
        except Exception as e:
            logger.error(f"图片编码失败 {image_path}: {e}")
            return None
    
    def encode_image(self, image_path: str) -> Optional[np.ndarray]:
        """
        编码单张图片（别名方法，用于以图搜图）
        Args:
            image_path: 图片路径
        Returns:
            图片特征向量
        """
        return self.encode_image_from_path(image_path)
    
    def encode_images_batch_from_paths(self, image_paths: List[str], batch_size: int = 32) -> Tuple[List[np.ndarray], List[str], List[Dict]]:
        """
        批量从本地路径编码图片 - 增强版，返回详细错误信息
        
        Returns:
            features: 特征向量列表
            valid_paths: 成功处理的图片路径列表  
            error_details: 错误详情列表
        """
        features = []
        valid_paths = []
        error_details = []
        processed_count = 0
        
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i:i+batch_size]
            batch_images = []
            batch_valid_paths = []
            
            # 预处理批次图片
            for path in batch_paths:
                try:
                    if not os.path.exists(path):
                        error_details.append({
                            'path': path,
                            'error': 'file_not_found',
                            'message': '文件不存在'
                        })
                        continue
                    
                    # 检查文件大小
                    try:
                        file_size = os.path.getsize(path)
                        if file_size == 0:
                            error_details.append({
                                'path': path,
                                'error': 'empty_file',
                                'message': '文件为空'
                            })
                            continue
                        
                        if file_size > 50 * 1024 * 1024:  # 50MB
                            error_details.append({
                                'path': path,
                                'error': 'file_too_large',
                                'message': f'文件过大: {file_size/1024/1024:.1f}MB'
                            })
                            continue
                    except OSError as e:
                        error_details.append({
                            'path': path,
                            'error': 'file_access_error',
                            'message': f'文件访问错误: {str(e)}'
                        })
                        continue
                    
                    # 尝试加载图片
                    try:
                        image = Image.open(path).convert('RGB')
                        
                        # 检查图片尺寸
                        width, height = image.size
                        if width < 10 or height < 10:
                            error_details.append({
                                'path': path,
                                'error': 'invalid_dimensions',
                                'message': f'图片尺寸过小: {width}x{height}'
                            })
                            continue
                        
                        if width > 10000 or height > 10000:
                            error_details.append({
                                'path': path,
                                'error': 'dimensions_too_large', 
                                'message': f'图片尺寸过大: {width}x{height}'
                            })
                            continue
                        
                        # 预处理图片
                        image_input = self.preprocess(image)
                        batch_images.append(image_input)
                        batch_valid_paths.append(path)
                        
                    except Exception as e:
                        error_details.append({
                            'path': path,
                            'error': 'image_processing_failed',
                            'message': f'图片处理失败: {str(e)}'
                        })
                        continue
                        
                except Exception as e:
                    error_details.append({
                        'path': path,
                        'error': 'unexpected_error',
                        'message': f'未知错误: {str(e)}'
                    })
                    continue
            
            if not batch_images:
                continue
            
            # 批量编码
            try:
                batch_tensor = torch.stack(batch_images).to(self.device)
                
                with torch.no_grad():
                    batch_features = self.model.encode_image(batch_tensor)
                    batch_features = batch_features / batch_features.norm(dim=-1, keepdim=True)
                
                # 添加到结果列表
                for j, feature in enumerate(batch_features.cpu().numpy()):
                    features.append(feature)
                    valid_paths.append(batch_valid_paths[j])
                    processed_count += 1
                
                logger.info(f"批次 {i//batch_size + 1}/{(len(image_paths)-1)//batch_size + 1} 完成 - 成功: {processed_count}, 失败: {len(error_details)}")
                
            except Exception as e:
                # 如果批量编码失败，尝试单张处理
                logger.warning(f"批量编码失败，尝试单张处理: {e}")
                
                for j, (path, image_input) in enumerate(zip(batch_valid_paths, batch_images)):
                    try:
                        single_tensor = image_input.unsqueeze(0).to(self.device)
                        
                        with torch.no_grad():
                            single_feature = self.model.encode_image(single_tensor)
                            single_feature = single_feature / single_feature.norm(dim=-1, keepdim=True)
                        
                        features.append(single_feature.cpu().numpy()[0])
                        valid_paths.append(path)
                        processed_count += 1
                        
                    except Exception as single_error:
                        error_details.append({
                            'path': path,
                            'error': 'encoding_failed',
                            'message': f'编码失败: {str(single_error)}'
                        })
                        continue
        
        # 统计错误类型
        error_stats = {}
        for error in error_details:
            error_type = error['error']
            error_stats[error_type] = error_stats.get(error_type, 0) + 1
        
        logger.info(f"批量编码完成 - 总成功: {processed_count}, 总失败: {len(error_details)}")
        if error_stats:
            logger.info(f"错误统计: {error_stats}")
        
        return features, valid_paths, error_details
    
    def encode_text(self, text: str) -> Optional[np.ndarray]:
        """
        编码文本
        Args:
            text: 输入文本
        Returns:
            文本特征向量
        """
        try:
            text_tokens = clip.tokenize([text]).to(self.device)
            
            with torch.no_grad():
                text_features = self.model.encode_text(text_tokens)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            
            return text_features.cpu().numpy()[0]
            
        except Exception as e:
            logger.error(f"文本编码失败: {e}")
            return None
    
    def encode_image_from_pil(self, pil_image: Image.Image) -> Optional[np.ndarray]:
        """
        从PIL图片编码
        Args:
            pil_image: PIL图片对象
        Returns:
            图片特征向量
        """
        try:
            # 确保是RGB格式
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # 预处理图片
            image_input = self.preprocess(pil_image).unsqueeze(0).to(self.device)
            
            # 编码图片
            with torch.no_grad():
                image_features = self.model.encode_image(image_input)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                
            return image_features.cpu().numpy()[0]
            
        except Exception as e:
            logger.error(f"从PIL图片编码失败: {e}")
            return None

class MySQLDataProcessor:
    """MySQL数据库处理器 - 优化版"""
    
    def __init__(self):
        """初始化MySQL数据处理器"""
        # 硬编码数据库配置
        self.db_config = {
            'host': '',
            'user': '',
            'password': '',
            'database': '',
            'port': 3306,
            'charset': 'utf8mb4'
        }
        
        # 图片路径前缀
        self.image_path_prefix = "/home/ai/"
        
        self.connection = None
        self.dataset_df = None
        self.available_tag_fields = []
        self.schema_info = None
        self.file_mapping = None  # 延迟初始化
        self._file_mapping_built = False  # 添加标志
        
        # 添加数据库状态追踪
        self.last_known_count = None
        self.last_check_time = None
        self.status_file = "db_status.json"  # 状态文件
        
        # 测试连接
        self._test_connection()
        
        logger.info(f"MySQL数据处理器初始化完成")
        logger.info(f"基础图片路径: {self.image_path_prefix}")
    
    def _test_connection(self):
        """测试数据库连接"""
        try:
            connection = pymysql.connect(**self.db_config)
            connection.close()
            logger.info(f"数据库连接测试成功 - {self.db_config['host']}:{self.db_config['port']}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise
    
    def _get_connection(self):
        """获取数据库连接"""
        if self.connection is None or not self.connection.open:
            self.connection = pymysql.connect(**self.db_config)
        return self.connection
    
    def _load_status(self):
        """加载数据库状态"""
        try:
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    status = json.load(f)
                    self.last_known_count = status.get('count')
                    self.last_check_time = status.get('check_time')
                    logger.info(f"加载状态: 上次记录 {self.last_known_count} 条数据")
        except Exception as e:
            logger.warning(f"加载状态文件失败: {e}")
    
    def _save_status(self, count: int):
        """保存数据库状态"""
        try:
            status = {
                'count': count,
                'check_time': datetime.now().isoformat(),
                'database': self.db_config['database'],
                'table': 'work_copy428'
            }
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
            
            self.last_known_count = count
            self.last_check_time = status['check_time']
            logger.info(f"保存状态: {count} 条数据")
        except Exception as e:
            logger.warning(f"保存状态文件失败: {e}")
    
    def check_data_updates(self) -> Dict:
        """检查数据库是否有更新"""
        try:
            # 加载上次状态
            self._load_status()
            
            connection = self._get_connection()
            
            # 获取当前数据库记录数
            base_fields = ['id', 'image_url']
            tag_fields = []
            
            # 检查可用字段
            schema_info = self.check_database_schema()
            if schema_info and schema_info['has_ai_tags']:
                tag_fields.append('ai_tags')
            if schema_info and schema_info['has_tags']:
                tag_fields.append('tags')
            
            # 构建查询条件
            where_conditions = ["image_url IS NOT NULL", "image_url != ''"]
            
            if tag_fields:
                tag_conditions = []
                for field in tag_fields:
                    tag_conditions.append(f"({field} IS NOT NULL AND {field} != '')")
                where_conditions.append(f"({' OR '.join(tag_conditions)})")
            
            where_clause = ' AND '.join(where_conditions)
            
            # 获取当前总数
            count_sql = f"""
                SELECT COUNT(*) as total_count
                FROM work_copy428 
                WHERE {where_clause}
            """
            
            with connection.cursor() as cursor:
                cursor.execute(count_sql)
                current_count = cursor.fetchone()[0]
            
            # 比较数据变化
            if self.last_known_count is None:
                # 首次检查
                change_type = 'initial'
                change_count = current_count
                message = f"首次检测到数据库中有 {current_count:,} 条记录"
            elif current_count > self.last_known_count:
                # 数据增加
                change_type = 'increased'
                change_count = current_count - self.last_known_count
                message = f"数据库更新：新增 {change_count:,} 条记录 ({self.last_known_count:,} → {current_count:,})"
            elif current_count < self.last_known_count:
                # 数据减少
                change_type = 'decreased'
                change_count = self.last_known_count - current_count
                message = f"数据库更新：减少 {change_count:,} 条记录 ({self.last_known_count:,} → {current_count:,})"
            else:
                # 无变化
                change_type = 'no_change'
                change_count = 0
                message = f"数据库无变化，保持 {current_count:,} 条记录"
            
            # 获取最新记录的时间戳
            try:
                timestamp_sql = f"""
                    SELECT MAX(id) as latest_id
                    FROM work_copy428 
                    WHERE {where_clause}
                """
                with connection.cursor() as cursor:
                    cursor.execute(timestamp_sql)
                    latest_id = cursor.fetchone()[0]
            except:
                latest_id = None
            
            return {
                'has_updates': change_type != 'no_change',
                'change_type': change_type,
                'change_count': change_count,
                'current_count': current_count,
                'last_known_count': self.last_known_count,
                'latest_id': latest_id,
                'message': message,
                'check_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"检查数据更新失败: {e}")
            return {
                'has_updates': False,
                'change_type': 'error',
                'change_count': 0,
                'current_count': 0,
                'last_known_count': self.last_known_count,
                'message': f"检查失败: {e}",
                'error': str(e)
            }
    
    def check_database_schema(self):
        """检查数据库表结构"""
        try:
            connection = self._get_connection()
            
            # 检查表结构
            sql = "DESCRIBE work_copy428"
            
            with connection.cursor() as cursor:
                cursor.execute(sql)
                columns = cursor.fetchall()
            
            logger.info("数据库表字段结构:")
            available_columns = []
            for column in columns:
                field_name = column[0]
                field_type = column[1]
                available_columns.append(field_name)
                logger.info(f"  {field_name}: {field_type}")
            
            # 检查关键字段
            has_ai_tags = 'ai_tags' in available_columns
            has_tags = 'tags' in available_columns
            
            logger.info(f"关键字段检查:")
            logger.info(f"  ai_tags字段: {'✅ 存在' if has_ai_tags else '❌ 不存在'}")
            logger.info(f"  tags字段: {'✅ 存在' if has_tags else '❌ 不存在'}")
            
            return {
                'available_columns': available_columns,
                'has_ai_tags': has_ai_tags,
                'has_tags': has_tags
            }
            
        except Exception as e:
            logger.error(f"检查数据库结构失败: {e}")
            return None
    
    def load_data(self, limit: int = 183247, offset: int = 0, save_status: bool = True):
        """
        从数据库加载数据 - 动态适配字段
        Args:
            limit: 限制加载的记录数 (默认183247)
            offset: 偏移量
            save_status: 是否保存状态
        """
        try:
            # 先检查数据库结构
            schema_info = self.check_database_schema()
            if not schema_info:
                raise Exception("无法获取数据库结构信息")
            
            connection = self._get_connection()
            
            # 根据存在的字段动态构建查询
            base_fields = ['id', 'image_url']
            tag_fields = []
            
            if schema_info['has_ai_tags']:
                tag_fields.append('ai_tags')
            if schema_info['has_tags']:
                tag_fields.append('tags')
            
            if not tag_fields:
                raise Exception("数据库中没有找到ai_tags或tags字段")
            
            all_fields = base_fields + tag_fields
            fields_str = ', '.join(all_fields)
            
            # 构建WHERE条件 - 动态适配
            where_conditions = ["image_url IS NOT NULL", "image_url != ''"]
            
            # 添加标签字段的条件
            tag_conditions = []
            for field in tag_fields:
                tag_conditions.append(f"({field} IS NOT NULL AND {field} != '')")
            
            if tag_conditions:
                where_conditions.append(f"({' OR '.join(tag_conditions)})")
            
            where_clause = ' AND '.join(where_conditions)
            
            sql = f"""
                SELECT {fields_str}
                FROM work_copy428 
                WHERE {where_clause}
                ORDER BY id
                LIMIT %s OFFSET %s
            """
            
            logger.info(f"动态SQL查询: {sql}")
            logger.info(f"可用字段: {all_fields}")
            logger.info(f"执行查询: 限制 {limit} 条记录，偏移 {offset}")
            
            # 执行查询
            with connection.cursor() as cursor:
                cursor.execute(sql, (limit, offset))
                results = cursor.fetchall()
            
            # 转换为DataFrame
            self.dataset_df = pd.DataFrame(results, columns=all_fields)
            
            # 保存字段信息
            self.available_tag_fields = tag_fields
            self.schema_info = schema_info
            
            # 数据清洗和处理
            self._clean_data()
            
            # 保存状态（如果需要）
            if save_status:
                current_count = len(self.dataset_df)
                self._save_status(current_count)
            
            logger.info(f"成功加载 {len(self.dataset_df)} 条数据")
            
        except Exception as e:
            logger.error(f"数据加载失败: {e}")
            raise
    
    def _build_file_mapping_once(self):
        """只构建一次文件映射表"""
        if self._file_mapping_built and self.file_mapping is not None:
            logger.info(f"文件映射表已存在，包含 {len(self.file_mapping)} 个文件")
            return
        
        logger.info("首次构建文件映射表...")
        self.file_mapping = {}
        scraper_base = f'{self.image_path_prefix}scraper_data/'
        
        if os.path.exists(scraper_base):
            for brand_dir in os.listdir(scraper_base):
                brand_path = os.path.join(scraper_base, brand_dir)
                if os.path.isdir(brand_path):
                    try:
                        for filename in os.listdir(brand_path):
                            if filename.endswith(('.png', '.jpg', '.jpeg')):
                                full_path = os.path.join(brand_path, filename)
                                self.file_mapping[filename] = full_path
                    except Exception as e:
                        logger.warning(f"读取目录 {brand_dir} 失败: {e}")
        
        self._file_mapping_built = True
        logger.info(f"文件映射表构建完成，映射了 {len(self.file_mapping)} 个文件")
    
    def _clean_data(self):
        """清洗和处理数据 - 优化版本"""
        try:
            initial_count = len(self.dataset_df)
            self.dataset_df = self.dataset_df.dropna(subset=['image_url'])
            
            # 动态过滤空标签记录
            if hasattr(self, 'available_tag_fields'):
                tag_fields = self.available_tag_fields
            else:
                # 回退逻辑
                tag_fields = []
                if 'ai_tags' in self.dataset_df.columns:
                    tag_fields.append('ai_tags')
                if 'tags' in self.dataset_df.columns:
                    tag_fields.append('tags')
            
            logger.info(f"可用标签字段: {tag_fields}")
            
            # 过滤掉所有标签字段都为空的记录
            if tag_fields:
                mask = pd.Series([False] * len(self.dataset_df), index=self.dataset_df.index)
                for field in tag_fields:
                    field_mask = (
                        self.dataset_df[field].notna() & 
                        (self.dataset_df[field] != '') &
                        (self.dataset_df[field] != 'null')
                    )
                    mask = mask | field_mask
                
                self.dataset_df = self.dataset_df[mask]
                logger.info(f"标签过滤后剩余: {len(self.dataset_df)} 条记录")
            
            # 只在需要时构建文件映射表
            self._build_file_mapping_once()
            
            # 处理图片路径（使用已有的映射表）
            def process_image_path(image_url):
                if pd.isna(image_url) or image_url == '':
                    return ''
                
                clean_url = str(image_url).strip()
                filename = os.path.basename(clean_url)
                
                if filename in self.file_mapping:
                    return self.file_mapping[filename]
                
                if clean_url.startswith('/scraper_data/'):
                    return clean_url.replace('/scraper_data/', f'{self.image_path_prefix}scraper_data/')
                else:
                    return os.path.join(self.image_path_prefix, clean_url.lstrip('/'))
            
            self.dataset_df['full_image_path'] = self.dataset_df['image_url'].apply(process_image_path)
            
            # 动态处理和合并标签
            def process_and_merge_tags(row):
                """动态处理并合并所有可用的标签字段"""
                combined_tags = []
                
                # 遍历所有可用的标签字段
                for field in tag_fields:
                    if field in row and pd.notna(row[field]) and str(row[field]).strip():
                        field_value = str(row[field]).strip()
                        
                        # 跳过明显的空值
                        if field_value.lower() in ['null', 'none', '']:
                            continue
                        
                        try:
                            # 尝试解析JSON格式
                            if field_value.startswith('[') or field_value.startswith('{'):
                                parsed = json.loads(field_value)
                                if isinstance(parsed, list):
                                    parsed_tags = ', '.join(str(tag) for tag in parsed if tag)
                                elif isinstance(parsed, dict):
                                    parsed_tags = ', '.join(f"{k}: {v}" for k, v in parsed.items() if v)
                                else:
                                    parsed_tags = str(parsed)
                                
                                if parsed_tags:
                                    combined_tags.append(parsed_tags)
                            else:
                                combined_tags.append(field_value)
                                
                        except (json.JSONDecodeError, Exception):
                            # 如果不是JSON，直接使用原值
                            combined_tags.append(field_value)
                
                return ' | '.join(combined_tags) if combined_tags else '无标签信息'
            
            # 应用标签合并处理
            self.dataset_df['processed_tags'] = self.dataset_df.apply(process_and_merge_tags, axis=1)
            
            # 添加文件名信息
            self.dataset_df['filename'] = self.dataset_df['image_url'].apply(
                lambda x: os.path.basename(x) if x else ''
            )
            
            # 验证图片路径有效性
            def path_exists_check(path):
                try:
                    return os.path.exists(path) if path else False
                except:
                    return False
            
            self.dataset_df['file_exists'] = self.dataset_df['full_image_path'].apply(path_exists_check)
            valid_count = self.dataset_df['file_exists'].sum()
            
            # 统计标签字段
            tag_stats = {}
            for field in tag_fields:
                if field in self.dataset_df.columns:
                    non_empty = (
                        self.dataset_df[field].notna() & 
                        (self.dataset_df[field] != '') &
                        (self.dataset_df[field] != 'null')
                    ).sum()
                    tag_stats[field] = int(non_empty)
            
            logger.info(f"标签合并和路径处理完成:")
            logger.info(f"  总记录: {len(self.dataset_df)}")
            logger.info(f"  文件匹配成功: {valid_count}")
            logger.info(f"  标签统计: {tag_stats}")
            
            # 显示样本数据
            sample_data = self.dataset_df[['id'] + tag_fields + ['processed_tags']].head(3)
            logger.info(f"标签样本数据:")
            for idx, row in sample_data.iterrows():
                logger.info(f"  ID {row['id']}:")
                for field in tag_fields:
                    value = str(row[field])[:100] if pd.notna(row[field]) else 'null'
                    logger.info(f"    {field}: {value}")
                processed = str(row['processed_tags'])[:100]
                logger.info(f"    processed_tags: {processed}")
            
            cleaned_count = len(self.dataset_df)
            logger.info(f"数据清洗完成: {initial_count} -> {cleaned_count}")
            
        except Exception as e:
            logger.error(f"数据清洗失败: {e}")
            raise
    
    def ensure_data_loaded(self, limit: int = 183247):
        """确保数据已加载（延迟加载）"""
        if self.dataset_df is None:
            logger.info("延迟加载数据库数据...")
            self.load_data(limit=limit)
        else:
            logger.info(f"数据已加载，包含 {len(self.dataset_df)} 条记录")
    
    def get_dataset_info(self) -> Dict:
        """获取数据集信息"""
        if self.dataset_df is None or len(self.dataset_df) == 0:
            return {"total_images": 0}
        
        # 统计文件存在情况
        existing_files = self.dataset_df['file_exists'].sum()
        missing_files = len(self.dataset_df) - existing_files
        
        # 标签统计
        tag_stats = {}
        if hasattr(self, 'available_tag_fields'):
            for field in self.available_tag_fields:
                if field in self.dataset_df.columns:
                    non_empty = (
                        self.dataset_df[field].notna() & 
                        (self.dataset_df[field] != '') &
                        (self.dataset_df[field] != 'null')
                    ).sum()
                    tag_stats[field] = int(non_empty)
        
        return {
            "total_records": len(self.dataset_df),
            "existing_files": int(existing_files),
            "missing_files": int(missing_files),
            "data_source": f"MySQL Database - {self.db_config['host']}",
            "database": self.db_config['database'],
            "table": "work_copy428", 
            "path_prefix": self.image_path_prefix,
            "columns": list(self.dataset_df.columns),
            "available_tag_fields": self.available_tag_fields,
            "tag_stats": tag_stats,
            "sample_data": self.dataset_df[['id', 'image_url', 'full_image_path', 'processed_tags', 'file_exists']].head(3).to_dict('records')
        }

    def close_connection(self):
        """关闭数据库连接"""
        if self.connection and self.connection.open:
            self.connection.close()
            logger.info("数据库连接已关闭")

class ChromaDBManager:
    """ChromaDB数据库管理器 - 增强版"""
    
    def __init__(self, host: str = "localhost", port: int = 6600, 
                 collection_name: str = "local_image_collection",
                 fallback_local_path: str = "./local_chromadb"):
        """初始化ChromaDB管理器"""
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.fallback_local_path = fallback_local_path
        self.client = None
        self.collection = None
        self.is_local_mode = False
        
        self._connect()
        self._verify_persistence()
    
    def _connect(self):
        """建立数据库连接"""
        try:
            # 尝试连接Docker中的ChromaDB
            self.client = chromadb.HttpClient(host=self.host, port=self.port)
            # 测试连接
            self.client.heartbeat()
            self.is_local_mode = False
            logger.info(f"连接到Docker ChromaDB: http://{self.host}:{self.port}")
            
        except Exception as e:
            logger.warning(f"Docker连接失败: {e}")
            logger.info("回退到本地文件模式...")
            
            try:
                Path(self.fallback_local_path).mkdir(parents=True, exist_ok=True)
                self.client = chromadb.PersistentClient(path=self.fallback_local_path)
                self.is_local_mode = True
                logger.info(f"使用本地模式: {self.fallback_local_path}")
            except Exception as e2:
                logger.error(f"本地模式失败: {e2}")
                raise ConnectionError("无法连接到ChromaDB")
        
        # 创建或获取集合
        self._setup_collection()
    
    def _setup_collection(self):
        """设置集合"""
        try:
            self.collection = self.client.get_collection(self.collection_name)
            logger.info(f"加载已存在集合: {self.collection_name}")
        except:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "CLIP本地图片向量集合"}
            )
            logger.info(f"创建新集合: {self.collection_name}")
    
    def _verify_persistence(self):
        """验证数据持久化"""
        try:
            # 检查现有数据
            count = self.collection.count()
            
            if count > 0:
                logger.info(f"✅ 检测到持久化数据: {count} 条记录")
                
                # 验证数据完整性
                sample = self.collection.get(limit=1, include=['metadatas'])
                if sample and sample['ids']:
                    logger.info(f"✅ 数据访问正常")
                else:
                    logger.warning("⚠️ 数据可能损坏")
            else:
                logger.info("💾 空集合，等待数据写入")
                
        except Exception as e:
            logger.error(f"❌ 持久化验证失败: {e}")
    
    def add_images(self, embeddings: List[List[float]], metadatas: List[Dict], 
                   documents: List[str], ids: List[str], batch_size: int = 5000):
        """
        分批添加图片数据 - 增强版本
        """
        total_items = len(embeddings)
        
        if total_items == 0:
            logger.warning("没有数据需要添加")
            return
        
        logger.info(f"开始分批插入 {total_items} 条数据，批次大小: {batch_size}")
        
        successful_batches = 0
        failed_batches = 0
        total_inserted = 0
        
        try:
            for i in range(0, total_items, batch_size):
                end_idx = min(i + batch_size, total_items)
                
                batch_embeddings = embeddings[i:end_idx]
                batch_metadatas = metadatas[i:end_idx]
                batch_documents = documents[i:end_idx]
                batch_ids = ids[i:end_idx]
                
                batch_num = i // batch_size + 1
                total_batches = (total_items + batch_size - 1) // batch_size
                
                logger.info(f"插入批次 {batch_num}/{total_batches}: {len(batch_embeddings)} 条记录")
                
                try:
                    self.collection.add(
                        embeddings=batch_embeddings,
                        metadatas=batch_metadatas,
                        documents=batch_documents,
                        ids=batch_ids
                    )
                    
                    # 立即验证写入
                    new_count = self.collection.count()
                    logger.info(f"✅ 批次 {batch_num} 插入成功, 当前总数: {new_count}")
                    
                    successful_batches += 1
                    total_inserted += len(batch_embeddings)
                    
                except Exception as e:
                    logger.error(f"❌ 批次 {batch_num} 插入失败: {e}")
                    failed_batches += 1
                    continue
            
            # 最终验证
            final_count = self.collection.count()
            logger.info(f"📊 最终验证: ChromaDB中共有 {final_count} 条记录")
            
            logger.info(f"📊 分批插入完成:")
            logger.info(f"   总批次: {successful_batches + failed_batches}")
            logger.info(f"   成功批次: {successful_batches}")
            logger.info(f"   失败批次: {failed_batches}")
            logger.info(f"   成功插入: {total_inserted} 条记录")
            
            if failed_batches > 0:
                logger.warning(f"有 {failed_batches} 个批次插入失败")
            
        except Exception as e:
            logger.error(f"分批插入过程中出错: {e}")
            raise
    
    def search_similar_images(self, query_vector: List[float], top_k: int = 10,
                            where: Optional[Dict] = None) -> Dict:
        """
        搜索相似图片
        Args:
            query_vector: 查询向量
            top_k: 返回结果数量
            where: 过滤条件
        Returns:
            搜索结果
        """
        try:
            results = self.collection.query(
                query_embeddings=[query_vector],
                n_results=top_k,
                where=where,
                include=['metadatas', 'documents', 'distances']
            )
            return results
        except Exception as e:
            logger.error(f"相似图片搜索失败: {e}")
            return {}
    
    def get_collection_info(self) -> Dict:
        """获取集合信息"""
        try:
            count = self.collection.count()
            return {
                "name": self.collection_name,
                "count": count,
                "mode": "local" if self.is_local_mode else "docker"
            }
        except Exception as e:
            logger.error(f"获取集合信息失败: {e}")
            return {}
    
    def reset_collection(self):
        """重置集合"""
        try:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name,
                metadata={"description": "CLIP本地图片向量集合"}
            )
            logger.info("集合已重置")
        except Exception as e:
            logger.error(f"重置集合失败: {e}")
            
    def get_all_existing_ids(self) -> set:
        """获取ChromaDB中所有已存在的ID - 修复版"""
        try:
            existing_ids = set()
            batch_size = 5000  # 减小批次大小
            
            # 先获取总数
            total_count = self.collection.count()
            logger.info(f"ChromaDB总记录数: {total_count}")
            
            if total_count == 0:
                return set()
            
            # 分批获取所有数据
            processed = 0
            while processed < total_count:
                try:
                    # 获取这一批数据
                    results = self.collection.get(
                        limit=batch_size,
                        offset=processed,
                        include=['metadatas']
                    )
                    
                    if not results or not results.get('metadatas'):
                        break
                    
                    batch_count = len(results['metadatas'])
                    logger.info(f"获取批次: {processed}-{processed + batch_count}/{total_count}")
                    
                    # 提取ID
                    for metadata in results['metadatas']:
                        if 'id' in metadata:
                            try:
                                existing_ids.add(int(metadata['id']))
                            except (ValueError, TypeError):
                                logger.warning(f"无效ID: {metadata.get('id')}")
                    
                    processed += batch_count
                    
                    # 如果返回的数据少于batch_size，说明已经获取完了
                    if batch_count < batch_size:
                        break
                        
                except Exception as e:
                    logger.error(f"获取批次 {processed} 失败: {e}")
                    processed += batch_size  # 跳过这个批次
                    continue
            
            logger.info(f"成功获取 {len(existing_ids)} 个已存在的ID")
            return existing_ids
            
        except Exception as e:
            logger.error(f"获取已存在ID失败: {e}")
            return set()

class DatabaseImageRetrievalSystem:
    """基于数据库的本地图片检索系统"""
    
    def __init__(self, 
                 clip_model: str = "ViT-B/32",
                 chromadb_host: str = "localhost", 
                 chromadb_port: int = 6600,
                 collection_name: str = "local_db_image_collection"):
        """初始化数据库图片检索系统"""
        logger.info("初始化本地图片检索系统...")
        
        # 初始化各个组件
        self.clip_encoder = CLIPImageEncoder(clip_model)
        self.chromadb = ChromaDBManager(chromadb_host, chromadb_port, collection_name)
        self.db_processor = MySQLDataProcessor()
        self.tag_keywords = {
            "色彩": ["单色系", "对比色", "黑白", "金属色", "哑光色", "鲜艳色彩", "柔和色彩", "复古色彩", "梦幻色彩"],
            "色调":["冷色调", "暖色调", "中性色调", "高对比度", "低对比度", "明亮色调", "暗黑色调", "黄昏色调", "褪色效果", "夜景色调", "饱和色调"],
            "光线":["自然光线", "人工光线", "柔和光线", "强烈光线", "侧光", "逆光", "顺光", "漫射光", "光影对比", "黄金时刻光线", "蓝调时刻光线", "夜晚光线"],
            "构图":["中心构图", "对称构图", "三分法构图", "前景框架", "引导线构图", "重复元素", "负空间构图", "对角线构图", "层次构图", "最小化构图", "黄金比例构图"],
            "质感":["金属质感", "光滑质感", "哑光质感", "粗糙质感", "反光质感", "皮革质感", "科技质感", "奢华质感", "复古质感", "自然质感"],
            "人车互动":["生活", "家庭", "休闲", "街拍", "城市", "风景", "建筑", "驾驶场景", "家庭出游", "商务出行", "休闲旅行", "户外探险", "城市通勤", "社交聚会", "展示场景", "试驾场景", "儿童互动", "宠物互动", "情侣场景"],
            "画面风格":["摄影", "CG", "极简", "商业风格", "生活纪实", "复古风格", "未来风格", "艺术创意", "工业风格", "运动风格", "奢华风格", "科技风格", "电影感"],
            "拍摄视角":["特写","正面视角", "侧面视角", "45度角", "后视图", "俯视图", "仰视角", "车内视角", "全景视角", "鸟瞰视角",],
            "车型": ["轿车", "SUV", "越野", "房车", "MPV", "紧凑型轿车", "中型轿车", "豪华轿车", "跑车", "皮卡", "古典车", "电动车"],
        }
        
        # 检查现有索引状态
        try:
            collection_info = self.chromadb.get_collection_info()
            existing_count = collection_info.get('count', 0)
            self.is_indexed = existing_count > 0
            
            if self.is_indexed:
                logger.info(f"检测到现有索引: {existing_count} 条记录")
            else:
                logger.info("未检测到现有索引")
                
        except Exception as e:
            logger.warning(f"检查索引状态失败: {e}")
            self.is_indexed = False
        
        logger.info("本地图片检索系统初始化完成")
    
    def build_index(self, batch_size: int = 32, force_rebuild: bool = False, 
                   limit: int = 183247, only_existing_files: bool = True,
                   chromadb_batch_size: int = 4000):
        """构建图片索引 - 增强版"""
        # 检查是否需要重建
        collection_info = self.chromadb.get_collection_info()
        if not force_rebuild and collection_info.get('count', 0) > 0:
            logger.info(f"检测到已存在 {collection_info['count']} 条数据，跳过构建")
            self.is_indexed = True
            return
        
        if force_rebuild:
            logger.info("强制重建索引...")
            self.chromadb.reset_collection()
        
        logger.info(f"开始构建图片索引 - 限制: {limit} 张图片...")
        
        # 加载数据
        if self.db_processor.dataset_df is None:
            self.db_processor.load_data(limit=limit)
        
        # 获取数据
        dataset_df = self.db_processor.dataset_df
        if len(dataset_df) == 0:
            logger.error("没有可用的数据")
            return
        
        # 获取图片路径
        if only_existing_files:
            valid_df = dataset_df[dataset_df['file_exists'] == True].copy()
            logger.info(f"找到 {len(valid_df)} 个存在的图片文件")
        else:
            valid_df = dataset_df.copy()
            logger.info(f"处理 {len(valid_df)} 个图片记录 (包括不存在的文件)")
        
        if len(valid_df) == 0:
            logger.error("没有找到可用的图片文件")
            return
        
        # 去重处理
        logger.info("去除重复文件...")
        initial_count = len(valid_df)
        
        # 按文件路径去重，保留第一条记录
        valid_df = valid_df.drop_duplicates(subset=['full_image_path'], keep='first')
        
        # 确保ID唯一性
        valid_df = valid_df.drop_duplicates(subset=['id'], keep='first')
        
        deduplicated_count = len(valid_df)
        logger.info(f"去重完成: {initial_count} -> {deduplicated_count}")
        
        if len(valid_df) == 0:
            logger.error("去重后没有可用的数据")
            return
        
        # 获取唯一的图片路径
        image_paths = valid_df['full_image_path'].tolist()
        
        # 批量编码图片 - 使用增强版方法
        features, valid_paths, error_details = self.clip_encoder.encode_images_batch_from_paths(
            image_paths, batch_size
        )
        
        # 详细分析错误
        if error_details:
            logger.warning(f"\n⚠️ 编码过程中发现 {len(error_details)} 个错误:")
            
            error_stats = {}
            for error in error_details:
                error_type = error['error']
                error_stats[error_type] = error_stats.get(error_type, 0) + 1
            
            for error_type, count in error_stats.items():
                logger.warning(f"   {error_type}: {count} 个")
            
            # 显示前10个错误的详细信息
            logger.warning(f"\n前10个错误详情:")
            for i, error in enumerate(error_details[:10]):
                logger.warning(f"   {i+1}. {os.path.basename(error['path'])}: {error['message']}")
            
            # 保存错误报告
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            error_report_file = f"encoding_errors_{timestamp}.json"
            try:
                with open(error_report_file, 'w', encoding='utf-8') as f:
                    json.dump(error_details, f, ensure_ascii=False, indent=2)
                logger.info(f"错误报告已保存: {error_report_file}")
            except:
                pass
        
        if not features:
            logger.error("没有成功编码的图片")
            return
        
        logger.info(f"📊 编码统计:")
        logger.info(f"   总图片: {len(image_paths)}")
        logger.info(f"   成功编码: {len(features)}")
        logger.info(f"   编码失败: {len(error_details)}")
        logger.info(f"   成功率: {len(features)/len(image_paths)*100:.2f}%")
        
        # 准备数据插入ChromaDB
        embeddings = []
        metadatas = []
        documents = []
        ids = []
        
        used_ids = set()
        used_paths = set()
        
        for i, path in enumerate(valid_paths):
            if path in used_paths:
                continue
            
            matching_rows = valid_df[valid_df['full_image_path'] == path]
            if len(matching_rows) == 0:
                continue
            
            row = matching_rows.iloc[0]
            
            # 生成唯一ID
            vector_id = f"img_{row['id']}"
            
            # 确保ID唯一
            if vector_id in used_ids:
                counter = 1
                while f"{vector_id}_{counter}" in used_ids:
                    counter += 1
                vector_id = f"{vector_id}_{counter}"
            
            embeddings.append(features[i].tolist())
            
            # 清晰的字段命名
            metadatas.append({
                'id': int(row['id']),
                'image_path': path,
                'original_url': row['image_url'],
                'filename': row['filename'],
                'original_ai_tags': str(row.get('ai_tags', '')),
                'original_tags': str(row.get('tags', '')),
                'combined_tags': str(row['processed_tags']),
                'display_tags': str(row['processed_tags']),
                'created_at': datetime.now().isoformat(),
                'clip_model': self.clip_encoder.model_name
            })
            
            # documents字段用于搜索
            documents.append(f"图片: {row['filename']}, 标签: {row['processed_tags']}")
            ids.append(vector_id)
            
            used_ids.add(vector_id)
            used_paths.add(path)
        
        # 插入数据库
        try:
            self.chromadb.add_images(
                embeddings, metadatas, documents, ids, 
                batch_size=chromadb_batch_size
            )
            
            self.is_indexed = True
            logger.info(f"✅ 索引构建完成! 成功索引 {len(embeddings)} 张图片")
            
        except Exception as e:
            logger.error(f"数据插入失败: {e}")
            raise
    
    def search_by_text(self, query_text: str, top_k: int = 9, 
                      search_mode: str = "original") -> List[Dict]:
        """根据文本查询相似图片"""
        collection_info = self.chromadb.get_collection_info()
        current_count = collection_info.get('count', 0)
        
        if current_count == 0:
            logger.warning("ChromaDB中没有数据，请先构建索引")
            return []
        
        try:
            query_embedding = self.clip_encoder.encode_text(query_text)
            results = self.chromadb.search_similar_images(
                query_embedding.tolist(), 
                top_k=top_k
            )
            
            if not results or not results['ids'] or len(results['ids'][0]) == 0:
                logger.info("没有找到相似的图片")
                return []
            
            formatted_results = []
            for i in range(len(results['ids'][0])):
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                similarity = 1 / (1 + distance) if distance > 0 else 1.0
                
                result = {
                    'id': metadata.get('id', ''),
                    'image_path': metadata.get('image_path', ''),
                    'original_url': metadata.get('original_url', ''),
                    'filename': metadata.get('filename', ''),
                    'original_ai_tags': metadata.get('original_ai_tags', ''),
                    'original_tags': metadata.get('original_tags', ''),
                    'combined_tags': metadata.get('combined_tags', ''),
                    'display_tags': metadata.get('display_tags', ''),
                    'similarity': float(similarity),
                    'distance': float(distance),
                    'clip_model': metadata.get('clip_model', ''),
                    'created_at': metadata.get('created_at', ''),
                    'search_type': search_mode
                }
                formatted_results.append(result)
            
            logger.info(f"找到 {len(formatted_results)} 个相似结果")
            return formatted_results
            
        except Exception as e:
            logger.error(f"文本搜索失败: {e}")
            return []
    
    def search_by_image(self, image_path: str, top_k: int = 9) -> List[Dict]:
        """根据图片查询相似图片"""
        collection_info = self.chromadb.get_collection_info()
        current_count = collection_info.get('count', 0)
        
        if current_count == 0:
            logger.warning("ChromaDB中没有数据，请先构建索引")
            return []
        
        try:
            if not os.path.exists(image_path):
                logger.error(f"图片文件不存在: {image_path}")
                return []
            
            query_embedding = self.clip_encoder.encode_image(image_path)
            
            results = self.chromadb.search_similar_images(
                query_embedding.tolist(), 
                top_k=top_k
            )
            
            if not results or not results['ids'] or len(results['ids'][0]) == 0:
                logger.info("没有找到相似的图片")
                return []
            
            formatted_results = []
            for i in range(len(results['ids'][0])):
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                
                similarity = 1 / (1 + distance) if distance > 0 else 1.0
                
                result = {
                    'id': metadata.get('id', ''),
                    'image_path': metadata.get('image_path', ''),
                    'original_url': metadata.get('original_url', ''),
                    'filename': metadata.get('filename', ''),
                    'original_ai_tags': metadata.get('original_ai_tags', ''),
                    'original_tags': metadata.get('original_tags', ''),
                    'combined_tags': metadata.get('combined_tags', ''),
                    'display_tags': metadata.get('display_tags', ''),
                    'similarity': float(similarity),
                    'distance': float(distance),
                    'clip_model': metadata.get('clip_model', ''),
                    'created_at': metadata.get('created_at', '')
                }
                formatted_results.append(result)
            
            logger.info(f"找到 {len(formatted_results)} 个相似结果")
            return formatted_results
            
        except Exception as e:
            logger.error(f"图片搜索失败: {e}")
            return []
    
    def get_system_info(self) -> Dict:
        """获取系统信息"""
        try:
            collection_info = self.chromadb.get_collection_info()
            current_count = collection_info.get('count', 0)
            self.is_indexed = current_count > 0
            
            system_info = {
                'clip_model': self.clip_encoder.model_name,
                'feature_dim': self.clip_encoder.feature_dim,
                'device': str(self.clip_encoder.device),
                'is_indexed': self.is_indexed,
                'collection': collection_info
            }
            
            if hasattr(self.db_processor, 'dataset_df') and self.db_processor.dataset_df is not None:
                dataset_info = self.db_processor.get_dataset_info()
                system_info['dataset'] = dataset_info
            
            return system_info
            
        except Exception as e:
            logger.error(f"获取系统信息失败: {e}")
            return {
                'clip_model': getattr(self.clip_encoder, 'model_name', 'unknown'),
                'device': 'unknown',
                'is_indexed': False,
                'collection': {'count': 0},
                'error': str(e)
            }
    
    def close_connections(self):
        """关闭所有连接"""
        self.db_processor.close_connection()
        logger.info("所有数据库连接已关闭")

class EnhancedDatabaseImageRetrievalSystem(DatabaseImageRetrievalSystem):
    """增强的图片检索系统（集成OpenRouter）"""
    
    def __init__(self, 
                 clip_model: str = "ViT-B/32",
                 chromadb_host: str = "localhost", 
                 chromadb_port: int = 6600,
                 collection_name: str = "local_db_image_collection",
                 openrouter_api_key: str = None,
                 openrouter_model: str = "anthropic/claude-3-haiku"):
        """
        初始化增强检索系统
        Args:
            openrouter_api_key: OpenRouter API密钥
            openrouter_model: 使用的模型
        """
        # 调用父类初始化
        super().__init__(clip_model, chromadb_host, chromadb_port, collection_name)
        
        # 初始化OpenRouter处理器
        self.openrouter = None
        if openrouter_api_key:
            try:
                self.openrouter = OpenRouterProcessor(openrouter_api_key, openrouter_model)
                logger.info("✅ OpenRouter处理器初始化成功")
            except Exception as e:
                logger.warning(f"⚠️ OpenRouter初始化失败，将使用备用方法: {e}")
        else:
            logger.info("💡 未提供OpenRouter API密钥，将使用备用分析方法")
        
        # 构建可用标签列表
        self.available_tags = self._build_available_tags()
        logger.info(f"📋 构建了 {len(self.available_tags)} 个可用标签")
    
    def _build_available_tags(self) -> List[str]:
        """构建所有可用标签的扁平列表"""
        all_tags = []
        for category, tags in self.tag_keywords.items():
            all_tags.extend(tags)
        return list(set(all_tags))
    
    def search_by_text_intelligent(self, user_query: str, top_k: int = 9,
                             tag_weight: float = 0.6, visual_weight: float = 0.4) -> List[Dict]:
        """
        智能文本搜索（集成LLM分析）
        """
        collection_info = self.chromadb.get_collection_info()
        current_count = collection_info.get('count', 0)
        
        if current_count == 0:
            logger.warning("ChromaDB中没有数据，请先构建索引")
            return []
        
        logger.info(f"开始智能搜索: '{user_query}'")
        
        try:
            # LLM分析用户查询
            if self.openrouter:
                logger.info("🤖 使用LLM分析用户查询...")
                query_analysis = self.openrouter.analyze_query(user_query, self.available_tags)
            else:
                logger.info("🔄 使用备用方法分析查询...")
                query_analysis = self._fallback_query_analysis(user_query)
            
            # 显示分析结果
            self._log_analysis_result(query_analysis)
            
            # 构建优化的CLIP查询
            optimized_clip_query = self._build_optimized_clip_query(query_analysis, user_query)
            
            # CLIP视觉搜索
            visual_results = self._get_visual_results_optimized(optimized_clip_query, top_k)
            
            # 添加分析信息到结果中
            for result in visual_results:
                result['query_analysis'] = query_analysis
                result['optimized_query'] = optimized_clip_query
                result['search_type'] = 'intelligent'
            
            logger.info(f"智能搜索完成，返回 {len(visual_results)} 个结果")
            return visual_results
            
        except Exception as e:
            logger.error(f"智能搜索失败: {e}")
            # 回退到基础搜索
            return self.search_by_text(user_query, top_k)
    
    def _log_analysis_result(self, analysis: Dict):
        """记录分析结果"""
        logger.info("🧠 LLM分析结果:")
        logger.info(f"   总结: {analysis.get('summary', '')}")
        logger.info(f"   场景类型: {analysis.get('scene_type', '')}")
        logger.info(f"   风格偏好: {analysis.get('style_preference', '')}")
        logger.info(f"   核心概念: {analysis.get('key_concepts', [])}")
        logger.info(f"   视觉关键词: {analysis.get('visual_keywords', [])}")
        logger.info(f"   搜索策略: {analysis.get('search_strategy', 'balanced')}")
        
        matched_tags = analysis.get('matched_tags', {})
        if matched_tags:
            logger.info("   匹配的标签:")
            for category, tags in matched_tags.items():
                if tags:
                    logger.info(f"     {category}: {tags}")
    
    def _build_optimized_clip_query(self, analysis: Dict, original_query: str) -> str:
        """构建优化的CLIP查询"""
        try:
            # 获取英文视觉关键词
            visual_keywords = analysis.get('visual_keywords', [])
            
            # 场景和风格信息
            scene_type = analysis.get('scene_type', '')
            style_preference = analysis.get('style_preference', '')
            
            # 构建优化查询
            query_parts = []
            
            # 添加原始查询
            query_parts.append(original_query)
            
            # 添加英文视觉关键词
            if visual_keywords:
                query_parts.extend(visual_keywords)
            
            # 添加场景描述
            if scene_type:
                scene_mapping = {
                    '家庭': 'family scene',
                    '商务': 'business scene',
                    '休闲': 'leisure scene',
                    '城市': 'urban scene',
                    '自然': 'natural scene'
                }
                english_scene = scene_mapping.get(scene_type, scene_type)
                query_parts.append(english_scene)
            
            optimized_query = ' '.join(query_parts)
            
            logger.info(f"优化的CLIP查询: '{optimized_query}'")
            return optimized_query
            
        except Exception as e:
            logger.error(f"构建优化查询失败: {e}")
            return original_query
    
    def _get_visual_results_optimized(self, optimized_query: str, top_k: int) -> List[Dict]:
        """使用优化查询获取视觉结果"""
        try:
            query_embedding = self.clip_encoder.encode_text(optimized_query)
            if query_embedding is None:
                return []
            
            results = self.chromadb.search_similar_images(
                query_embedding.tolist(), 
                top_k=top_k
            )
            
            if not results or not results['ids'] or len(results['ids'][0]) == 0:
                return []
            
            visual_results = []
            for i in range(len(results['ids'][0])):
                metadata = results['metadatas'][0][i]
                distance = results['distances'][0][i]
                similarity = 1 / (1 + distance) if distance > 0 else 1.0
                
                # 安全地获取所有字段
                result = {
                    'id': metadata.get('id', ''),
                    'image_path': metadata.get('image_path', ''),
                    'original_url': metadata.get('original_url', ''),
                    'filename': metadata.get('filename', ''),
                    'original_ai_tags': metadata.get('original_ai_tags', ''),
                    'original_tags': metadata.get('original_tags', ''),
                    'combined_tags': metadata.get('combined_tags', ''),
                    'display_tags': metadata.get('display_tags', ''),
                    'visual_score': float(similarity),
                    'similarity': float(similarity),
                    'distance': float(distance),
                    'clip_model': metadata.get('clip_model', ''),
                    'created_at': metadata.get('created_at', '')
                }
                
                visual_results.append(result)
            
            logger.info(f"优化视觉搜索获得 {len(visual_results)} 个结果")
            return visual_results
            
        except Exception as e:
            logger.error(f"优化视觉搜索失败: {e}")
            return []
    
    def _fallback_query_analysis(self, user_query: str) -> Dict:
        """备用查询分析（不使用LLM）"""
        logger.info("使用备用查询分析方法")
        
        query_lower = user_query.lower()
        
        # 简单的场景识别
        scene_keywords = {
            "家庭": ["家庭", "亲子", "家人", "温馨", "居家"],
            "商务": ["商务", "办公", "工作", "正式", "专业"],
            "休闲": ["休闲", "放松", "度假", "娱乐", "旅行"],
            "城市": ["城市", "都市", "街道", "市区", "建筑"],
            "自然": ["自然", "风景", "户外", "山", "海", "田野"]
        }
        
        detected_scene = "通用"
        for scene, keywords in scene_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                detected_scene = scene
                break
        
        # 匹配可用标签
        matched_tags = []
        for tag in self.available_tags:
            if tag.lower() in query_lower:
                matched_tags.append(tag)
        
        return {
            "summary": f"查询: {user_query}",
            "key_concepts": user_query.split()[:5],
            "visual_keywords": user_query.split()[:3],
            "matched_tags": {"通用": matched_tags[:10]},
            "scene_type": detected_scene,
            "style_preference": "未指定",
            "search_strategy": "balanced"
        }
    
    def check_index_status(self) -> Dict:
        """检查索引状态和数据更新"""
        try:
            # 检查ChromaDB中的数据
            collection_info = self.chromadb.get_collection_info()
            indexed_count = collection_info.get('count', 0)
            
            # 检查数据库更新
            update_info = self.db_processor.check_data_updates()
            
            # 判断是否需要重建索引
            need_rebuild = False
            rebuild_reason = []
            
            # 如果没有索引
            if indexed_count == 0:
                need_rebuild = True
                rebuild_reason.append("没有现有索引")
            
            # 如果数据库有更新
            elif update_info['has_updates']:
                need_rebuild = True
                rebuild_reason.append(f"数据库{update_info['change_type']}: {update_info['change_count']:,} 条记录")
            
            # 如果索引数量与数据库不匹配
            elif update_info['current_count'] > 0:
                expected_count = update_info['current_count']
                if abs(indexed_count - expected_count) > 100:  # 允许小误差
                    need_rebuild = True
                    rebuild_reason.append(f"索引不匹配: ChromaDB({indexed_count:,}) vs 数据库({expected_count:,})")
            
            return {
                'indexed_count': indexed_count,
                'database_count': update_info['current_count'],
                'need_rebuild': need_rebuild,
                'rebuild_reason': rebuild_reason,
                'update_info': update_info,
                'collection_info': collection_info
            }
            
        except Exception as e:
            logger.error(f"检查索引状态失败: {e}")
            return {
                'indexed_count': 0,
                'database_count': 0,
                'need_rebuild': True,
                'rebuild_reason': [f"检查失败: {e}"],
                'update_info': {'has_updates': False, 'message': 'Unknown'},
                'error': str(e)
            }
            
    def smart_index_management(self, force_rebuild: bool = False, 
                              limit: int = 183247, batch_size: int = 32,
                              chromadb_batch_size: int = 4000) -> bool:
        """智能索引管理"""
        try:
            print("\n🔍 检查索引状态...")
            
            status = self.check_index_status()
            
            print(f"📊 当前状态:")
            print(f"   ChromaDB索引: {status['indexed_count']:,} 条")
            print(f"   数据库记录: {status['database_count']:,} 条")
            
            # 显示更新信息
            update_info = status['update_info']
            print(f"   {update_info['message']}")
            
            if update_info.get('check_time'):
                check_time = datetime.fromisoformat(update_info['check_time'])
                print(f"   检查时间: {check_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 决定是否重建
            if force_rebuild:
                print("🔄 强制重建索引...")
                should_rebuild = True
            elif not status['need_rebuild']:
                print("✅ 索引状态良好，无需重建")
                return True
            else:
                print(f"\n⚠️ 检测到需要重建索引:")
                for reason in status['rebuild_reason']:
                    print(f"   • {reason}")
                
                print(f"\n📈 详细变化:")
                if update_info['change_type'] == 'increased':
                    print(f"   新增 {update_info['change_count']:,} 条记录")
                elif update_info['change_type'] == 'decreased':
                    print(f"   减少 {update_info['change_count']:,} 条记录")
                elif update_info['change_type'] == 'initial':
                    print(f"   初始化，需要索引 {update_info['current_count']:,} 条记录")
                
                # 询问用户
                response = input("\n🤔 是否重建索引? (y/n): ").lower().strip()
                should_rebuild = response in ['y', 'yes', '是']
                
                if not should_rebuild:
                    print("⏭️ 跳过索引重建，使用现有索引")
                    return True
            
            # 执行重建
            if should_rebuild:
                print(f"\n🚀 开始重建索引 (限制: {limit:,} 条记录)...")
                
                # 重置集合
                if status['indexed_count'] > 0:
                    print("🗑️ 清理现有索引...")
                    self.chromadb.reset_collection()
                
                # 加载数据（会自动保存状态）
                print("📊 加载数据库数据...")
                self.db_processor.load_data(limit=limit, save_status=True)
                
                # 构建索引
                print("🔨 构建新索引...")
                self.build_index(
                    batch_size=batch_size, 
                    force_rebuild=True, 
                    limit=limit,
                    chromadb_batch_size=chromadb_batch_size
                )
                
                # 验证结果
                final_status = self.check_index_status()
                print(f"\n✅ 索引重建完成:")
                print(f"   最终索引量: {final_status['indexed_count']:,} 条")
                print(f"   数据库总量: {final_status['database_count']:,} 条")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"智能索引管理失败: {e}")
            print(f"❌ 索引管理失败: {e}")
            return False

class VisualizationTool:
    """可视化工具"""
    
    def __init__(self):
        """初始化可视化工具"""
        self.figure_count = 0
    
    def load_image_from_path(self, image_path: str) -> Optional[Image.Image]:
        """从本地路径加载图片"""
        try:
            if not os.path.exists(image_path):
                logger.warning(f"图片文件不存在: {image_path}")
                return None
            
            image = Image.open(image_path).convert('RGB')
            return image
        except Exception as e:
            logger.warning(f"图片加载失败 {image_path}: {e}")
            return None
    
    def show_search_results(self, query: str, results: List[Dict], 
                          max_display: int = 9, figsize: Tuple[int, int] = (15, 12)):
        """显示搜索结果"""
        if not results:
            print("没有找到相关结果")
            return
        
        display_count = min(len(results), max_display)
        cols = 3
        rows = (display_count + cols - 1) // cols
        
        fig, axes = plt.subplots(rows, cols, figsize=figsize)
        if rows == 1:
            axes = axes.reshape(1, -1)
        elif cols == 1:
            axes = axes.reshape(-1, 1)
        
        query_type = results[0].get('query_type', 'text')
        
        if query_type == 'image':
            fig.suptitle(f'以图搜图结果: {query}', fontsize=16, fontweight='bold')
        else:
            fig.suptitle(f'以文搜图结果: "{query[:50]}"', fontsize=16, fontweight='bold')
        
        for i in range(display_count):
            row, col = i // cols, i % cols
            ax = axes[row, col] if rows > 1 else axes[col]
            
            result = results[i]
            
            # 加载并显示图片
            image = self.load_image_from_path(result['image_path'])
            
            if image is not None:
                ax.imshow(image)
                
                # 设置标题
                title = f"相似度: {result['similarity']:.3f}\nID: {result['id']}"
                
                # 显示合并后的标签
                combined_tags = result.get('combined_tags') or result.get('display_tags', '')
                if combined_tags:
                    tags_display = combined_tags[:30]
                    if len(combined_tags) > 30:
                        tags_display += "..."
                else:
                    tags_display = "无标签"
                
                title += f"\n{tags_display}"
                
                ax.set_title(title, fontsize=9)
                ax.axis('off')
            else:
                ax.text(0.5, 0.5, f"图片加载失败\nID: {result['id']}\n{result['filename']}", 
                       ha='center', va='center', transform=ax.transAxes,
                       fontsize=8, bbox=dict(boxstyle="round,pad=0.3", facecolor="red", alpha=0.3))
                ax.set_title(f"错误: {result['filename']}", fontsize=10)
                ax.axis('off')
        
        # 隐藏多余的子图
        for i in range(display_count, rows * cols):
            row, col = i // cols, i % cols
            ax = axes[row, col] if rows > 1 else axes[col]
            ax.axis('off')
        
        plt.tight_layout()
        self.figure_count += 1
        plt.show()

# 统一的结果显示函数
def display_search_results(results, query_info=""):
    """统一的搜索结果显示函数 - 修复版本"""
    if not results:
        print("❌ 未找到相关结果")
        return
    
    print(f"\n✅ 找到 {len(results)} 个结果")
    
    # 显示查询分析（如果是智能搜索）
    if results and results[0].get('query_analysis'):
        analysis = results[0].get('query_analysis', {})
        print(f"\n🧠 搜索分析:")
        print(f"   理解: {analysis.get('summary', '')}")
        print(f"   场景: {analysis.get('scene_type', '')}")
        print(f"   风格: {analysis.get('style_preference', '')}")
        print(f"   策略: {analysis.get('search_strategy', '')}")
        
        optimized_query = results[0].get('optimized_query', '')
        if optimized_query and optimized_query != query_info:
            print(f"   优化查询: {optimized_query}")
    
    # 显示结果列表
    print(f"\n📋 搜索结果:")
    for i, result in enumerate(results, 1):
        similarity = result.get('similarity', 0)
        print(f"  {i:2d}. 相似度: {similarity:.4f}")
        print(f"      ID: {result.get('id', 'N/A')}")
        print(f"      文件名: {result.get('filename', 'N/A')}")
        print(f"      完整路径: {result.get('image_path', 'N/A')}")
        
        # 安全地获取原始URL
        original_url = result.get('original_url', 'N/A')
        if original_url and original_url != 'N/A':
            print(f"      原始URL: {original_url}")
        else:
            print(f"      原始URL: 未找到")
        
        # 修复的标签显示逻辑
        display_tags = (
            result.get('combined_tags') or
            result.get('display_tags') or
            result.get('original_ai_tags') or
            result.get('original_tags', '')
        )
        
        if display_tags and str(display_tags).strip() and str(display_tags).strip() not in ['nan', '无标签信息', '图片为空']:
            display_tags_str = str(display_tags)
            
            if display_tags_str.strip() == '图片为空':
                print(f"      标签: 无有效标签信息")
            else:
                if len(display_tags_str) > 150:
                    print(f"      标签: {display_tags_str[:150]}...")
                else:
                    print(f"      标签: {display_tags_str}")
        else:
            print(f"      标签: 无标签信息")
        
        # 检查文件是否存在
        image_path = result.get('image_path', '')
        if image_path:
            file_exists = os.path.exists(image_path)
            print(f"      文件状态: {'✅ 存在' if file_exists else '❌ 不存在'}")
        else:
            print(f"      文件状态: ❌ 无路径信息")
        print()

def main():
    """主函数 - 支持LLM增强的智能搜索"""
    print("=" * 60)
    print("🎨 CLIP + ChromaDB + MySQL + LLM 智能图片检索系统 v2.1")  
    print("🤖 集成OpenRouter大语言模型进行自然语言理解")
    print("🏠 处理本地绝对路径图片")
    print("📊 智能索引管理和增量更新检测")
    print("=" * 60)
    
    # OpenRouter配置
    print("\n🔧 配置OpenRouter (可选):")
    print("如果您有OpenRouter API密钥，可以启用LLM增强搜索")
    print("没有密钥也可以使用基础搜索功能")
    
    use_openrouter = input("是否配置OpenRouter? (y/n): ").lower() == 'y'
    openrouter_api_key = None
    openrouter_model = "anthropic/claude-3-haiku"
    
    if use_openrouter:
        openrouter_api_key = input("请输入OpenRouter API密钥: ").strip()
        if not openrouter_api_key:
            print("⚠️ 未提供API密钥，将使用基础搜索功能")
        else:
            print("\n🤖 选择LLM模型:")
            models = [
                "anthropic/claude-3-haiku",
                "anthropic/claude-3-5-sonnet", 
                "openai/gpt-4o-mini",
                "openai/gpt-3.5-turbo",
                "meta-llama/llama-3.1-8b-instruct"
            ]
            for i, model in enumerate(models, 1):
                print(f"{i}. {model}")
            
            model_choice = input("请选择模型 (默认: 1): ").strip()
            try:
                model_index = int(model_choice) - 1 if model_choice else 0
                openrouter_model = models[model_index]
            except:
                openrouter_model = "anthropic/claude-3-haiku"
            
            print(f"选择的模型: {openrouter_model}")
    
    # CLIP模型选择
    print("\n🤖 选择CLIP模型:")
    clip_models = ["ViT-B/32", "ViT-B/16", "ViT-L/14", "RN50"]
    for i, model in enumerate(clip_models, 1):
        print(f"{i}. {model}")
    
    model_choice = input("请选择CLIP模型 (默认: 1): ").strip()
    try:
        model_index = int(model_choice) - 1 if model_choice else 0
        clip_model = clip_models[model_index]
    except:
        clip_model = "ViT-B/32"
    
    try:
        # 初始化增强检索系统
        print("\n🚀 初始化智能检索系统...")
        
        retrieval_system = EnhancedDatabaseImageRetrievalSystem(
            clip_model=clip_model,
            chromadb_port=6600,
            openrouter_api_key=openrouter_api_key,
            openrouter_model=openrouter_model
        )
        
        # 智能索引管理
        print("\n📊 智能索引管理...")
        retrieval_system.smart_index_management(
            force_rebuild=False,  # 不强制重建，让系统智能判断
            limit=183247
        )
        
        # 显示最终系统信息
        system_info = retrieval_system.get_system_info()
        print("\n📊 系统就绪:")
        print(f"   LLM集成: {'✅ 已启用' if retrieval_system.openrouter else '❌ 未启用'}")
        if retrieval_system.openrouter:
            print(f"   LLM模型: {openrouter_model}")
        print(f"   CLIP模型: {clip_model}")
        print(f"   已索引: {system_info['collection']['count']:,} 张图片")
        print(f"   可用标签: {len(retrieval_system.available_tags)} 个")
        
        # 初始化可视化工具
        viz_tool = VisualizationTool()
        
        # 交互式搜索循环
        while True:
            print("\n" + "="*60)
            print("🔍 智能图片检索系统 v2.1")
            
            if retrieval_system.openrouter:
                print("1. 智能搜索 (LLM + CLIP + 标签)")
                print("2. 基础搜索 (CLIP)")
                print("3. 以图搜图")
            else:
                print("1. 基础搜索 (CLIP)")
                print("2. 以图搜图")
                
            print("5. 手动检查更新")
            print("6. 检查数据完整性")
            print("7. 强制重建索引")
            print("8. 查看系统状态")
            print("9. 退出")
            
            choice = input("请选择功能: ").strip()
            
            # 智能搜索或基础搜索
            if choice == '1':
                if retrieval_system.openrouter:
                    search_mode = 'intelligent'
                    print("\n🧠 智能搜索 (LLM理解 + 多维度匹配)")
                    print("💡 智能搜索建议:")
                    print("   • 用自然语言描述：如'温馨的家庭出游场景'")
                    print("   • 描述情感和氛围：如'商务正式感'、'年轻活力'")
                    print("   • 包含场景信息：如'城市街道'、'自然风光'")
                    print("   • 提及风格偏好：如'现代简约'、'经典优雅'")
                else:
                    search_mode = 'basic'
                    print("\n🔍 基础搜索 (CLIP视觉特征)")
                
                user_query = input("📝 请输入搜索描述: ").strip()
                if not user_query:
                    continue
                
                top_k = input("返回结果数量 (默认: 9): ").strip()
                try:
                    top_k = int(top_k) if top_k else 9
                except:
                    top_k = 9
                
                print(f"\n🔍 开始搜索: '{user_query}'")
                
                try:
                    if search_mode == 'intelligent':
                        results = retrieval_system.search_by_text_intelligent(user_query, top_k)
                    else:
                        results = retrieval_system.search_by_text(user_query, top_k)
                    
                    # 显示结果
                    display_search_results(results, user_query)
                    
                    # 可视化选项
                    if results:
                        show_viz = input("📊 显示图片结果? (y/n): ").lower() == 'y'
                        if show_viz:
                            viz_tool.show_search_results(user_query, results, max_display=top_k)
                            
                except Exception as e:
                    print(f"❌ 搜索失败: {e}")
                    logger.exception("搜索错误")
            
            # 基础搜索或以图搜图
            elif choice == '2':
                if retrieval_system.openrouter:
                    print("\n🔍 基础搜索 (CLIP视觉特征)")
                    user_query = input("📝 请输入搜索描述: ").strip()
                    if not user_query:
                        continue
                    
                    top_k = input("返回结果数量 (默认: 9): ").strip()
                    try:
                        top_k = int(top_k) if top_k else 9
                    except:
                        top_k = 9
                    
                    print(f"\n🔍 开始基础搜索: '{user_query}'")
                    results = retrieval_system.search_by_text(user_query, top_k)
                    
                    # 显示结果
                    display_search_results(results, user_query)
                    
                    # 可视化选项
                    if results:
                        show_viz = input("📊 显示图片结果? (y/n): ").lower() == 'y'
                        if show_viz:
                            viz_tool.show_search_results(user_query, results, max_display=top_k)
                else:
                    # 没有OpenRouter时，选项2是以图搜图
                    print("\n🖼️ 以图搜图")
                    query_image_path = input("请输入图片路径: ").strip()
                    if query_image_path and os.path.exists(query_image_path):
                        top_k = input("返回结果数量 (默认: 9): ").strip()
                        top_k = int(top_k) if top_k.isdigit() else 9
                        
                        print(f"\n🔍 开始以图搜图: '{os.path.basename(query_image_path)}'")
                        results = retrieval_system.search_by_image(query_image_path, top_k)
                        
                        if results:
                            for result in results:
                                result['query_type'] = 'image'
                            
                            display_search_results(results, f"查询图片: {os.path.basename(query_image_path)}")
                            
                            show_viz = input("📊 显示图片结果? (y/n): ").lower() == 'y'
                            if show_viz:
                                viz_tool.show_search_results(f"查询图片: {os.path.basename(query_image_path)}", results, max_display=top_k)
                        else:
                            print("❌ 未找到相似图片")
                    else:
                        print("❌ 图片文件不存在")
            
            # 以图搜图（当有OpenRouter时）
            elif choice == '3' and retrieval_system.openrouter:
                print("\n🖼️ 以图搜图")
                query_image_path = input("请输入图片路径: ").strip()
                if query_image_path and os.path.exists(query_image_path):
                    top_k = input("返回结果数量 (默认: 9): ").strip()
                    top_k = int(top_k) if top_k.isdigit() else 9
                    
                    print(f"\n🔍 开始以图搜图: '{os.path.basename(query_image_path)}'")
                    results = retrieval_system.search_by_image(query_image_path, top_k)
                    
                    if results:
                        for result in results:
                            result['query_type'] = 'image'
                        
                        display_search_results(results, f"查询图片: {os.path.basename(query_image_path)}")
                        
                        show_viz = input("📊 显示图片结果? (y/n): ").lower() == 'y'
                        if show_viz:
                            viz_tool.show_search_results(f"查询图片: {os.path.basename(query_image_path)}", results, max_display=top_k)
                    else:
                        print("❌ 未找到相似图片")
                else:
                    print("❌ 图片文件不存在")
            
            # 新增选项5：手动检查更新
            elif choice == '5':
                print("\n🔍 手动检查数据更新...")
                try:
                    status = retrieval_system.check_index_status()
                    update_info = status['update_info']
                    
                    print(f"\n📊 检查结果:")
                    print(f"   {update_info['message']}")
                    print(f"   ChromaDB索引: {status['indexed_count']:,} 条")
                    print(f"   数据库记录: {status['database_count']:,} 条")
                    
                    if status['need_rebuild']:
                        print(f"\n⚠️ 建议重建原因:")
                        for reason in status['rebuild_reason']:
                            print(f"   • {reason}")
                        
                        rebuild = input("\n🤔 是否立即重建索引? (y/n): ").lower() == 'y'
                        if rebuild:
                            retrieval_system.smart_index_management(force_rebuild=True)
                    else:
                        print("✅ 索引状态良好，无需重建")
                        
                except Exception as e:
                    print(f"❌ 检查失败: {e}")
            
            # 原有的选项6改为检查数据完整性
            elif choice == '6':
                print("\n🔍 检查数据完整性...")
                try:
                    integrity_report = retrieval_system.check_data_integrity()
                    if integrity_report['missing_count'] > 0:
                        print(f"\n发现 {integrity_report['missing_count']} 条缺失数据")
                        print("建议重建索引以确保数据完整性")
                    else:
                        print("✅ 数据完整性良好!")
                except Exception as e:
                    print(f"❌ 检查失败: {e}")
            
            # 新增选项7：强制重建索引
            elif choice == '7':
                print("\n🔄 强制重建索引...")
                try:
                    confirm = input("⚠️ 这将删除现有索引并重新构建，确认吗? (y/n): ").lower()
                    if confirm == 'y':
                        retrieval_system.smart_index_management(force_rebuild=True)
                    else:
                        print("❌ 已取消")
                except Exception as e:
                    print(f"❌ 重建失败: {e}")
                
                
            elif choice == '8':
                # 系统状态
                system_info = retrieval_system.get_system_info()
                print("\n📊 详细系统状态:")
                print(f"   LLM集成: {'✅' if retrieval_system.openrouter else '❌'}")
                if retrieval_system.openrouter:
                    print(f"   LLM模型: {openrouter_model}")
                print(f"   CLIP模型: {system_info['clip_model']}")
                print(f"   特征维度: {system_info['feature_dim']}")
                print(f"   运行设备: {system_info['device']}")
                print(f"   已索引: {system_info['collection']['count']} 张图片")
                print(f"   存储模式: {system_info['collection'].get('mode', 'unknown')}")
                print(f"   可用标签: {len(retrieval_system.available_tags)} 个")
                
                # 显示数据库字段信息
                if 'dataset' in system_info:
                    dataset_info = system_info['dataset']
                    print(f"   数据库字段: {dataset_info.get('available_tag_fields', [])}")
                    print(f"   标签统计: {dataset_info.get('tag_stats', {})}")
                
            elif choice == '9':
                print("\n👋 感谢使用智能检索系统!")
                break
            
            else:
                print("❌ 无效选择")
                
    
    except Exception as e:
        print(f"\n❌ 系统错误: {e}")
        logger.exception("系统错误")
    
    finally:
        try:
            retrieval_system.close_connections()
        except:
            pass

if __name__ == "__main__":
    main()