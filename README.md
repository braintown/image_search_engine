# 代码文件作用解释：

## 主代码
### 核心代码
main.py
- 数据库连接与存储
- 图像嵌入与检索
- 相似图像检索

### 后端代码
app.py 
- 主文件，负责启动Flask应用，处理用户请求并返回响应。
- 包含路由定义、HTML模板渲染、数据库交互等核心功能。

### 前端展示
static/app.js 
- 前端JavaScript代码，处理用户界面交互，包括搜索框输入、相似图像展示等。
- 与后端API进行通信，实现搜索功能。

### 页面模板
templates/index.html 

### 启动项目
- 确保已安装Flask、OpenAI CLIP、Pexels API等依赖。
- 设置环境变量，包括Pexels API Key、Unsplash Access Key等。
- 运行`uv run start.py`启动后端服务。
- 运行前会自动检查映射数据库的数据完整性
- 访问`http://localhost:9899`，即可使用图像搜索功能。

## 环境变量配置
- export PEXELS_API_KEY="你的Pexels API Key"
- export UNSPLASH_ACCESS_KEY="你的Unsplash Access Key"
- export OPENROUTER_API_KEY="你的OpenRouter API Key"
- export PIXABAY_API_KEY="你的Pixabay API Key"

## 其余代码
data_checker.py
- 用于检查SQL和向量数据库的数据差异，并检查文件夹的实际文件内容是否与数据库中的记录一致。
- 确保数据库中的图像路径与实际文件系统中的路径一致。

file_checker.py
- 用于检查文件夹中的文件是否存在于数据库中，但数据库中没有对应的记录。
- 确保数据库中的图像路径与实际文件系统中的路径一致。






