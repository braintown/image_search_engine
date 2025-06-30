def diagnose_file_structure():
    """详细诊断文件结构"""
    import os
    from pathlib import Path
    
    base_path = "/home/ai/"
    scraper_path = os.path.join(base_path, "scraper_data")
    
    print("🔍 详细文件结构分析...")
    print(f"基础路径: {base_path}")
    print(f"scraper_data路径: {scraper_path}")
    
    if os.path.exists(scraper_path):
        print(f"\n📁 scraper_data目录内容:")
        try:
            subdirs = []
            file_count = 0
            
            for item in os.listdir(scraper_path):
                item_path = os.path.join(scraper_path, item)
                if os.path.isdir(item_path):
                    subdirs.append(item)
                    # 统计每个子目录的文件数量
                    try:
                        files = [f for f in os.listdir(item_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
                        file_count += len(files)
                        print(f"   📂 {item}/ ({len(files)} 个图片文件)")
                        
                        if len(files) > 0:
                            # 显示几个文件示例
                            print(f"      示例文件: {files[:3]}")
                    except PermissionError:
                        print(f"   📂 {item}/ (权限拒绝)")
                    except Exception as e:
                        print(f"   📂 {item}/ (错误: {e})")
            
            print(f"\n📊 统计:")
            print(f"   子目录总数: {len(subdirs)}")
            print(f"   图片文件总数: {file_count}")
            print(f"   目录列表: {subdirs}")
            
            # 检查数据库中的目录是否存在
            print(f"\n🔍 检查数据库中提到的目录:")
            db_dirs = ['cherytiggo2', 'cherytiggo4']  # 从数据库样例中看到的
            for db_dir in db_dirs:
                db_dir_path = os.path.join(scraper_path, db_dir)
                exists = os.path.exists(db_dir_path)
                print(f"   {db_dir}: {'✅ 存在' if exists else '❌ 不存在'}")
                
                if exists:
                    try:
                        files = [f for f in os.listdir(db_dir_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
                        print(f"      包含 {len(files)} 个图片文件")
                    except:
                        print(f"      无法读取文件列表")
            
        except Exception as e:
            print(f"❌ 读取目录失败: {e}")
    else:
        print(f"❌ scraper_data目录不存在: {scraper_path}")

if __name__ == "__main__":
    # 运行诊断
    diagnose_file_structure()
