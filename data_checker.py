#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
向量数据库与本地数据一致性检测工具 - 修复版
检测ChromaDB中的数据与MySQL、本地文件系统的一致性
"""

import os
import json
import pandas as pd
import pymysql
import chromadb
from typing import Dict, Set, List, Tuple
from datetime import datetime
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataConsistencyChecker:
    """数据一致性检测器 - 修复版"""
    
    def __init__(self):
        # MySQL配置
        self.db_config = {
            'host': '10.7.100.245',
            'user': 'root',
            'password': 'gempoll',
            'database': 'gempoll_tips',
            'port': 3306,
            'charset': 'utf8mb4'
        }
        
        # ChromaDB配置
        self.chromadb_host = "localhost"
        self.chromadb_port = 6600
        self.collection_name = "local_db_image_collection"
        
        # 路径配置
        self.image_path_prefix = "/home/ai/"
        
        # 数据存储
        self.mysql_data = {}
        self.chromadb_data = {}
        self.file_system_data = {}
        
        print("🚀 数据一致性检测器初始化完成")
    
    def connect_mysql(self) -> pymysql.Connection:
        """连接MySQL数据库"""
        try:
            connection = pymysql.connect(**self.db_config)
            logger.info("✅ MySQL连接成功")
            return connection
        except Exception as e:
            logger.error(f"❌ MySQL连接失败: {e}")
            raise
    
    def connect_chromadb(self):
        """连接ChromaDB"""
        try:
            client = chromadb.HttpClient(host=self.chromadb_host, port=self.chromadb_port)
            
            # 检查集合是否存在
            try:
                collection = client.get_collection(self.collection_name)
                logger.info("✅ ChromaDB连接成功，找到现有集合")
            except Exception:
                logger.warning("⚠️ ChromaDB集合不存在，尝试创建...")
                collection = client.create_collection(self.collection_name)
                logger.info("✅ ChromaDB集合创建成功")
            
            return client, collection
        except Exception as e:
            logger.error(f"❌ ChromaDB连接失败: {e}")
            raise
    
    def scan_mysql_data(self) -> Dict:
        """扫描MySQL数据"""
        print("\n📊 扫描MySQL数据...")
        
        connection = self.connect_mysql()
        
        try:
            sql = """
                SELECT id, image_url, ai_tags, tags
                FROM work_copy428 
                WHERE image_url IS NOT NULL AND image_url != ''
                AND (ai_tags IS NOT NULL OR tags IS NOT NULL)
                ORDER BY id
            """
            
            with connection.cursor() as cursor:
                cursor.execute(sql)
                results = cursor.fetchall()
            
            # 处理数据
            mysql_records = {}
            valid_files = 0
            invalid_files = 0
            
            print(f"   处理 {len(results)} 条MySQL记录...")
            
            for i, record in enumerate(results):
                if i % 10000 == 0:
                    print(f"   进度: {i}/{len(results)}")
                    
                record_id, image_url, ai_tags, tags = record
                
                # 构建完整路径
                filename = os.path.basename(image_url)
                
                # 尝试多种路径构建方式
                possible_paths = [
                    os.path.join(self.image_path_prefix, image_url.lstrip('/')),
                    image_url.replace('/scraper_data/', f'{self.image_path_prefix}scraper_data/'),
                ]
                
                # 检查文件是否存在
                file_exists = False
                actual_path = None
                for path in possible_paths:
                    if os.path.exists(path):
                        file_exists = True
                        actual_path = path
                        break
                
                if file_exists:
                    valid_files += 1
                else:
                    invalid_files += 1
                    # 如果文件不存在，使用第一个可能的路径
                    actual_path = possible_paths[0]
                
                mysql_records[record_id] = {
                    'id': record_id,
                    'image_url': image_url,
                    'filename': filename,
                    'full_path': actual_path,
                    'file_exists': file_exists,
                    'ai_tags': ai_tags,
                    'tags': tags,
                    'has_tags': bool((ai_tags and str(ai_tags).strip()) or (tags and str(tags).strip()))
                }
            
            self.mysql_data = {
                'records': mysql_records,
                'total_count': len(mysql_records),
                'valid_files': valid_files,
                'invalid_files': invalid_files,
                'id_range': (min(mysql_records.keys()), max(mysql_records.keys())) if mysql_records else (0, 0)
            }
            
            print(f"   📈 MySQL统计:")
            print(f"      总记录: {self.mysql_data['total_count']:,}")
            print(f"      文件存在: {valid_files:,}")
            print(f"      文件缺失: {invalid_files:,}")
            print(f"      ID范围: {self.mysql_data['id_range']}")
            
            return self.mysql_data
            
        finally:
            connection.close()
    
    def scan_chromadb_data(self) -> Dict:
        """扫描ChromaDB数据 - 修复版"""
        print("\n🗄️ 扫描ChromaDB数据...")
        
        try:
            client, collection = self.connect_chromadb()
        except Exception as e:
            print(f"   ❌ ChromaDB连接失败: {e}")
            # 返回空数据结构
            self.chromadb_data = {
                'records': {},
                'total_count': 0,
                'valid_files': 0,
                'invalid_files': 0,
                'id_range': (0, 0),
                'error': str(e)
            }
            return self.chromadb_data
        
        try:
            total_count = collection.count()
            print(f"   ChromaDB总记录: {total_count:,}")
            
            if total_count == 0:
                print("   ⚠️ ChromaDB为空，没有任何数据!")
                self.chromadb_data = {
                    'records': {},
                    'total_count': 0,
                    'valid_files': 0,
                    'invalid_files': 0,
                    'id_range': (0, 0)
                }
                return self.chromadb_data
            
            # 分批获取所有数据
            chromadb_records = {}
            batch_size = 5000
            processed = 0
            valid_files = 0
            invalid_files = 0
            
            while processed < total_count:
                try:
                    results = collection.get(
                        limit=batch_size,
                        offset=processed,
                        include=['metadatas']
                    )
                    
                    if not results or not results.get('metadatas'):
                        break
                    
                    batch_count = len(results['metadatas'])
                    print(f"   处理批次: {processed + 1}-{processed + batch_count}/{total_count}")
                    
                    for i, metadata in enumerate(results['metadatas']):
                        try:
                            record_id = int(metadata.get('id', 0))
                            image_path = metadata.get('image_path', '')
                            file_exists_flag = os.path.exists(image_path) if image_path else False
                            
                            if file_exists_flag:
                                valid_files += 1
                            else:
                                invalid_files += 1
                            
                            if record_id > 0:
                                chromadb_records[record_id] = {
                                    'id': record_id,
                                    'vector_id': results['ids'][i],
                                    'image_path': image_path,
                                    'filename': metadata.get('filename', ''),
                                    'original_url': metadata.get('original_url', ''),
                                    'combined_tags': metadata.get('combined_tags', ''),
                                    'created_at': metadata.get('created_at', ''),
                                    'file_exists': file_exists_flag
                                }
                        except (ValueError, TypeError) as e:
                            logger.warning(f"无效记录: {metadata}")
                    
                    processed += batch_count
                    
                    if batch_count < batch_size:
                        break
                        
                except Exception as e:
                    logger.error(f"获取批次失败: {e}")
                    processed += batch_size
                    continue
            
            self.chromadb_data = {
                'records': chromadb_records,
                'total_count': len(chromadb_records),
                'valid_files': valid_files,
                'invalid_files': invalid_files,
                'id_range': (min(chromadb_records.keys()), max(chromadb_records.keys())) if chromadb_records else (0, 0)
            }
            
            print(f"   📈 ChromaDB统计:")
            print(f"      总记录: {self.chromadb_data['total_count']:,}")
            print(f"      文件存在: {valid_files:,}")
            print(f"      文件缺失: {invalid_files:,}")
            if chromadb_records:
                print(f"      ID范围: {self.chromadb_data['id_range']}")
            
            return self.chromadb_data
            
        except Exception as e:
            logger.error(f"扫描ChromaDB失败: {e}")
            # 返回空数据但不抛异常
            self.chromadb_data = {
                'records': {},
                'total_count': 0,
                'valid_files': 0,
                'invalid_files': 0,
                'id_range': (0, 0),
                'error': str(e)
            }
            return self.chromadb_data
    
    def scan_file_system(self) -> Dict:
        """扫描文件系统"""
        print("\n📁 扫描文件系统...")
        
        scraper_base = f'{self.image_path_prefix}scraper_data/'
        
        if not os.path.exists(scraper_base):
            print(f"   ❌ 路径不存在: {scraper_base}")
            self.file_system_data = {'files': {}, 'total_count': 0, 'brands': {}}
            return self.file_system_data
        
        file_mapping = {}
        total_files = 0
        brand_stats = {}
        
        print(f"   扫描路径: {scraper_base}")
        
        for brand_dir in os.listdir(scraper_base):
            brand_path = os.path.join(scraper_base, brand_dir)
            if os.path.isdir(brand_path):
                try:
                    brand_files = 0
                    for filename in os.listdir(brand_path):
                        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                            full_path = os.path.join(brand_path, filename)
                            file_mapping[filename] = {
                                'full_path': full_path,
                                'brand': brand_dir,
                                'size': os.path.getsize(full_path)
                            }
                            brand_files += 1
                            total_files += 1
                    
                    brand_stats[brand_dir] = brand_files
                    if brand_files > 0:
                        print(f"      {brand_dir}: {brand_files:,} 个文件")
                        
                except Exception as e:
                    logger.warning(f"读取目录 {brand_dir} 失败: {e}")
        
        self.file_system_data = {
            'files': file_mapping,
            'total_count': total_files,
            'brands': brand_stats
        }
        
        print(f"   📈 文件系统统计:")
        print(f"      总文件: {total_files:,}")
        print(f"      品牌数: {len(brand_stats)}")
        
        return self.file_system_data
    
    def analyze_consistency(self) -> Dict:
        """分析数据一致性 - 修复版"""
        print("\n🔍 分析数据一致性...")
        
        mysql_ids = set(self.mysql_data.get('records', {}).keys())
        chromadb_ids = set(self.chromadb_data.get('records', {}).keys())
        
        # ID层面的对比
        missing_in_chromadb = mysql_ids - chromadb_ids
        extra_in_chromadb = chromadb_ids - mysql_ids
        common_ids = mysql_ids & chromadb_ids
        
        print(f"\n📊 ID层面对比:")
        print(f"   MySQL总ID: {len(mysql_ids):,}")
        print(f"   ChromaDB总ID: {len(chromadb_ids):,}")
        print(f"   共同ID: {len(common_ids):,}")
        print(f"   ChromaDB缺失: {len(missing_in_chromadb):,}")
        print(f"   ChromaDB多余: {len(extra_in_chromadb):,}")
        
        # 安全获取valid_files，避免KeyError
        mysql_valid_files = self.mysql_data.get('valid_files', 0)
        chromadb_valid_files = self.chromadb_data.get('valid_files', 0)
        
        print(f"\n📁 文件存在性对比:")
        print(f"   MySQL有效文件: {mysql_valid_files:,}")
        print(f"   ChromaDB有效文件: {chromadb_valid_files:,}")
        
        # 检查共同ID的数据一致性（如果有共同ID）
        inconsistent_records = []
        if common_ids:
            sample_size = min(100, len(common_ids))
            for common_id in list(common_ids)[:sample_size]:
                mysql_record = self.mysql_data['records'][common_id]
                chromadb_record = self.chromadb_data['records'][common_id]
                
                issues = []
                if mysql_record['filename'] != chromadb_record['filename']:
                    issues.append('filename_mismatch')
                if mysql_record['file_exists'] != chromadb_record['file_exists']:
                    issues.append('file_existence_mismatch')
                
                if issues:
                    inconsistent_records.append({
                        'id': common_id,
                        'issues': issues,
                        'mysql': mysql_record,
                        'chromadb': chromadb_record
                    })
        
        # 特殊情况检测
        special_cases = []
        if len(chromadb_ids) == 0:
            special_cases.append("ChromaDB完全为空 - 需要初始化数据")
        elif len(missing_in_chromadb) > len(chromadb_ids):
            special_cases.append("ChromaDB数据严重缺失 - 建议重建索引")
        elif len(extra_in_chromadb) > len(mysql_ids) * 0.1:
            special_cases.append("ChromaDB包含大量过期数据")
        
        # 生成详细报告
        analysis_result = {
            'timestamp': datetime.now().isoformat(),
            'mysql_stats': self.mysql_data,
            'chromadb_stats': self.chromadb_data,
            'file_system_stats': self.file_system_data,
            'consistency': {
                'mysql_ids': len(mysql_ids),
                'chromadb_ids': len(chromadb_ids),
                'common_ids': len(common_ids),
                'missing_in_chromadb': len(missing_in_chromadb),
                'extra_in_chromadb': len(extra_in_chromadb),
                'consistency_rate': (len(common_ids) / max(len(mysql_ids), 1)) * 100,
                'missing_ids_sample': sorted(list(missing_in_chromadb))[:20],
                'extra_ids_sample': sorted(list(extra_in_chromadb))[:20],
                'inconsistent_records': len(inconsistent_records),
                'special_cases': special_cases,
                'file_consistency': {
                    'mysql_valid': mysql_valid_files,
                    'chromadb_valid': chromadb_valid_files,
                    'file_system_total': self.file_system_data.get('total_count', 0)
                }
            }
        }
        
        return analysis_result
    
    def print_detailed_report(self, analysis: Dict):
        """打印详细报告"""
        print("\n" + "=" * 80)
        print("📋 数据一致性详细报告")
        print("=" * 80)
        
        consistency = analysis['consistency']
        
        print(f"\n🎯 总体概况:")
        print(f"   检测时间: {analysis['timestamp']}")
        print(f"   数据一致性: {consistency['consistency_rate']:.2f}%")
        
        # 特殊情况提醒
        if consistency['special_cases']:
            print(f"\n⚠️ 特殊情况:")
            for case in consistency['special_cases']:
                print(f"   🔴 {case}")
        
        print(f"\n📊 数据量统计:")
        print(f"   MySQL记录: {consistency['mysql_ids']:,}")
        print(f"   ChromaDB记录: {consistency['chromadb_ids']:,}")
        print(f"   本地文件: {consistency['file_consistency']['file_system_total']:,}")
        print(f"   共同记录: {consistency['common_ids']:,}")
        
        print(f"\n⚠️ 不一致问题:")
        print(f"   ChromaDB缺失记录: {consistency['missing_in_chromadb']:,}")
        print(f"   ChromaDB多余记录: {consistency['extra_in_chromadb']:,}")
        
        if consistency['missing_in_chromadb'] > 0:
            print(f"\n🔍 缺失ID示例 (前20个):")
            mysql_records = self.mysql_data.get('records', {})
            for missing_id in consistency['missing_ids_sample']:
                mysql_record = mysql_records.get(missing_id, {})
                file_status = "✅" if mysql_record.get('file_exists') else "❌"
                print(f"      ID {missing_id}: {mysql_record.get('filename', 'unknown')} {file_status}")
        
        if consistency['extra_in_chromadb'] > 0:
            print(f"\n🔍 多余ID示例 (前20个):")
            chromadb_records = self.chromadb_data.get('records', {})
            for extra_id in consistency['extra_ids_sample']:
                chromadb_record = chromadb_records.get(extra_id, {})
                print(f"      ID {extra_id}: {chromadb_record.get('filename', 'unknown')}")
        
        print(f"\n📁 文件状态:")
        print(f"   MySQL中有效文件: {consistency['file_consistency']['mysql_valid']:,}")
        print(f"   ChromaDB中有效文件: {consistency['file_consistency']['chromadb_valid']:,}")
        print(f"   文件系统总文件: {consistency['file_consistency']['file_system_total']:,}")
        
        print("\n" + "=" * 80)
    
    def export_report(self, analysis: Dict, filename: str = None):
        """导出报告到文件"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data_consistency_report_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
            
            print(f"\n💾 报告已导出: {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"导出报告失败: {e}")
            return None
    
    def generate_fix_suggestions(self, analysis: Dict) -> List[str]:
        """生成修复建议 - 增强版"""
        suggestions = []
        consistency = analysis['consistency']
        
        # 针对ChromaDB为空的特殊情况
        if consistency['chromadb_ids'] == 0:
            suggestions.append("🚨 紧急: ChromaDB完全为空!")
            suggestions.append("   原因可能:")
            suggestions.append("     • ChromaDB容器重启导致数据丢失")
            suggestions.append("     • 数据卷挂载配置问题")
            suggestions.append("     • 集合被意外删除")
            suggestions.append("   立即执行:")
            suggestions.append("     1. 检查ChromaDB容器状态: docker ps | grep chroma")
            suggestions.append("     2. 检查数据卷挂载: docker inspect <container> | grep Mounts")
            suggestions.append("     3. 运行主程序重建完整索引")
            
        elif consistency['missing_in_chromadb'] > 0:
            suggestions.append(f"建议1: ChromaDB缺失 {consistency['missing_in_chromadb']:,} 条记录，需要执行增量更新")
            suggestions.append(f"   命令: 运行主程序选择 '修复缺失数据' 功能")
        
        if consistency['extra_in_chromadb'] > 0:
            suggestions.append(f"建议2: ChromaDB多出 {consistency['extra_in_chromadb']:,} 条记录，可能是过期数据")
            suggestions.append(f"   建议: 检查MySQL是否删除了某些记录")
        
        mysql_valid = consistency['file_consistency']['mysql_valid']
        chromadb_valid = consistency['file_consistency']['chromadb_valid']
        file_system_total = consistency['file_consistency']['file_system_total']
        
        if mysql_valid != file_system_total:
            suggestions.append(f"建议3: MySQL有效文件数({mysql_valid:,})与文件系统总数({file_system_total:,})不匹配")
            suggestions.append(f"   可能原因: 文件路径解析问题或文件被移动/删除")
        
        if consistency['consistency_rate'] < 95:
            suggestions.append(f"建议4: 数据一致性较低 ({consistency['consistency_rate']:.1f}%)")
            if consistency['chromadb_ids'] == 0:
                suggestions.append(f"   操作: 重建完整ChromaDB索引")
            else:
                suggestions.append(f"   操作: 执行增量更新或重建索引")
        
        return suggestions
    
    def run_full_check(self):
        """运行完整检测"""
        print("🚀 开始完整数据一致性检测...")
        start_time = datetime.now()
        
        try:
            # 扫描各数据源
            self.scan_mysql_data()
            self.scan_chromadb_data()
            self.scan_file_system()
            
            # 分析一致性
            analysis = self.analyze_consistency()
            
            # 打印报告
            self.print_detailed_report(analysis)
            
            # 生成修复建议
            suggestions = self.generate_fix_suggestions(analysis)
            if suggestions:
                print(f"\n💡 修复建议:")
                for suggestion in suggestions:
                    print(f"   {suggestion}")
            
            # 导出报告
            report_file = self.export_report(analysis)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"\n✅ 检测完成，耗时: {duration:.2f}秒")
            
            return analysis
            
        except Exception as e:
            logger.error(f"检测失败: {e}")
            raise

def main():
    """主函数"""
    print("=" * 80)
    print("🔍 向量数据库与本地数据一致性检测工具 v2.0")
    print("=" * 80)
    
    try:
        checker = DataConsistencyChecker()
        analysis = checker.run_full_check()
        
        # 交互选项
        while True:
            print(f"\n📋 后续操作:")
            print("1. 重新检测")
            print("2. 导出详细报告")
            print("3. 检查特定ID")
            print("4. 查看ChromaDB容器状态")
            print("5. 退出")
            
            choice = input("请选择操作: ").strip()
            
            if choice == '1':
                analysis = checker.run_full_check()
                
            elif choice == '2':
                filename = input("输入文件名 (回车使用默认): ").strip()
                checker.export_report(analysis, filename if filename else None)
                
            elif choice == '3':
                id_input = input("输入要检查的ID: ").strip()
                try:
                    check_id = int(id_input)
                    
                    mysql_info = checker.mysql_data.get('records', {}).get(check_id, "不存在")
                    chromadb_info = checker.chromadb_data.get('records', {}).get(check_id, "不存在")
                    
                    print(f"\nID {check_id} 检查结果:")
                    print(f"MySQL: {mysql_info}")
                    print(f"ChromaDB: {chromadb_info}")
                    
                except ValueError:
                    print("请输入有效的数字ID")
            
            elif choice == '4':
                print("\n🐳 ChromaDB容器检查:")
                print("请在终端运行以下命令:")
                print("  docker ps | grep chroma")
                print("  docker logs <chromadb_container_name>")
                print("  docker inspect <chromadb_container_name> | grep -A 5 Mounts")
                    
            elif choice == '5':
                break
            else:
                print("无效选择")
        
    except KeyboardInterrupt:
        print("\n\n👋 检测被用户中断")
    except Exception as e:
        print(f"\n❌ 检测失败: {e}")
        logger.exception("检测过程出错")

if __name__ == "__main__":
    main()