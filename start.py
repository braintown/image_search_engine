#!/usr/bin/env python3
"""
Web应用启动脚本
"""
import os
import sys

def main():
    print("🎨 智能图片检索Web系统启动器")
    print("=" * 50)
    
    # 配置API密钥
    print("请配置系统参数：")
    
    # OpenRouter配置
    use_openrouter = input("启用LLM智能搜索? (y/n): ").lower() == 'y'
    if use_openrouter:
        api_key = input("请输入OpenRouter API Key (留空跳过): ").strip()
        if api_key:
            os.environ['OPENROUTER_API_KEY'] = api_key
            
            models = [
                "anthropic/claude-3-sonnet",
                "openai/gpt-4o-mini", 
                "meta-llama/llama-3.1-8b-instruct"
            ]
            
            print("\n选择LLM模型:")
            for i, model in enumerate(models, 1):
                print(f"{i}. {model}")
            
            choice = input("选择模型 (默认: 1): ").strip()
            try:
                model_index = int(choice) - 1 if choice else 0
                os.environ['OPENROUTER_MODEL'] = models[model_index]
            except:
                os.environ['OPENROUTER_MODEL'] = "anthropic/claude-3-sonnet"
        else:
            print("⚠️ 未提供API密钥，LLM功能将被禁用")
    
    # 外部图片源配置
    print("\n🌐 外部图片源配置:")
    
    # Pexels配置
    use_pexels = input("启用Pexels图片源? (y/n): ").lower() == 'y'
    if use_pexels:
        pexels_key = input("请输入Pexels API Key (留空跳过): ").strip()
        if pexels_key:
            os.environ['PEXELS_API_KEY'] = pexels_key
            print("✅ Pexels配置完成")
        else:
            print("⚠️ 跳过Pexels配置")
    
    # Unsplash配置  
    use_unsplash = input("启用Unsplash图片源? (y/n): ").lower() == 'y'
    if use_unsplash:
        unsplash_key = input("请输入Unsplash Access Key (留空跳过): ").strip()
        if unsplash_key:
            os.environ['UNSPLASH_ACCESS_KEY'] = unsplash_key
            print("✅ Unsplash配置完成")
        else:
            print("⚠️ 跳过Unsplash配置")
    
    # Pixabay配置
    use_pixabay = input("启用Pixabay图片源? (y/n): ").lower() == 'y'
    if use_pixabay:
        pixabay_key = input("请输入Pixabay API Key (留空跳过): ").strip()
        if pixabay_key:
            os.environ['PIXABAY_API_KEY'] = pixabay_key
            print("✅ Pixabay配置完成")
        else:
            print("⚠️ 跳过Pixabay配置")

    # Picsum是免费的，无需配置
    # print("✅ Picsum (Lorem Picsum) 自动启用 - 无需API密钥")
    # CLIP模型配置
    clip_models = ["ViT-B/32", "ViT-B/16", "ViT-L/14", "RN50"]
    print("\n选择CLIP模型:")
    for i, model in enumerate(clip_models, 1):
        print(f"{i}. {model}")
    
    choice = input("选择模型 (默认: 1): ").strip()
    try:
        model_index = int(choice) - 1 if choice else 0
        os.environ['CLIP_MODEL'] = clip_models[model_index]
    except:
        os.environ['CLIP_MODEL'] = "ViT-B/32"
    
    print("\n🚀 启动Web服务...")
    print("📍 访问地址: http://localhost:9899")
    print("💡 功能说明:")
    print("  - 智能搜索: 基于本地数据库的AI理解搜索")
    print("  - 基础搜索: 基于本地数据库的关键词搜索")
    print("  - AI图片源: 从Pexels/Unsplash搜索高质量图片")
    print("  - 以图搜图: 基于图像相似度的搜索")
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    
    # 启动Flask应用
    try:
        from app import app
        app.run(host='0.0.0.0', port=9899, debug=False)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == '__main__':
    main()