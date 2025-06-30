from flask import Flask, render_template, request, jsonify, send_file, Response
import os
import json
import base64
from io import BytesIO
from PIL import Image
import logging
import requests
import time
from urllib.parse import quote
from googletrans import Translator
import re

# 导入您的检索系统 - 修改这里的导入路径
from main import EnhancedDatabaseImageRetrievalSystem

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 全局配置
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY', '')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'anthropic/claude-sonnet-4')
CLIP_MODEL = os.getenv('CLIP_MODEL', 'ViT-B/32')

# 外部API配置
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY', '')
UNSPLASH_ACCESS_KEY = os.getenv('UNSPLASH_ACCESS_KEY', '')
PIXABAY_API_KEY = os.getenv('PIXABAY_API_KEY', '')

# 全局检索系统实例
retrieval_system = None
system_initialized = False
last_index_check = None

def search_pixabay(query, page=1, per_page=20):
    """搜索Pixabay图片"""
    if not PIXABAY_API_KEY:
        return []
    
    url = "https://pixabay.com/api/"
    params = {
        'key': PIXABAY_API_KEY,
        'q': query,
        'image_type': 'photo',
        'orientation': 'all',
        'category': 'backgrounds,fashion,nature,science,education,feelings,health,people,religion,places,animals,industry,computer,food,sports,transportation,travel,buildings,business,music',
        'per_page': min(per_page, 200),
        'page': page,
        'safesearch': 'true',
        'order': 'popular'
    }
    
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    results = []
    
    for hit in data.get('hits', []):
        result = {
            'id': f"pixabay_{hit['id']}",
            'source': 'pixabay',
            'title': hit.get('tags', 'Untitled'),
            'description': hit.get('tags', ''),
            'url': hit['pageURL'],
            'image_url': hit['webformatURL'],
            'thumbnail_url': hit['previewURL'],
            'large_url': hit['largeImageURL'],
            'original_url': hit.get('fullHDURL', hit['largeImageURL']),
            'photographer': hit['user'],
            'photographer_url': f"https://pixabay.com/users/{hit['user']}-{hit['user_id']}/",
            'width': hit['imageWidth'],
            'height': hit['imageHeight'],
            'color': '#4CAF50',
            'likes': hit.get('likes', 0),
            'downloads': hit.get('downloads', 0),
            'views': hit.get('views', 0),
            'relevance': min((hit.get('likes', 0) + hit.get('downloads', 0) / 10) / 1000, 1.0)
        }
        results.append(result)
    
    return results

def safe_image_to_jpeg_base64(image_path, max_size=(300, 300), quality=85):
    """
    安全地将图片转换为JPEG格式的base64编码
    处理各种图片格式和模式
    """
    try:
        with Image.open(image_path) as img:
            # 获取原始模式
            original_mode = img.mode
            logger.debug(f"处理图片 {image_path}, 原始模式: {original_mode}")
            
            # 根据不同的图片模式进行处理
            if original_mode in ('RGBA', 'LA'):
                # 有Alpha通道的图片，需要合成到白色背景
                background = Image.new('RGB', img.size, (255, 255, 255))
                if original_mode == 'RGBA':
                    # 使用Alpha通道进行合成
                    background.paste(img, mask=img.split()[-1])
                else:  # LA mode
                    # 灰度+Alpha，先转换为RGBA
                    img_rgba = img.convert('RGBA')
                    background.paste(img_rgba, mask=img_rgba.split()[-1])
                processed_img = background
                
            elif original_mode == 'P':
                # 调色板模式
                if 'transparency' in img.info:
                    # 有透明度信息，转换为RGBA再合成
                    img_rgba = img.convert('RGBA')
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img_rgba, mask=img_rgba.split()[-1])
                    processed_img = background
                else:
                    # 无透明度，直接转换为RGB
                    processed_img = img.convert('RGB')
                    
            elif original_mode in ('L', '1'):
                # 灰度或二值图像，转换为RGB
                processed_img = img.convert('RGB')
                
            elif original_mode == 'CMYK':
                # CMYK模式转换为RGB
                processed_img = img.convert('RGB')
                
            elif original_mode == 'RGB':
                # 已经是RGB，直接使用
                processed_img = img.copy()
                
            else:
                # 其他未知模式，强制转换为RGB
                logger.warning(f"未知图片模式 {original_mode}，强制转换为RGB")
                processed_img = img.convert('RGB')
            
            # 压缩尺寸
            processed_img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 保存为JPEG格式的base64
            buffer = BytesIO()
            processed_img.save(buffer, format='JPEG', quality=quality, optimize=True)
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            return f"data:image/jpeg;base64,{img_str}"
            
    except Exception as e:
        logger.error(f"图片处理失败 {image_path}: {e}")
        return None

def init_retrieval_system():
    """延迟初始化检索系统"""
    global retrieval_system, system_initialized
    
    if system_initialized and retrieval_system is not None:
        logger.info("检索系统已初始化，跳过重复初始化")
        return retrieval_system
    
    logger.info("正在初始化检索系统...")
    try:
        retrieval_system = EnhancedDatabaseImageRetrievalSystem(
            clip_model=CLIP_MODEL,
            chromadb_port=6600,
            openrouter_api_key=OPENROUTER_API_KEY,
            openrouter_model=OPENROUTER_MODEL
        )
        
        system_initialized = True
        logger.info("✅ 检索系统初始化完成")
        
    except Exception as e:
        logger.error(f"检索系统初始化失败: {e}")
        raise
    
    return retrieval_system

def check_and_manage_index():
    """检查并管理索引状态"""
    global retrieval_system, last_index_check
    
    if retrieval_system is None:
        retrieval_system = init_retrieval_system()
    
    try:
        # 检查索引状态
        status = retrieval_system.check_index_status()
        
        # 记录检查时间
        last_index_check = time.time()
        
        if status.get('need_rebuild', False):
            update_info = status.get('update_info', {})
            indexed_count = status.get('indexed_count', 0)
            database_count = status.get('database_count', 0)
            
            logger.info(f"📊 索引状态检查:")
            logger.info(f"   ChromaDB索引: {indexed_count:,} 条")
            logger.info(f"   数据库记录: {database_count:,} 条")
            logger.info(f"   {update_info.get('message', '需要重建索引')}")
            
            # 如果有重建原因，记录详情
            rebuild_reasons = status.get('rebuild_reason', [])
            if rebuild_reasons:
                logger.info(f"   重建原因: {'; '.join(rebuild_reasons)}")
            
            # 自动检查是否应该重建
            if update_info.get('change_type') == 'initial':
                # 初次运行，自动构建索引
                logger.info("🚀 初次运行，自动构建索引...")
                return auto_rebuild_index()
                
            elif update_info.get('change_type') in ['increased', 'decreased']:
                # 数据有变化，询问是否重建
                change_count = update_info.get('change_count', 0)
                change_type = update_info.get('change_type', 'changed')
                
                logger.warning(f"⚠️ 检测到数据库更新: {change_type} {change_count:,} 条记录")
                logger.warning("   建议重建索引以确保数据一致性")
                logger.warning("   可通过 /api/rebuild_index 接口手动重建")
                
                # 在Web环境下，不自动重建，而是返回状态让用户选择
                return {
                    'needs_user_action': True,
                    'status': status,
                    'message': f"数据库{change_type} {change_count:,} 条记录，建议重建索引"
                }
            else:
                # 其他情况的不匹配
                logger.warning(f"⚠️ 索引与数据库不匹配: {'; '.join(rebuild_reasons)}")
                return {
                    'needs_user_action': True,
                    'status': status,
                    'message': "索引与数据库不匹配，建议重建"
                }
        else:
            logger.info(f"✅ 索引状态良好: {indexed_count:,} 条记录")
            return {'status': 'good', 'indexed_count': indexed_count}
            
    except Exception as e:
        logger.error(f"索引状态检查失败: {e}")
        return {'error': str(e)}

def auto_rebuild_index():
    """自动重建索引"""
    global retrieval_system
    
    try:
        logger.info("🔄 开始自动重建索引...")
        
        # 使用智能索引管理
        rebuild_result = retrieval_system.smart_index_management(
            force_rebuild=True,
            limit=183247
        )
        
        if rebuild_result:
            final_status = retrieval_system.check_index_status()
            indexed_count = final_status.get('indexed_count', 0)
            
            logger.info(f"✅ 自动重建完成: {indexed_count:,} 条记录")
            return {
                'status': 'rebuilt', 
                'indexed_count': indexed_count,
                'message': f"自动重建完成，索引了 {indexed_count:,} 条记录"
            }
        else:
            logger.error("❌ 自动重建失败")
            return {'error': '自动重建失败'}
            
    except Exception as e:
        logger.error(f"自动重建索引失败: {e}")
        return {'error': str(e)}

def ensure_data_ready():
    """确保数据就绪（智能检查）"""
    global retrieval_system, last_index_check
    
    # 如果最近检查过且时间不长，跳过检查
    if last_index_check and (time.time() - last_index_check) < 300:  # 5分钟内
        logger.debug("最近已检查过索引状态，跳过重复检查")
        return {'status': 'cached'}
    
    # 执行索引检查和管理
    return check_and_manage_index()

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/system_info')
def system_info():
    """获取系统信息"""
    try:
        system = init_retrieval_system()
        
        # 检查索引状态
        index_status = ensure_data_ready()
        
        info = system.get_system_info()
        
        return jsonify({
            'success': True,
            'data': {
                'llm_enabled': system.openrouter is not None,
                'llm_model': OPENROUTER_MODEL if system.openrouter else None,
                'clip_model': info.get('clip_model', ''),
                'indexed_count': info.get('collection', {}).get('count', 0),
                'available_tags': len(system.available_tags),
                'status': 'ready',
                'external_sources': {
                    'pexels': bool(PEXELS_API_KEY),
                    'unsplash': bool(UNSPLASH_ACCESS_KEY),
                    'pixabay': bool(PIXABAY_API_KEY),
                },
                'index_status': index_status  # 添加索引状态信息
            }
        })
    except Exception as e:
        logger.error(f"获取系统信息失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/check_index_status')
def check_index_status_api():
    """检查索引状态API"""
    try:
        system = init_retrieval_system()
        status = system.check_index_status()
        
        return jsonify({
            'success': True,
            'data': status
        })
        
    except Exception as e:
        logger.error(f"检查索引状态失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/rebuild_index', methods=['POST'])
def rebuild_index_api():
    """重建索引API"""
    try:
        data = request.get_json() or {}
        force = data.get('force', False)
        limit = data.get('limit', 183247)
        
        system = init_retrieval_system()
        
        logger.info(f"🔄 开始手动重建索引 (force={force}, limit={limit})...")
        
        # 使用智能索引管理
        rebuild_result = system.smart_index_management(
            force_rebuild=force,
            limit=limit
        )
        
        if rebuild_result:
            final_status = system.check_index_status()
            indexed_count = final_status.get('indexed_count', 0)
            
            return jsonify({
                'success': True,
                'data': {
                    'message': f"索引重建完成，索引了 {indexed_count:,} 条记录",
                    'indexed_count': indexed_count,
                    'status': final_status
                }
            })
        else:
            return jsonify({
                'success': False,
                'error': '重建失败'
            })
            
    except Exception as e:
        logger.error(f"手动重建索引失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/search/intelligent', methods=['POST'])
def intelligent_search():
    """智能搜索"""
    try:
        # 确保数据就绪
        data_status = ensure_data_ready()
        if data_status.get('needs_user_action'):
            return jsonify({
                'success': False,
                'error': f"数据库有更新，{data_status.get('message', '建议重建索引')}",
                'needs_rebuild': True,
                'rebuild_info': data_status.get('status')
            })
        
        data = request.get_json()
        query = data.get('query', '').strip()
        top_k = data.get('top_k', 9)
        
        if not query:
            return jsonify({
                'success': False,
                'error': '搜索内容不能为空'
            })
        
        system = init_retrieval_system()
        
        if not system.openrouter:
            return jsonify({
                'success': False,
                'error': 'LLM功能未启用'
            })
        
        logger.info(f"执行智能搜索: {query}")
        results = system.search_by_text_intelligent(query, top_k)
        
        # 转换结果格式
        formatted_results = []
        for result in results:
            formatted_result = format_search_result(result)
            formatted_results.append(formatted_result)
        
        return jsonify({
            'success': True,
            'data': {
                'query': query,
                'results': formatted_results,
                'query_analysis': results[0].get('query_analysis', {}) if results else {},
                'search_type': 'intelligent'
            }
        })
        
    except Exception as e:
        logger.error(f"智能搜索失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/search/basic', methods=['POST'])
def basic_search():
    """基础搜索"""
    try:
        # 确保数据就绪
        data_status = ensure_data_ready()
        if data_status.get('needs_user_action'):
            return jsonify({
                'success': False,
                'error': f"数据库有更新，{data_status.get('message', '建议重建索引')}",
                'needs_rebuild': True,
                'rebuild_info': data_status.get('status')
            })
        
        data = request.get_json()
        query = data.get('query', '').strip()
        top_k = data.get('top_k', 9)
        
        if not query:
            return jsonify({
                'success': False,
                'error': '搜索内容不能为空'
            })
        
        system = init_retrieval_system()
        
        logger.info(f"执行基础搜索: {query}")
        results = system.search_by_text(query, top_k)
        
        # 转换结果格式
        formatted_results = []
        for result in results:
            formatted_result = format_search_result(result)
            formatted_results.append(formatted_result)
        
        return jsonify({
            'success': True,
            'data': {
                'query': query,
                'results': formatted_results,
                'search_type': 'basic'
            }
        })
        
    except Exception as e:
        logger.error(f"基础搜索失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/search/external', methods=['POST'])
def external_search():
    """外部图片搜索（Pexels + Unsplash + Pixabay）"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        source = data.get('source', 'all')
        page = data.get('page', 1)
        per_page = data.get('per_page', 20)
        
        if not query:
            return jsonify({
                'success': False,
                'error': '搜索内容不能为空'
            })
        
        logger.info(f"执行外部搜索: {query}, 源: {source}")
        
        results = []
        sources_count = 0
        
        # 计算有多少个源可用
        available_sources = []
        if source in ['all', 'pexels'] and PEXELS_API_KEY:
            available_sources.append('pexels')
        if source in ['all', 'unsplash'] and UNSPLASH_ACCESS_KEY:
            available_sources.append('unsplash')
        if source in ['all', 'pixabay'] and PIXABAY_API_KEY:
            available_sources.append('pixabay')
        
        # 如果选择的是单个源，就只搜索那个源
        if source != 'all':
            available_sources = [source] if source in available_sources else []
        
        sources_count = len(available_sources)
        per_source = max(per_page // sources_count, 5) if sources_count > 0 else per_page
        
        # 搜索Pexels
        if 'pexels' in available_sources and PEXELS_API_KEY:
            try:
                pexels_results = search_pexels(query, page, per_source)
                results.extend(pexels_results)
                logger.info(f"Pexels返回{len(pexels_results)}个结果")
            except Exception as e:
                logger.error(f"Pexels搜索失败: {e}")
        
        # 搜索Unsplash
        if 'unsplash' in available_sources and UNSPLASH_ACCESS_KEY:
            try:
                unsplash_results = search_unsplash(query, page, per_source)
                results.extend(unsplash_results)
                logger.info(f"Unsplash返回{len(unsplash_results)}个结果")
            except Exception as e:
                logger.error(f"Unsplash搜索失败: {e}")
        
        # 搜索Pixabay
        if 'pixabay' in available_sources and PIXABAY_API_KEY:
            try:
                pixabay_results = search_pixabay(query, page, per_source)
                results.extend(pixabay_results)
                logger.info(f"Pixabay返回{len(pixabay_results)}个结果")
            except Exception as e:
                logger.error(f"Pixabay搜索失败: {e}")
        
        # 按相关性排序
        results.sort(key=lambda x: (x.get('relevance', 0), x.get('likes', 0)), reverse=True)
        
        # 限制结果数量
        if len(results) > per_page:
            results = results[:per_page]
        
        return jsonify({
            'success': True,
            'data': {
                'query': query,
                'source': source,
                'results': results,
                'page': page,
                'total_results': len(results),
                'available_sources': available_sources,
                'search_type': 'external'
            }
        })
        
    except Exception as e:
        logger.error(f"外部搜索失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

def search_pexels(query, page=1, per_page=20):
    """搜索Pexels图片"""
    if not PEXELS_API_KEY:
        return []
    
    url = "https://api.pexels.com/v1/search"
    headers = {
        'Authorization': PEXELS_API_KEY
    }
    params = {
        'query': query,
        'page': page,
        'per_page': min(per_page, 80),
        'orientation': 'all'
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    
    data = response.json()
    results = []
    
    for photo in data.get('photos', []):
        result = {
            'id': f"pexels_{photo['id']}",
            'source': 'pexels',
            'title': photo.get('alt', 'Untitled'),
            'description': photo.get('alt', ''),
            'url': photo['url'],
            'image_url': photo['src']['medium'],
            'thumbnail_url': photo['src']['small'],
            'large_url': photo['src']['large'],
            'original_url': photo['src']['original'],
            'photographer': photo['photographer'],
            'photographer_url': photo['photographer_url'],
            'width': photo['width'],
            'height': photo['height'],
            'color': photo.get('avg_color', '#000000'),
            'relevance': 1.0
        }
        results.append(result)
    
    return results

def search_unsplash(query, page=1, per_page=20):
    """搜索Unsplash图片"""
    if not UNSPLASH_ACCESS_KEY:
        return []
    
    url = "https://api.unsplash.com/search/photos"
    headers = {
        'Authorization': f'Client-ID {UNSPLASH_ACCESS_KEY}',
        'Accept-Version': 'v1'
    }
    params = {
        'query': query,
        'page': page,
        'per_page': min(per_page, 30),
    }
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        logger.info(f"Unsplash请求URL: {response.url}")
        logger.info(f"Unsplash响应状态: {response.status_code}")
        
        if response.status_code == 401:
            logger.error("Unsplash API密钥无效或未授权")
            return []
        elif response.status_code == 403:
            logger.error("Unsplash API请求超出限制")
            return []
        elif response.status_code != 200:
            logger.error(f"Unsplash API错误: {response.status_code} - {response.text}")
            return []
        
        response.raise_for_status()
        
        data = response.json()
        results = []
        
        for photo in data.get('results', []):
            result = {
                'id': f"unsplash_{photo['id']}",
                'source': 'unsplash',
                'title': photo.get('description') or photo.get('alt_description', 'Untitled'),
                'description': photo.get('description', ''),
                'url': photo['links']['html'],
                'image_url': photo['urls']['regular'],
                'thumbnail_url': photo['urls']['thumb'],
                'large_url': photo['urls']['full'],
                'original_url': photo['urls']['raw'],
                'photographer': photo['user']['name'],
                'photographer_url': photo['user']['links']['html'],
                'width': photo['width'],
                'height': photo['height'],
                'color': photo.get('color', '#000000'),
                'likes': photo.get('likes', 0),
                'relevance': min(photo.get('likes', 0) / 1000, 1.0)
            }
            results.append(result)
        
        return results
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Unsplash网络请求失败: {e}")
        return []
    except Exception as e:
        logger.error(f"Unsplash搜索异常: {e}")
        return []

@app.route('/api/search/image', methods=['POST'])
def image_search():
    """以图搜图"""
    try:
        # 确保数据就绪
        data_status = ensure_data_ready()
        if data_status.get('needs_user_action'):
            return jsonify({
                'success': False,
                'error': f"数据库有更新，{data_status.get('message', '建议重建索引')}",
                'needs_rebuild': True,
                'rebuild_info': data_status.get('status')
            })
        
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'error': '请上传图片文件'
            })
        
        file = request.files['image']
        top_k = int(request.form.get('top_k', 9))
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': '请选择图片文件'
            })
        
        # 保存临时文件
        temp_path = f"/tmp/search_image_{file.filename}"
        file.save(temp_path)
        
        try:
            system = init_retrieval_system()
            
            logger.info(f"执行以图搜图: {file.filename}")
            results = system.search_by_image(temp_path, top_k)
            
            # 转换结果格式
            formatted_results = []
            for result in results:
                formatted_result = format_search_result(result)
                formatted_results.append(formatted_result)
            
            return jsonify({
                'success': True,
                'data': {
                    'query_image': file.filename,
                    'results': formatted_results,
                    'search_type': 'image'
                }
            })
            
        finally:
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
    except Exception as e:
        logger.error(f"以图搜图失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

# 保留其他现有的API路由...
# download_image, download_external_image, serve_image, 
# search_similar_by_path, search_similar_by_id, get_image_info 等

@app.route('/api/download_image', methods=['POST'])
def download_image():
    """下载图片"""
    try:
        data = request.get_json()
        image_path = data.get('image_path', '')
        
        if not image_path or not os.path.exists(image_path):
            return jsonify({
                'success': False,
                'error': '图片文件不存在'
            })
        
        return send_file(
            image_path, 
            as_attachment=True, 
            download_name=os.path.basename(image_path),
            mimetype='application/octet-stream'
        )
        
    except Exception as e:
        logger.error(f"图片下载失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/download_external', methods=['POST'])
def download_external_image():
    """下载外部图片"""
    try:
        data = request.get_json()
        image_url = data.get('image_url', '')
        filename = data.get('filename', 'image.jpg')
        
        if not image_url:
            return jsonify({
                'success': False,
                'error': '图片URL不能为空'
            })
        
        # 下载图片
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        
        # 返回图片数据
        return Response(
            response.content,
            mimetype=response.headers.get('Content-Type', 'image/jpeg'),
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as e:
        logger.error(f"外部图片下载失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/image/<path:image_path>')
def serve_image(image_path):
    """提供图片服务"""
    try:
        # 确保路径安全
        if not os.path.exists(image_path):
            logger.warning(f"图片不存在: {image_path}")
            return "Image not found", 404
        
        return send_file(image_path, mimetype='image/jpeg')
        
    except Exception as e:
        logger.error(f"图片服务失败: {e}")
        return "Image error", 500

def format_search_result(result):
    """格式化搜索结果"""
    try:
        # 获取图片的base64编码用于前端显示
        image_path = result.get('image_path', '')
        image_base64 = None
        
        if image_path and os.path.exists(image_path):
            image_base64 = safe_image_to_jpeg_base64(image_path)
        
        # 获取显示标签
        display_tags = (
            result.get('combined_tags') or 
            result.get('display_tags') or 
            result.get('ai_tags') or 
            result.get('original_ai_tags') or 
            result.get('original_tags', '')
        )
        
        if not display_tags or str(display_tags).strip() in ['nan', '无标签信息', '图片为空']:
            display_tags = '无标签信息'
        
        return {
            'id': result.get('id', ''),
            'filename': result.get('filename', ''),
            'image_path': image_path,
            'image_base64': image_base64,
            'image_exists': os.path.exists(image_path) if image_path else False,
            'display_tags': str(display_tags),
            'similarity': result.get('similarity', 0),
            'original_url': result.get('original_url', ''),
        }
        
    except Exception as e:
        logger.error(f"格式化结果失败: {e}")
        return {
            'id': result.get('id', ''),
            'filename': result.get('filename', ''),
            'error': str(e),
            'similarity': result.get('similarity', 0)
        }

@app.route('/api/search/similar_by_path', methods=['POST'])
def search_similar_by_path():
    """基于图片路径搜索相似图片"""
    try:
        # 确保数据就绪
        data_status = ensure_data_ready()
        if data_status.get('needs_user_action'):
            return jsonify({
                'success': False,
                'error': f"数据库有更新，{data_status.get('message', '建议重建索引')}",
                'needs_rebuild': True,
                'rebuild_info': data_status.get('status')
            })
        
        data = request.get_json()
        image_path = data.get('image_path', '').strip()
        top_k = data.get('top_k', 9)
        exclude_self = data.get('exclude_self', True)
        
        if not image_path:
            return jsonify({
                'success': False,
                'error': '图片路径不能为空'
            })
        
        if not os.path.exists(image_path):
            return jsonify({
                'success': False,
                'error': '图片文件不存在'
            })
        
        system = init_retrieval_system()
        
        logger.info(f"执行相似图搜索: {os.path.basename(image_path)}")
        
        search_count = top_k + 1 if exclude_self else top_k
        results = system.search_by_image(image_path, search_count)
        
        # 排除自身
        if exclude_self and results:
            current_path = os.path.abspath(image_path)
            filtered_results = []
            
            for result in results:
                result_path = result.get('image_path', '')
                if result_path and os.path.abspath(result_path) != current_path:
                    filtered_results.append(result)
                    if len(filtered_results) >= top_k:
                        break
            
            results = filtered_results
        
        # 转换结果格式
        formatted_results = []
        for result in results:
            formatted_result = format_search_result(result)
            formatted_results.append(formatted_result)
        
        return jsonify({
            'success': True,
            'data': {
                'query_image': os.path.basename(image_path),
                'query_path': image_path,
                'results': formatted_results,
                'search_type': 'similar_image',
                'excluded_self': exclude_self
            }
        })
        
    except Exception as e:
        logger.error(f"相似图搜索失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/search/similar_by_id', methods=['POST'])
def search_similar_by_id():
    """基于图片ID搜索相似图片"""
    try:
        # 确保数据就绪
        data_status = ensure_data_ready()
        if data_status.get('needs_user_action'):
            return jsonify({
                'success': False,
                'error': f"数据库有更新，{data_status.get('message', '建议重建索引')}",
                'needs_rebuild': True,
                'rebuild_info': data_status.get('status')
            })
        
        data = request.get_json()
        image_id = data.get('image_id', '')
        top_k = data.get('top_k', 9)
        exclude_self = data.get('exclude_self', True)
        
        if not image_id:
            return jsonify({
                'success': False,
                'error': '图片ID不能为空'
            })
        
        system = init_retrieval_system()
        
        # 从ChromaDB中查找对应的图片路径
        try:
            collection = system.chromadb.collection
            
            results = collection.get(
                where={"id": int(image_id)},
                include=['metadatas']
            )
            
            if not results or not results['metadatas']:
                return jsonify({
                    'success': False,
                    'error': f'未找到ID为 {image_id} 的图片'
                })
            
            image_path = results['metadatas'][0].get('image_path', '')
            
            if not image_path or not os.path.exists(image_path):
                return jsonify({
                    'success': False,
                    'error': f'ID {image_id} 对应的图片文件不存在'
                })
            
            logger.info(f"基于ID {image_id} 执行相似图搜索: {os.path.basename(image_path)}")
            
            search_count = top_k + 1 if exclude_self else top_k
            similar_results = system.search_by_image(image_path, search_count)
            
            # 排除自身
            if exclude_self and similar_results:
                filtered_results = []
                for result in similar_results:
                    if str(result.get('id', '')) != str(image_id):
                        filtered_results.append(result)
                        if len(filtered_results) >= top_k:
                            break
                similar_results = filtered_results
            
            # 转换结果格式
            formatted_results = []
            for result in similar_results:
                formatted_result = format_search_result(result)
                formatted_results.append(formatted_result)
            
            return jsonify({
                'success': True,
                'data': {
                    'query_image_id': image_id,
                    'query_image': os.path.basename(image_path),
                    'query_path': image_path,
                    'results': formatted_results,
                    'search_type': 'similar_by_id',
                    'excluded_self': exclude_self
                }
            })
            
        except Exception as e:
            logger.error(f"查找图片ID {image_id} 失败: {e}")
            return jsonify({
                'success': False,
                'error': f'查找图片失败: {str(e)}'
            })
        
    except Exception as e:
        logger.error(f"基于ID的相似图搜索失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/get_image_info/<image_id>')
def get_image_info(image_id):
    """获取图片详细信息"""
    try:
        system = init_retrieval_system()
        
        # 从ChromaDB中查找图片信息
        collection = system.chromadb.collection
        results = collection.get(
            where={"id": int(image_id)},
            include=['metadatas', 'documents']
        )
        
        if not results or not results['metadatas']:
            return jsonify({
                'success': False,
                'error': f'未找到ID为 {image_id} 的图片'
            })
        
        metadata = results['metadatas'][0]
        document = results['documents'][0] if results['documents'] else ''
        
        # 构建图片信息
        image_info = {
            'id': metadata.get('id', ''),
            'filename': metadata.get('filename', ''),
            'image_path': metadata.get('image_path', ''),
            'original_url': metadata.get('original_url', ''),
            'display_tags': metadata.get('display_tags', ''),
            'combined_tags': metadata.get('combined_tags', ''),
            'clip_model': metadata.get('clip_model', ''),
            'created_at': metadata.get('created_at', ''),
            'document': document,
            'image_exists': os.path.exists(metadata.get('image_path', '')) if metadata.get('image_path') else False
        }
        
        # 添加图片base64编码
        image_path = metadata.get('image_path', '')
        if image_path and os.path.exists(image_path):
            image_info['image_base64'] = safe_image_to_jpeg_base64(image_path)
        
        return jsonify({
            'success': True,
            'data': image_info
        })
        
    except Exception as e:
        logger.error(f"获取图片信息失败: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })

def test_unsplash_connection():
    """测试Unsplash API连接"""
    if not UNSPLASH_ACCESS_KEY:
        logger.warning("未设置Unsplash API密钥")
        return False
    
    try:
        url = "https://api.unsplash.com/photos"
        headers = {
            'Authorization': f'Client-ID {UNSPLASH_ACCESS_KEY}',
            'Accept-Version': 'v1'
        }
        params = {'per_page': 1}
        
        response = requests.get(url, headers=headers, params=params, timeout=5)
        
        if response.status_code == 200:
            logger.info("✅ Unsplash API连接正常")
            return True
        elif response.status_code == 401:
            logger.error("❌ Unsplash API密钥无效")
            return False
        else:
            logger.error(f"❌ Unsplash API测试失败: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Unsplash API连接测试异常: {e}")
        return False

# 初始化Google翻译器
def translate_with_openrouter(text):
    """使用OpenRouter API进行翻译 - 改进版"""
    if not OPENROUTER_API_KEY:
        logger.warning("OpenRouter API密钥未设置")
        return text
    
    try:
        # 构建更精确的翻译提示词
        prompt = f"""请将以下中文文本翻译成英文，用于图片搜索。

要求：
1. 保持原文的标点符号和分隔符（特别是逗号）
2. 将中文词汇翻译为对应的英文词汇
3. 适合用于图片搜索的关键词
4. 只返回翻译后的英文文本，不要任何其他内容

中文文本：{text}

英文翻译："""

        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:9899",
            "X-Title": "Image Search Translation"
        }
        
        data = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "system", 
                    "content": "你是一个专业的中英文翻译助手，专门为图片搜索提供准确的翻译服务。你必须保持原文的标点符号和格式，将所有中文准确翻译为英文。"
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "temperature": 0.1,
            "max_tokens": 300,
            "stream": False
        }
        
        logger.info(f"OpenRouter翻译请求: {text}")
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            
            if 'choices' in result and len(result['choices']) > 0:
                translated_text = result['choices'][0]['message']['content'].strip()
                
                # 清理翻译结果
                translated_text = clean_translation_result(translated_text)
                
                if translated_text and translated_text != text:
                    logger.info(f"OpenRouter翻译成功: {text} -> {translated_text}")
                    return translated_text
                else:
                    logger.warning(f"OpenRouter翻译结果无效: {translated_text}")
                    return text
            else:
                logger.error(f"OpenRouter翻译响应格式错误: {result}")
                return text
        else:
            logger.error(f"OpenRouter翻译请求失败: {response.status_code} - {response.text}")
            return text
            
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenRouter翻译网络错误: {e}")
        return text
    except Exception as e:
        logger.error(f"OpenRouter翻译异常: {e}")
        return text

def clean_translation_result(text):
    """清理翻译结果"""
    if not text:
        return text
    
    # 移除常见的AI回复前缀
    prefixes_to_remove = [
        "英文翻译：",
        "翻译结果：", 
        "Translation:",
        "English:",
        "翻译：",
        "结果：",
        "答：",
        "A:",
        "Answer:",
        "英文："
    ]
    
    cleaned = text.strip()
    for prefix in prefixes_to_remove:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    
    # 移除引号
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1]
    if cleaned.startswith("'") and cleaned.endswith("'"):
        cleaned = cleaned[1:-1]
    
    # 保持原有的标点符号，只清理多余空格
    # 不要删除逗号等重要分隔符
    cleaned = ' '.join(cleaned.split())
    
    return cleaned

def has_chinese_text(text):
    """检查文本是否包含中文字符"""
    import re
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]+')
    return bool(chinese_pattern.search(text))

def translate_to_english(text):
    """主翻译函数 - 只使用OpenRouter"""
    try:
        # 预处理检查
        if not text or not text.strip():
            return text
        
        original_text = text.strip()
        
        # 如果不包含中文，直接返回
        if not has_chinese_text(original_text):
            logger.info(f"文本不包含中文，直接返回: {original_text}")
            return original_text
        
        # 检查是否有OpenRouter API密钥
        if not OPENROUTER_API_KEY:
            logger.error("OpenRouter API密钥未设置，无法翻译")
            return original_text
        
        max_attempts = 3
        current_text = original_text
        
        for attempt in range(max_attempts):
            logger.info(f"第 {attempt + 1} 次翻译尝试: {current_text}")
            
            # 使用OpenRouter翻译
            translated = translate_with_openrouter(current_text)
            
            if translated == current_text:
                logger.warning(f"第 {attempt + 1} 次翻译无变化，可能翻译失败")
                break
            
            logger.info(f"第 {attempt + 1} 次翻译结果: {translated}")
            
            # 检查翻译结果是否还包含中文
            if has_chinese_text(translated):
                logger.info(f"翻译结果仍包含中文，准备第 {attempt + 2} 次翻译")
                current_text = translated
                continue
            else:
                logger.info(f"翻译完成，无中文残留: {original_text} -> {translated}")
                return translated
        
        # 如果经过多次尝试仍有中文，返回最后的结果
        logger.warning(f"经过 {max_attempts} 次翻译，仍有中文残留: {current_text}")
        return current_text if current_text != original_text else original_text
        
    except Exception as e:
        logger.error(f"翻译主函数失败: {e}")
        return text

@app.route('/api/translate', methods=['POST'])
def translate_text():
    """翻译文本接口 - 纯OpenRouter版本"""
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({
                'success': False,
                'error': '翻译内容不能为空'
            })
        
        # 检查OpenRouter配置
        if not OPENROUTER_API_KEY:
            return jsonify({
                'success': False,
                'error': 'OpenRouter API密钥未配置，无法使用翻译功能'
            })
        
        # 记录翻译请求
        logger.info(f"收到翻译请求: '{text}'")
        
        # 执行翻译
        translated = translate_to_english(text)
        
        # 记录翻译结果
        logger.info(f"翻译完成: '{text}' -> '{translated}'")
        
        # 检查翻译是否成功（是否有变化且无中文残留）
        translation_success = (translated != text) and not has_chinese_text(translated)
        
        return jsonify({
            'success': True,
            'data': {
                'original': text,
                'translated': translated,
                'method': 'openrouter',
                'has_chinese_remaining': has_chinese_text(translated),
                'translation_successful': translation_success
            }
        })
        
    except Exception as e:
        logger.error(f"翻译接口失败: {e}")
        return jsonify({
            'success': False,
            'error': f'翻译服务异常: {str(e)}'
        })
        
        
# 在应用启动时测试连接和索引状态
if __name__ == '__main__':
    print("🚀 启动智能图片检索Web应用...")
    print(f"🤖 LLM功能: {'✅ 启用' if OPENROUTER_API_KEY else '❌ 未启用'}")
    print(f"🌐 Pexels: {'✅ 启用' if PEXELS_API_KEY else '❌ 未启用'}")
    
    if UNSPLASH_ACCESS_KEY:
        if test_unsplash_connection():
            print("🎨 Unsplash: ✅ 启用")
        else:
            print("🎨 Unsplash: ❌ 配置错误")
    else:
        print("🎨 Unsplash: ❌ 未启用")
    
    print(f"📍 访问地址: http://localhost:9899")
    print("💡 检索系统将在首次请求时自动初始化并智能检查索引状态")
    print("📊 如有数据更新，系统会智能提示是否重建索引")
    
    app.run(host='0.0.0.0', port=9899, debug=False)