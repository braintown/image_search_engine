class FullscreenImageViewer {
    constructor() {
        this.viewer = null;
        this.image = null;
        this.container = null;
        this.scale = 1;
        this.translateX = 0;
        this.translateY = 0;
        this.isDragging = false;
        this.startX = 0;
        this.startY = 0;
        this.currentImageData = null;
        
        this.init();
    }
    
    init() {
        this.viewer = document.getElementById('fullscreenImageViewer');
        this.image = document.getElementById('fullscreenImage');
        this.container = document.getElementById('imageContainer');
        
        // 移除这行循环初始化的代码！
        // this.fullscreenViewer = new FullscreenImageViewer();
        
        if (!this.viewer || !this.image || !this.container) {
            console.error('全屏图片查看器元素未找到');
            return;
        }
        
        this.bindEvents();
    }
    
    bindEvents() {
        // 关闭按钮
        const closeBtn = document.getElementById('closeFullscreen');
        if (closeBtn) closeBtn.addEventListener('click', () => this.close());
        
        // 工具栏按钮
        const zoomInBtn = document.getElementById('zoomIn');
        const zoomOutBtn = document.getElementById('zoomOut');
        const resetZoomBtn = document.getElementById('resetZoom');
        const downloadBtn = document.getElementById('downloadFullscreen');
        
        if (zoomInBtn) zoomInBtn.addEventListener('click', () => this.zoomIn());
        if (zoomOutBtn) zoomOutBtn.addEventListener('click', () => this.zoomOut());
        if (resetZoomBtn) resetZoomBtn.addEventListener('click', () => this.resetZoom());
        if (downloadBtn) downloadBtn.addEventListener('click', () => this.downloadImage());
        
        // 键盘事件
        document.addEventListener('keydown', (e) => {
            if (!this.viewer || this.viewer.classList.contains('hidden')) return;
            
            switch(e.key) {
                case 'Escape':
                    this.close();
                    break;
                case '+':
                case '=':
                    this.zoomIn();
                    break;
                case '-':
                    this.zoomOut();
                    break;
                case '0':
                    this.resetZoom();
                    break;
            }
        });
        
        // 鼠标滚轮缩放
        this.container.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? -0.1 : 0.1;
            this.zoom(delta);
        });
        
        // 拖拽功能
        this.container.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return; // 只处理左键
            this.startDrag(e.clientX, e.clientY);
        });
        
        document.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                this.drag(e.clientX, e.clientY);
            }
        });
        
        document.addEventListener('mouseup', () => {
            this.endDrag();
        });
        
        // 双击重置缩放
        this.image.addEventListener('dblclick', () => {
            this.resetZoom();
        });
        
        // 点击背景关闭
        this.viewer.addEventListener('click', (e) => {
            if (e.target === this.viewer) {
                this.close();
            }
        });
    }
    
    show(imageSrc, imageData = null) {
        console.log('全屏查看器显示图片:', imageSrc);
        this.currentImageData = imageData;
        this.image.src = imageSrc;
        this.viewer.classList.remove('hidden');
        
        // 重置状态
        this.resetZoom();
        
        // 更新图片信息
        this.updateImageInfo();
        
        // 图片加载完成后适配大小
        this.image.onload = () => {
            this.fitToScreen();
        };
        
        // 禁止页面滚动
        document.body.style.overflow = 'hidden';
    }
    
    close() {
        this.viewer.classList.add('hidden');
        document.body.style.overflow = 'auto';
        this.currentImageData = null;
    }
    
    updateImageInfo() {
        const fileNameEl = document.getElementById('imageFileName');
        const dimensionsEl = document.getElementById('imageDimensions');
        
        if (this.currentImageData) {
            if (fileNameEl) fileNameEl.textContent = this.currentImageData.filename || this.currentImageData.title || '未知文件';
            if (dimensionsEl) dimensionsEl.textContent = this.currentImageData.id ? `ID: ${this.currentImageData.id}` : '';
        } else {
            if (fileNameEl) fileNameEl.textContent = '图片预览';
            if (dimensionsEl) dimensionsEl.textContent = '';
        }
    }
    
    fitToScreen() {
        const containerRect = this.container.getBoundingClientRect();
        
        const scaleX = (containerRect.width * 0.9) / this.image.naturalWidth;
        const scaleY = (containerRect.height * 0.9) / this.image.naturalHeight;
        
        this.scale = Math.min(scaleX, scaleY, 1); // 不超过原始大小
        this.translateX = 0;
        this.translateY = 0;
        
        this.updateTransform();
    }
    
    zoom(delta) {
        const newScale = Math.min(Math.max(this.scale + delta, 0.1), 5);
        if (newScale !== this.scale) {
            this.scale = newScale;
            this.updateTransform();
        }
    }
    
    zoomIn() {
        this.zoom(0.2);
    }
    
    zoomOut() {
        this.zoom(-0.2);
    }
    
    resetZoom() {
        this.fitToScreen();
    }
    
    startDrag(x, y) {
        if (this.scale <= 1) return; // 只有放大时才允许拖拽
        
        this.isDragging = true;
        this.startX = x - this.translateX;
        this.startY = y - this.translateY;
        this.container.style.cursor = 'grabbing';
    }
    
    drag(x, y) {
        if (!this.isDragging) return;
        
        this.translateX = x - this.startX;
        this.translateY = y - this.startY;
        
        this.updateTransform();
    }
    
    endDrag() {
        this.isDragging = false;
        this.container.style.cursor = this.scale > 1 ? 'grab' : 'default';
    }
    
    updateTransform() {
        const transform = `translate(-50%, -50%) translate(${this.translateX}px, ${this.translateY}px) scale(${this.scale})`;
        this.image.style.transform = transform;
        
        // 更新缩放比例显示
        const zoomLevelEl = document.getElementById('zoomLevel');
        if (zoomLevelEl) {
            zoomLevelEl.textContent = `${Math.round(this.scale * 100)}%`;
        }
        
        // 更新光标
        this.container.style.cursor = this.scale > 1 ? 'grab' : 'default';
    }
    
    downloadImage() {
        if (this.currentImageData) {
            // 调用已有的下载功能
            app.downloadImageByData(this.currentImageData);
        }
    }
}


class ImageSearchApp {
    constructor() {
        this.currentSearchType = 'intelligent';
        this.systemInfo = null;
        this.currentResults = [];
        this.currentModalImageData = null;
        this.currentPage = 1;
        this.selectedTags = [];
        this.fullscreenViewer = null; // 添加这个属性
        this.init();
    }

    async init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.bindEvents();
                this.loadSystemInfo();
                this.initAnimations();
                this.initFullscreenViewer(); // 添加全屏查看器初始化
            });
        } else {
            this.bindEvents();
            await this.loadSystemInfo();
            this.initAnimations();
            this.initFullscreenViewer(); // 添加全屏查看器初始化
        }
    }

    // 新增方法：初始化全屏查看器
    initFullscreenViewer() {
        // 等待DOM元素加载完成
        setTimeout(() => {
            this.fullscreenViewer = new FullscreenImageViewer();
            console.log('全屏图片查看器已初始化');
        }, 100);
    }

    initAnimations() {
        // 添加页面加载动画
        const animatedElements = document.querySelectorAll('.animate-fade-in-up');
        animatedElements.forEach(element => {
            element.style.opacity = '0';
            element.style.transform = 'translateY(30px)';
        });

        // 逐个显示动画元素
        setTimeout(() => {
            animatedElements.forEach((element, index) => {
                setTimeout(() => {
                    element.style.transition = 'all 0.6s ease-out';
                    element.style.opacity = '1';
                    element.style.transform = 'translateY(0)';
                }, index * 100);
            });
        }, 100);
    }

    bindEvents() {
        console.log('开始绑定事件...');
        this.bindKeyboardEvents();
        this.bindTagEvents();
        this.bindAIInputEvents();

        // 标签页切换
        const tabIntelligent = document.getElementById('tabIntelligent');
        const tabBasic = document.getElementById('tabBasic');
        const tabAI = document.getElementById('tabAI');
        const tabImage = document.getElementById('tabImage');

        if (tabIntelligent) tabIntelligent.addEventListener('click', () => this.switchTab('intelligent'));
        if (tabBasic) tabBasic.addEventListener('click', () => this.switchTab('basic'));
        if (tabAI) tabAI.addEventListener('click', () => this.switchTab('ai'));
        if (tabImage) tabImage.addEventListener('click', () => this.switchTab('image'));

        // 文本搜索
        const textSearchBtn = document.getElementById('textSearchBtn');
        const searchInput = document.getElementById('searchInput');
        if (textSearchBtn) textSearchBtn.addEventListener('click', () => this.performTextSearch());
        if (searchInput) {
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.performTextSearch();
            });
        }

        // AI搜索
        const aiSearchBtn = document.getElementById('aiSearchBtn');
        const aiSearchInput = document.getElementById('aiSearchInput');
        if (aiSearchBtn) aiSearchBtn.addEventListener('click', () => this.performAISearch());
        if (aiSearchInput) {
            aiSearchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') this.performAISearch();
            });
        }

        // 图片上传
        const uploadArea = document.getElementById('uploadArea');
        const imageInput = document.getElementById('imageInput');
        const imageSearchBtn = document.getElementById('imageSearchBtn');
        const removeImageBtn = document.getElementById('removeImageBtn'); // 新增
        const reSelectImageBtn = document.getElementById('reSelectImageBtn'); // 新增

        if (uploadArea && imageInput) {
            uploadArea.addEventListener('click', () => {
                imageInput.click();
            });
            
            imageInput.addEventListener('change', (e) => {
                this.handleImageUpload(e.target.files[0]);
            });
        }

        if (imageSearchBtn) {
            imageSearchBtn.addEventListener('click', () => this.performImageSearch());
        }
        
        if (removeImageBtn) {
        removeImageBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.removeUploadedImage();
        });
        }

        if (reSelectImageBtn) {
        reSelectImageBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.reSelectImage();
        });
        }

        // 拖拽上传
        if (uploadArea) {
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.classList.add('border-blue-500', 'bg-blue-50');
            });

            uploadArea.addEventListener('dragleave', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('border-blue-500', 'bg-blue-50');
            });

            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.classList.remove('border-blue-500', 'bg-blue-50');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    this.handleImageUpload(files[0]);
                }
            });
        }

        // 模态框事件
        this.bindModalEvents();

        // 批量下载
        const downloadAllBtn = document.getElementById('downloadAllBtn');
        if (downloadAllBtn) {
            downloadAllBtn.addEventListener('click', () => this.downloadAllImages());
        }
    }

    bindModalEvents() {
        const modal = document.getElementById('imageModal');
        const closeBtn = document.querySelector('.close');

        if (closeBtn) closeBtn.addEventListener('click', () => this.closeModal());
        
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) this.closeModal();
            });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeModal();
        });

        // 模态框操作按钮
        const downloadBtn = document.getElementById('downloadBtn');
        const copyPathBtn = document.getElementById('copyPathBtn');
        const copyUrlBtn = document.getElementById('copyUrlBtn');
        const similarSearchBtn = document.getElementById('similarSearchBtn'); // 新增

        if (downloadBtn) downloadBtn.addEventListener('click', () => this.downloadCurrentImage());
        if (copyPathBtn) copyPathBtn.addEventListener('click', () => this.copyImagePath());
        if (copyUrlBtn) copyUrlBtn.addEventListener('click', () => this.copyImageUrl());
        if (similarSearchBtn) similarSearchBtn.addEventListener('click', () => this.searchSimilarToThis()); // 新增

    }

    bindTagEvents() {
        // 绑定所有标签点击事件
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('tag-pill') && e.target.hasAttribute('data-tag')) {
                e.preventDefault();
                const tag = e.target.getAttribute('data-tag');
                this.toggleTag(tag, e.target);
            }
        });

        // 绑定分类展开/收起
        document.querySelectorAll('.category-toggle').forEach(toggle => {
            toggle.addEventListener('click', (e) => {
                e.preventDefault();
                const content = toggle.closest('.category-card').querySelector('.category-content');
                const icon = toggle.querySelector('i');
                
                if (content.classList.contains('hidden')) {
                    content.classList.remove('hidden');
                    icon.style.transform = 'rotate(180deg)';
                } else {
                    content.classList.add('hidden');
                    icon.style.transform = 'rotate(0deg)';
                }
            });
        });
    }

    bindAIInputEvents() {
        const aiSearchInput = document.getElementById('aiSearchInput');
        const translateBtn = document.getElementById('translateBtn');
        
        if (aiSearchInput) {
            aiSearchInput.addEventListener('input', (e) => {
                const text = e.target.value;
                const hasChinese = /[\u4e00-\u9fa5]/.test(text);
                
                if (translateBtn) {
                    if (hasChinese && text.trim()) {
                        translateBtn.classList.add('animate-pulse');
                        translateBtn.style.background = 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)';
                        translateBtn.title = '检测到中文，建议翻译获得更好效果';
                    } else {
                        translateBtn.classList.remove('animate-pulse');
                        translateBtn.style.background = '#10b981';
                        translateBtn.title = '翻译为英文';
                        
                        if (!text.trim()) {
                            this.hideTranslationResult();
                        }
                    }
                }
            });
        }
    }

    bindKeyboardEvents() {
        document.addEventListener('keydown', (e) => {
            // AI搜索相关快捷键
            if (this.currentSearchType === 'ai' || document.getElementById('aiSearchInput') === document.activeElement) {
                if ((e.ctrlKey || e.metaKey) && e.key === 't') {
                    e.preventDefault();
                    this.translateSearchText();
                    return;
                }
                
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                    e.preventDefault();
                    this.smartAISearch();
                    return;
                }
            }
            
            // 模态框相关快捷键
            const modal = document.getElementById('imageModal');
            if (modal && !modal.classList.contains('hidden')) {
                switch(e.key) {
                    case 'Escape':
                        this.closeModal();
                        break;
                    case 'ArrowLeft':
                        e.preventDefault();
                        this.showPreviousImage();
                        break;
                    case 'ArrowRight':
                        e.preventDefault();
                        this.showNextImage();
                        break;
                    case 'd':
                    case 'D':
                        if (e.ctrlKey || e.metaKey) {
                            e.preventDefault();
                            this.downloadCurrentImage();
                        }
                        break;
                }
            }
        });
    }

    toggleTag(tag, element) {
        if (this.selectedTags.includes(tag)) {
            this.removeTag(tag);
            element.classList.remove('selected');
        } else {
            this.addTag(tag);
            element.classList.add('selected');
        }
    }

    addTag(tag) {
        if (!tag || this.selectedTags.includes(tag)) return;

        this.selectedTags.push(tag);
        this.updateSelectedTagsDisplay();
        this.updateSearchInput();
        this.showSuccess(`已添加标签: ${tag}`);

        // 更新所有对应的标签元素视觉状态
        document.querySelectorAll(`[data-tag="${tag}"]`).forEach(el => {
            el.classList.add('selected');
        });
    }

    removeTag(tag) {
        const index = this.selectedTags.indexOf(tag);
        if (index > -1) {
            this.selectedTags.splice(index, 1);
            this.updateSelectedTagsDisplay();
            this.updateSearchInput();

            // 更新所有对应的标签元素视觉状态
            document.querySelectorAll(`[data-tag="${tag}"]`).forEach(el => {
                el.classList.remove('selected');
            });
        }
    }

    updateSelectedTagsDisplay() {
        const selectedTagsContainer = document.getElementById('selectedTags');
        const selectedTagsArea = document.getElementById('selectedTagsArea');
        
        if (!selectedTagsContainer) return;

        selectedTagsContainer.innerHTML = '';

        if (this.selectedTags.length === 0) {
            selectedTagsArea.style.display = 'none';
            return;
        }

        selectedTagsArea.style.display = 'block';

        this.selectedTags.forEach(tag => {
            const tagElement = document.createElement('span');
            tagElement.className = 'inline-flex items-center px-4 py-2 rounded-full text-sm bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg';
            tagElement.innerHTML = `
                <span class="mr-2">${tag}</span>
                <button type="button" class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-white bg-opacity-20 hover:bg-opacity-30 transition-all" onclick="app.removeTag('${tag}')">
                    <i class="fas fa-times text-xs"></i>
                </button>
            `;
            selectedTagsContainer.appendChild(tagElement);
        });
    }

    clearAllTags() {
        this.selectedTags.forEach(tag => {
            document.querySelectorAll(`[data-tag="${tag}"]`).forEach(el => {
                el.classList.remove('selected');
            });
        });
        
        this.selectedTags = [];
        this.updateSelectedTagsDisplay();
        this.updateSearchInput();
        this.showSuccess('已清空所有标签');
    }

    updateSearchInput() {
        const searchInput = document.getElementById('searchInput');
        const aiSearchInput = document.getElementById('aiSearchInput');
        
        // 对于本地搜索（智能搜索和基础搜索），直接使用标签组合
        const localSearchText = this.selectedTags.join(' ');
        
        // 对于AI搜索，需要转换为英文描述
        const aiSearchText = this.convertTagsToAIQuery(this.selectedTags);
        
        if (searchInput && (this.currentSearchType === 'intelligent' || this.currentSearchType === 'basic')) {
            searchInput.value = localSearchText;
        }
        
        if (aiSearchInput && this.currentSearchType === 'ai') {
            aiSearchInput.value = aiSearchText;
        }
    }

    // 新增：将中文标签转换为AI搜索友好的英文查询
    convertTagsToAIQuery(tags) {
        if (tags.length === 0) return '';
        
        // 标签映射表：中文标签 -> 英文搜索词
        const tagTranslations = {
            // 车型
            '轿车': 'sedan car',
            'SUV': 'SUV vehicle',
            '越野': 'off-road vehicle',
            '房车': 'RV motorhome',
            'MPV': 'MPV van',
            '跑车': 'sports car',
            '皮卡': 'pickup truck',
            '古典车': 'classic vintage car',
            '电动车': 'electric car',
            '紧凑型轿车': 'compact sedan',
            '中型轿车': 'mid-size sedan',
            '豪华轿车': 'luxury sedan',
            
            // 拍摄视角
            '正面视角': 'front view',
            '侧面视角': 'side view',
            '45度角': '45 degree angle',
            '后视图': 'rear view',
            '俯视图': 'top view aerial',
            '仰视角': 'low angle view',
            '车内视角': 'interior view',
            '全景视角': 'panoramic view',
            '鸟瞰视角': 'bird eye view',
            '特写': 'close up detail',
            
            // 场景环境
            '城市': 'urban city',
            '风景': 'scenic landscape',
            '家庭出游': 'family travel',
            '商务出行': 'business travel',
            '休闲旅行': 'leisure travel',
            '户外探险': 'outdoor adventure',
            '建筑': 'architecture building',
            '街拍': 'street photography',
            '展示场景': 'showroom display',
            
            // 光线效果
            '自然光线': 'natural lighting',
            '黄金时刻光线': 'golden hour',
            '逆光': 'backlight silhouette',
            '夜晚光线': 'night lighting',
            
            // 拍摄风格
            '商业风格': 'commercial photography',
            '艺术创意': 'artistic creative',
            '复古风格': 'vintage retro style',
            '科技风格': 'modern technology'
        };
        
        // 转换标签为英文
        const englishTerms = tags.map(tag => {
            return tagTranslations[tag] || tag; // 如果没有映射，使用原标签
        });
        
        // 组合成自然的英文查询
        return this.combineTermsNaturally(englishTerms);
    }
    
    // 将英文词汇自然地组合成搜索查询
    combineTermsNaturally(terms) {
        if (terms.length === 0) return '';
        if (terms.length === 1) return terms[0];
        
        // 简单的自然语言组合策略
        let query = '';
        
        // 分类词汇
        const vehicles = terms.filter(term => 
            term.includes('car') || term.includes('SUV') || term.includes('vehicle') || 
            term.includes('sedan') || term.includes('truck') || term.includes('van')
        );
        
        const views = terms.filter(term => 
            term.includes('view') || term.includes('angle') || term.includes('perspective')
        );
        
        const lighting = terms.filter(term => 
            term.includes('lighting') || term.includes('light') || term.includes('hour')
        );
        
        const styles = terms.filter(term => 
            term.includes('photography') || term.includes('style') || term.includes('artistic')
        );
        
        const scenes = terms.filter(term => 
            !vehicles.includes(term) && !views.includes(term) && 
            !lighting.includes(term) && !styles.includes(term)
        );
        
        // 按优先级组合
        const parts = [];
        
        if (vehicles.length > 0) parts.push(vehicles[0]);
        if (scenes.length > 0) parts.push(scenes.join(' '));
        if (views.length > 0) parts.push(views[0]);
        if (lighting.length > 0) parts.push(lighting[0]);
        if (styles.length > 0) parts.push(styles[0]);
        
        return parts.join(' ');
    }

    toggleTagPanel() {
        const content = document.getElementById('tagPanelContent');
        const icon = document.getElementById('tagPanelToggleIcon');
        
        if (content.style.display === 'none') {
            content.style.display = 'block';
            icon.className = 'fas fa-chevron-up';
        } else {
            content.style.display = 'none';
            icon.className = 'fas fa-chevron-down';
        }
    }

    async applyTagsAndSearch() {
        this.updateSearchInput();
        
        if (this.currentSearchType === 'ai') {
            const aiSearchInput = document.getElementById('aiSearchInput');
            const text = aiSearchInput.value.trim();
            
            // 对于AI搜索，如果转换后的查询包含中文（映射表中没有的标签），提供翻译选项
            if (/[\u4e00-\u9fa5]/.test(text)) {
                const shouldTranslate = confirm('检测到中文标签，AI搜索建议使用英文。是否自动翻译？');
                if (shouldTranslate) {
                    await this.translateSearchText();
                }
            }
            
            this.performAISearch();
        } else {
            this.performTextSearch();
        }
    }

    async loadSystemInfo() {
        try {
            const response = await fetch('/api/system_info');
            const result = await response.json();
            
            if (result.success) {
                this.systemInfo = result.data;
                this.updateSystemStatus();
                this.updateTabsBasedOnCapabilities();
            } else {
                this.showError('系统信息加载失败: ' + result.error);
            }
        } catch (error) {
            this.showError('无法连接到服务器');
        }
    }

    updateSystemStatus() {
        const statusText = document.getElementById('statusText');
        const indexedCount = document.getElementById('indexedCount');
        
        if (statusText) {
            if (this.systemInfo.status === 'ready') {
                statusText.textContent = '系统运行正常';
                statusText.className = 'text-gray-700 font-medium';
            } else {
                statusText.textContent = '系统异常';
                statusText.className = 'text-red-600 font-medium';
            }
        }
        
        if (indexedCount) {
            indexedCount.textContent = this.systemInfo.indexed_count?.toLocaleString() || '0';
        }
    }

    updateTabsBasedOnCapabilities() {
        const intelligentTab = document.getElementById('tabIntelligent');
        const aiTab = document.getElementById('tabAI');
        
        if (intelligentTab && !this.systemInfo.llm_enabled) {
            intelligentTab.style.opacity = '0.5';
            intelligentTab.title = 'LLM功能未启用';
            if (this.currentSearchType === 'intelligent') {
                this.switchTab('basic');
            }
        }

        const externalSources = this.systemInfo.external_sources;
        if (aiTab && (!externalSources || (!externalSources.pexels && !externalSources.unsplash))) {
            aiTab.style.opacity = '0.5';
            aiTab.title = '外部图片源API未配置';
            if (this.currentSearchType === 'ai') {
                this.switchTab('basic');
            }
        }
    }

    switchTab(tabType) {
        console.log('切换到标签页:', tabType);
        
        // 更新标签页外观
        const tabs = document.querySelectorAll('.search-tab');
        tabs.forEach(tab => {
            if (tab) tab.classList.remove('active');
        });
        
        let tabId;
        if (tabType === 'ai') {
            tabId = 'tabAI';
        } else {
            tabId = `tab${tabType.charAt(0).toUpperCase() + tabType.slice(1)}`;
        }
        
        const targetTab = document.getElementById(tabId);
        if (targetTab) {
            targetTab.classList.add('active');
        } else {
            console.error(`❌ 找不到标签页: ${tabId}`);
            return;
        }

        // 更新搜索面板
        const textPanel = document.getElementById('textSearchPanel');
        const aiPanel = document.getElementById('aiSearchPanel'); 
        const imagePanel = document.getElementById('imageSearchPanel');
        
        // 隐藏所有面板
        if (textPanel) textPanel.classList.add('hidden');
        if (aiPanel) aiPanel.classList.add('hidden');
        if (imagePanel) imagePanel.classList.add('hidden');

        // 显示对应面板
        if (tabType === 'ai') {
            if (aiPanel) aiPanel.classList.remove('hidden');
        } else if (tabType === 'image') {
            if (imagePanel) imagePanel.classList.remove('hidden');
        } else {
            if (textPanel) textPanel.classList.remove('hidden');
        }

        // 更新提示
        const intelligentHint = document.querySelector('.intelligent-hint');
        const basicHint = document.querySelector('.basic-hint');
        const aiHint = document.querySelector('.ai-hint');

        if (intelligentHint) intelligentHint.classList.toggle('hidden', tabType !== 'intelligent');
        if (basicHint) basicHint.classList.toggle('hidden', tabType !== 'basic');
        if (aiHint) aiHint.classList.toggle('hidden', tabType !== 'ai');

        this.currentSearchType = tabType;
        
        // 切换标签页时同步更新搜索输入框
        this.updateSearchInput();
        
        this.clearResults();
    }

    // 修改翻译搜索文本方法
    async translateSearchText() {
        const aiSearchInput = document.getElementById('aiSearchInput');
        const translationResult = document.getElementById('translationResult');
        const translatedText = document.getElementById('translatedText');
        const translateBtn = document.getElementById('translateBtn');
        
        if (!aiSearchInput || !aiSearchInput.value.trim()) {
            this.showError('请先输入要翻译的内容');
            return;
        }
        
        const textToTranslate = aiSearchInput.value.trim();
        
        // 改进的中文检测
        if (!/[\u4e00-\u9fa5]/.test(textToTranslate)) {
            this.showSuccess('输入内容已是英文，无需翻译');
            return;
        }
        
        // 检查文本长度，太短的文本可能翻译失败
        if (textToTranslate.length < 2) {
            this.showError('输入内容太短，请输入更完整的描述');
            return;
        }
        
        try {
            if (translateBtn) {
                translateBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>翻译中';
                translateBtn.disabled = true;
            }
            
            // 注意：这里修改了请求体结构，去掉了 source 和 target 参数
            // 因为您的后端代码没有使用这些参数
            const response = await fetch('/api/translate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: textToTranslate
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                if (translatedText) {
                    translatedText.textContent = result.data.translated;
                }
                if (translationResult) {
                    translationResult.classList.remove('hidden');
                }
                
                aiSearchInput.value = result.data.translated;
                this.showSuccess('翻译完成！已自动填入搜索框');
            } else {
                // 更详细的错误处理
                let errorMsg = result.error || '翻译失败';
                
                // 针对不同的错误类型给出不同建议
                if (errorMsg.includes('invalid source language')) {
                    errorMsg = '无法识别输入语言，请输入完整的中文描述';
                    this.showAlternativeSuggestions(textToTranslate);
                } else if (errorMsg.includes('翻译内容不能为空')) {
                    errorMsg = '输入内容为空，请输入要翻译的文本';
                } else if (errorMsg.includes('网络')) {
                    errorMsg = '网络连接失败，请检查网络后重试';
                }
                
                this.showError(errorMsg);
                
                // 如果是短文本翻译失败，提供备选方案
                if (textToTranslate.length <= 3) {
                    this.showAlternativeSuggestions(textToTranslate);
                }
            }
            
        } catch (error) {
            console.error('翻译失败:', error);
            
            // 网络错误处理
            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                this.showError('网络连接失败，请检查网络连接');
            } else {
                this.showError('翻译服务暂时不可用，请稍后再试');
            }
            
            // 提供备选方案
            this.showAlternativeSuggestions(textToTranslate);
            
        } finally {
            if (translateBtn) {
                translateBtn.innerHTML = '<i class="fas fa-language mr-1"></i>翻译';
                translateBtn.disabled = false;
            }
        }
    }

    // 改进的备选建议方法
    showAlternativeSuggestions(originalText) {
        // 扩展的简单翻译映射表
        const simpleTranslations = {
            // 单字符
            '车': 'car vehicle',
            
            // 车型
            '轿车': 'sedan car',
            '汽车': 'car automobile',
            'SUV': 'SUV vehicle',
            '越野': 'off-road vehicle',
            '房车': 'RV motorhome',
            'MPV': 'MPV van',
            '跑车': 'sports car', 
            '皮卡': 'pickup truck',
            '古典车': 'classic vintage car',
            '电动车': 'electric car',
            '紧凑型轿车': 'compact sedan',
            '中型轿车': 'mid-size sedan',
            '豪华轿车': 'luxury sedan',
            
            // 视角
            '正面视角': 'front view',
            '侧面视角': 'side view',
            '45度角': '45 degree angle',
            '后视图': 'rear view',
            '俯视图': 'top view aerial',
            '仰视角': 'low angle view',
            '车内视角': 'interior view',
            '全景视角': 'panoramic view',
            '鸟瞰视角': 'bird eye view',
            '特写': 'close up detail',
            
            // 场景
            '城市': 'urban city',
            '风景': 'scenic landscape',
            '家庭出游': 'family travel',
            '商务出行': 'business travel',
            '休闲旅行': 'leisure travel',
            '户外探险': 'outdoor adventure',
            '建筑': 'architecture building',
            '街拍': 'street photography',
            '展示场景': 'showroom display',
            
            // 光线
            '自然光线': 'natural lighting',
            '黄金时刻': 'golden hour',
            '逆光': 'backlight silhouette',
            '夜景': 'night lighting',
            
            // 风格
            '商业风格': 'commercial photography',
            '艺术创意': 'artistic creative',
            '复古风格': 'vintage retro style',
            '科技风格': 'modern technology'
        };
        
        // 尝试找到最佳匹配
        let suggestion = null;
        let matchedKey = null;
        
        // 完全匹配
        if (simpleTranslations[originalText]) {
            suggestion = simpleTranslations[originalText];
            matchedKey = originalText;
        } else {
            // 部分匹配
            for (const [chinese, english] of Object.entries(simpleTranslations)) {
                if (originalText.includes(chinese)) {
                    suggestion = english;
                    matchedKey = chinese;
                    break;
                }
            }
        }
        
        if (suggestion) {
            // 延迟显示建议，避免干扰用户
            setTimeout(() => {
                const message = matchedKey === originalText ? 
                    `翻译失败，是否使用预设翻译 "${suggestion}"？` :
                    `翻译失败，检测到关键词"${matchedKey}"，是否使用 "${suggestion}"？`;
                    
                if (confirm(message)) {
                    const aiSearchInput = document.getElementById('aiSearchInput');
                    if (aiSearchInput) {
                        aiSearchInput.value = suggestion;
                        this.showSuccess(`已使用建议搜索词：${suggestion}`);
                        
                        // 显示翻译结果区域
                        const translationResult = document.getElementById('translationResult');
                        const translatedText = document.getElementById('translatedText');
                        if (translationResult && translatedText) {
                            translatedText.textContent = suggestion;
                            translationResult.classList.remove('hidden');
                        }
                    }
                }
            }, 1000);
        } else if (originalText.length <= 2) {
            // 对于短文本，给出通用建议
            setTimeout(() => {
                if (confirm('文本太短导致翻译失败，是否改用英文关键词搜索？\n建议：car, vehicle, automobile')) {
                    const aiSearchInput = document.getElementById('aiSearchInput');
                    if (aiSearchInput) {
                        aiSearchInput.value = 'car vehicle';
                        this.showSuccess('已使用通用汽车搜索词');
                    }
                }
            }, 1000);
        }
    }

    hideTranslationResult() {
        const translationResult = document.getElementById('translationResult');
        if (translationResult) {
            translationResult.classList.add('hidden');
        }
    }

    async smartAISearch() {
        const aiSearchInput = document.getElementById('aiSearchInput');
        if (!aiSearchInput || !aiSearchInput.value.trim()) {
            this.showError('请先输入搜索内容');
            return;
        }
        
        const query = aiSearchInput.value.trim();
        
        // 检查是否包含中文
        if (/[\u4e00-\u9fa5]/.test(query)) {
            // 如果是单个字符或很短的文本，直接使用预设的英文词汇
            if (query.length <= 2) {
                const quickTranslations = {
                    '车': 'car vehicle',
                    '汽车': 'car automobile',
                    '轿车': 'sedan car',
                    '城市': 'city urban',
                    '风景': 'landscape',
                    '自然': 'natural'
                };
                
                if (quickTranslations[query]) {
                    aiSearchInput.value = quickTranslations[query];
                    this.showSuccess(`已使用快速翻译：${quickTranslations[query]}`);
                    
                    // 显示翻译结果
                    const translationResult = document.getElementById('translationResult');
                    const translatedText = document.getElementById('translatedText');
                    if (translationResult && translatedText) {
                        translatedText.textContent = quickTranslations[query];
                        translationResult.classList.remove('hidden');
                    }
                    
                    setTimeout(() => {
                        this.performAISearch();
                    }, 500);
                    return;
                }
            }
            
            // 对于较长的文本，尝试翻译
            try {
                await this.translateSearchText();
                setTimeout(() => {
                    this.performAISearch();
                }, 500);
            } catch (error) {
                // 翻译失败时，询问是否直接使用中文搜索
                const useChineseDirectly = confirm('翻译失败，是否直接使用中文进行搜索？\n注意：使用中文搜索效果可能不佳');
                if (useChineseDirectly) {
                    this.performAISearch();
                }
            }
        } else {
            // 直接搜索英文内容
            this.performAISearch();
        }
    }

    async performTextSearch() {
        const searchInput = document.getElementById('searchInput');
        if (!searchInput) {
            this.showError('搜索输入框未找到');
            return;
        }

        const query = searchInput.value.trim();
        if (!query) {
            this.showError('请输入搜索内容');
            return;
        }

        if (this.currentSearchType === 'intelligent' && !this.systemInfo.llm_enabled) {
            this.showError('LLM功能未启用，请使用基础搜索');
            return;
        }

        const customResultCount = document.getElementById('customResultCount');
        const topK = parseInt(customResultCount ? customResultCount.value : 9) || 9;
        
        this.showLoading(`正在执行${this.currentSearchType === 'intelligent' ? '智能' : '基础'}搜索...`);

        try {
            const endpoint = this.currentSearchType === 'intelligent' ? '/api/search/intelligent' : '/api/search/basic';
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, top_k: topK })
            });

            const result = await response.json();
            
            if (result.success) {
                this.currentResults = result.data.results;
                this.displayResults(result.data);
            } else {
                this.showError(result.error);
            }
        } catch (error) {
            this.showError('搜索请求失败: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    async performAISearch() {
        const aiSearchInput = document.getElementById('aiSearchInput');
        const aiSearchSource = document.getElementById('aiSearchSource');
        const aiResultCount = document.getElementById('aiResultCount');

        if (!aiSearchInput || !aiSearchSource || !aiResultCount) {
            this.showError('AI搜索界面元素未找到');
            return;
        }

        const query = aiSearchInput.value.trim();
        const source = aiSearchSource.value;
        const perPage = parseInt(aiResultCount.value) || 20;

        if (!query) {
            this.showError('请输入搜索内容');
            return;
        }

        // 给用户提示：如果仍包含中文，建议翻译
        if (/[\u4e00-\u9fa5]/.test(query)) {
            const shouldTranslate = confirm('检测到中文内容，AI搜索效果更好需要英文。是否先翻译为英文？');
            if (shouldTranslate) {
                await this.translateSearchText();
                return;
            }
        }

        this.showLoading(`正在从${source === 'all' ? '多个源' : source}搜索AI图片...`);

        try {
            const response = await fetch('/api/search/external', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    query: query,
                    source: source,
                    page: 1,
                    per_page: perPage
                })
            });

            const result = await response.json();
            
            if (result.success) {
                this.currentResults = result.data.results;
                this.displayAIResults(result.data);
                
                if (this.currentResults.length === 0) {
                    this.showError('未找到匹配的图片，请尝试其他关键词');
                }
            } else {
                this.showError(result.error);
            }
        } catch (error) {
            this.showError('AI搜索请求失败: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    async performImageSearch() {
        const imageInput = document.getElementById('imageInput');
        if (!imageInput || !imageInput.files[0]) {
            this.showError('请先选择图片');
            return;
        }

        const imageCustomResultCount = document.getElementById('imageCustomResultCount');
        const topK = parseInt(imageCustomResultCount ? imageCustomResultCount.value : 9) || 9;
        const formData = new FormData();
        formData.append('image', imageInput.files[0]);
        formData.append('top_k', topK);

        this.showLoading('正在执行以图搜图...');

        try {
            const response = await fetch('/api/search/image', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (result.success) {
                this.currentResults = result.data.results;
                this.displayResults(result.data);
            } else {
                this.showError(result.error);
            }
        } catch (error) {
            this.showError('图片搜索失败: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    handleImageUpload(file) {
        console.log('开始处理图片上传:', file);
        
        if (!file || !file.type.startsWith('image/')) {
            this.showError('请选择有效的图片文件');
            return;
        }

        // 检查文件大小（可选，比如限制10MB）
        const maxSize = 20 * 1024 * 1024; // 10MB
        if (file.size > maxSize) {
            this.showError('图片文件过大，请选择小于10MB的图片');
            return;
        }

        const reader = new FileReader();
        reader.onload = (e) => {
            console.log('文件读取完成，开始更新界面');
            
            const previewImage = document.getElementById('previewImage');
            const uploadArea = document.getElementById('uploadArea');
            const previewArea = document.getElementById('previewArea');
            const imageFileName = document.getElementById('imageFileName');
            const imageFileSize = document.getElementById('imageFileSize');
            const imageSearchBtn = document.getElementById('imageSearchBtn');
            
            console.log('DOM元素查找结果:', {
                previewImage: !!previewImage,
                uploadArea: !!uploadArea,
                previewArea: !!previewArea,
                imageFileName: !!imageFileName,
                imageFileSize: !!imageFileSize,
                imageSearchBtn: !!imageSearchBtn
            });
            
            if (previewImage) {
                previewImage.src = e.target.result;
                console.log('预览图片已设置');
            } else {
                console.error('找不到 previewImage 元素');
            }
            
            if (uploadArea) {
                uploadArea.style.display = 'none';
                console.log('上传区域已隐藏');
            } else {
                console.error('找不到 uploadArea 元素');
            }
            
            if (previewArea) {
                previewArea.classList.remove('hidden');
                console.log('预览区域已显示');
            } else {
                console.error('找不到 previewArea 元素');
            }
            
            if (imageFileName) {
                imageFileName.textContent = file.name;
                console.log('文件名已设置:', file.name);
            }
            
            if (imageFileSize) {
                imageFileSize.textContent = this.formatFileSize(file.size);
                console.log('文件大小已设置:', this.formatFileSize(file.size));
            }
            
            if (imageSearchBtn) {
                imageSearchBtn.disabled = false;
                console.log('搜索按钮已启用');
            }

            this.showSuccess(`图片 "${file.name}" 上传成功，可以开始搜索了！`);
        };
        
        reader.onerror = (error) => {
            console.error('文件读取失败:', error);
            this.showError('图片读取失败，请重试');
        };
        
        reader.readAsDataURL(file);
    }

    displayResults(data) {
        // 隐藏欢迎界面
        const welcomeView = document.getElementById('welcomeView');
        if (welcomeView) welcomeView.classList.add('hidden');

        const resultsSection = document.getElementById('resultsSection');
        const noResults = document.getElementById('noResults');
        const resultsGrid = document.getElementById('resultsGrid');
        const resultCountSpan = document.getElementById('searchResultCount');

        if (!data.results || data.results.length === 0) {
            if (resultsSection) resultsSection.classList.add('hidden');
            if (noResults) noResults.classList.remove('hidden');
            return;
        }

        if (data.search_type === 'intelligent' && data.query_analysis) {
            this.displayQueryAnalysis(data.query_analysis);
        } else {
            const queryAnalysis = document.getElementById('queryAnalysis');
            if (queryAnalysis) queryAnalysis.classList.add('hidden');
        }

        if (resultsGrid) resultsGrid.innerHTML = '';
        if (resultCountSpan) resultCountSpan.textContent = `找到 ${data.results.length} 个结果`;

        if (resultsGrid) {
            data.results.forEach((result, index) => {
                const resultCard = this.createResultCard(result, index);
                resultsGrid.appendChild(resultCard);
            });
        }

        if (resultsSection) resultsSection.classList.remove('hidden');
        if (noResults) noResults.classList.add('hidden');

        // 平滑滚动到结果区域
        setTimeout(() => {
            if (resultsSection) {
                resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 100);
    }

    displayAIResults(data) {
        const welcomeView = document.getElementById('welcomeView');
        if (welcomeView) welcomeView.classList.add('hidden');
        const resultsSection = document.getElementById('resultsSection');
        const noResults = document.getElementById('noResults');
        const resultsGrid = document.getElementById('resultsGrid');
        const resultCountSpan = document.getElementById('searchResultCount');

        if (!data.results || data.results.length === 0) {
            if (resultsSection) resultsSection.classList.add('hidden');
            if (noResults) noResults.classList.remove('hidden');
            return;
        }

        const queryAnalysis = document.getElementById('queryAnalysis');
        if (queryAnalysis) queryAnalysis.classList.add('hidden');

        // 显示AI搜索特定的结果信息
        this.displayAISearchInfo(data);

        if (resultsGrid) resultsGrid.innerHTML = '';
        if (resultCountSpan) {
            resultCountSpan.textContent = `从 ${data.source === 'all' ? '多个源' : data.source} 找到 ${data.results.length} 张图片`;
        }

        if (resultsGrid) {
            data.results.forEach((result, index) => {
                const resultCard = this.createAIResultCard(result, index);
                resultsGrid.appendChild(resultCard);
            });
        }

        if (resultsSection) resultsSection.classList.remove('hidden');
        if (noResults) noResults.classList.add('hidden');

        setTimeout(() => {
            if (resultsSection) {
                resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 100);
    }

    displayAISearchInfo(data) {
        // 在结果上方显示AI搜索的信息
        let aiInfoDiv = document.getElementById('aiSearchInfo');
        
        if (!aiInfoDiv) {
            aiInfoDiv = document.createElement('div');
            aiInfoDiv.id = 'aiSearchInfo';
            aiInfoDiv.className = 'glass-card rounded-2xl p-6 mb-6';
            
            // 插入到结果区域之前
            const resultsSection = document.getElementById('resultsSection');
            if (resultsSection && resultsSection.parentNode) {
                resultsSection.parentNode.insertBefore(aiInfoDiv, resultsSection);
            }
        }

        const sourceLabels = {
            'all': '多个图片源',
            'pexels': 'Pexels',
            'unsplash': 'Unsplash',
            'pixabay': 'Pixabay'
        };

        // 显示可用源信息
        const availableSources = data.available_sources || [];
        const sourceList = availableSources.map(s => sourceLabels[s] || s).join('、');

        aiInfoDiv.innerHTML = `
            <h3 class="font-semibold text-gray-800 mb-4">
                <i class="fas fa-globe mr-2 text-purple-500"></i>AI图片源搜索结果
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm text-gray-700">
                <div class="space-y-2">
                    <p><strong>搜索内容:</strong> "${data.query}"</p>
                    <p><strong>图片源:</strong> ${sourceLabels[data.source] || data.source}</p>
                </div>
                <div class="space-y-2">
                    <p><strong>结果数量:</strong> ${data.results.length} 张</p>
                    <p><strong>可用源:</strong> ${sourceList}</p>
                </div>
            </div>
            <div class="mt-4 p-3 bg-blue-50 rounded-lg text-xs text-gray-600">
                💡 AI图片源提供高质量的专业摄影作品，适合商业和创意用途
            </div>
        `;
        
        aiInfoDiv.classList.remove('hidden');
    }

    displayQueryAnalysis(analysis) {
        const queryAnalysis = document.getElementById('queryAnalysis');
        const analysisContent = document.getElementById('analysisContent');

        if (!queryAnalysis || !analysisContent) return;

        let html = '';
        if (analysis.summary) {
            html += `<div class="mb-3 p-3 bg-blue-50 rounded-lg"><strong class="text-blue-800">理解:</strong> <span class="text-blue-700">${analysis.summary}</span></div>`;
        }
        if (analysis.scene_type) {
            html += `<div class="mb-3 p-3 bg-green-50 rounded-lg"><strong class="text-green-800">场景:</strong> <span class="text-green-700">${analysis.scene_type}</span></div>`;
        }
        if (analysis.style_preference) {
            html += `<div class="mb-3 p-3 bg-purple-50 rounded-lg"><strong class="text-purple-800">风格:</strong> <span class="text-purple-700">${analysis.style_preference}</span></div>`;
        }
        if (analysis.key_concepts && analysis.key_concepts.length > 0) {
            html += `<div class="mb-3 p-3 bg-orange-50 rounded-lg"><strong class="text-orange-800">关键概念:</strong> <span class="text-orange-700">${analysis.key_concepts.join('、')}</span></div>`;
        }

        analysisContent.innerHTML = html;
        queryAnalysis.classList.remove('hidden');
    }

    // 修改结果卡片创建，确保本地图片的相似搜索按钮正常工作
    createResultCard(result, index) {
        const card = document.createElement('div');
        card.className = 'result-card rounded-2xl overflow-hidden group';
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';

        const imageHtml = result.image_base64 ? 
            `<img src="${result.image_base64}" alt="${result.filename}" class="w-full h-48 object-cover cursor-pointer group-hover:scale-105 transition-transform duration-300" onclick="app.showImageDetail(${index})">` :
            `<div class="w-full h-48 bg-gradient-to-br from-gray-200 to-gray-300 flex items-center justify-center cursor-pointer group-hover:scale-105 transition-transform duration-300" onclick="app.showImageDetail(${index})">
                <div class="text-center">
                    <i class="fas fa-image text-4xl text-gray-400"></i>
                    <p class="text-sm text-gray-500 mt-2">点击查看原图</p>
                </div>
            </div>`;

        const similarityColor = result.similarity >= 0.9 ? 'text-green-600' : result.similarity >= 0.7 ? 'text-blue-600' : 'text-orange-600';

        card.innerHTML = `
            <div class="overflow-hidden">
                ${imageHtml}
            </div>
            <div class="p-4">
                <div class="flex justify-between items-start mb-2">
                    <h3 class="font-semibold text-gray-800 truncate cursor-pointer hover:text-blue-600 transition-colors" 
                        title="${result.filename}" onclick="app.showImageDetail(${index})">
                        ${result.filename}
                    </h3>
                    <span class="text-sm font-bold ${similarityColor} ml-2 bg-gray-50 px-2 py-1 rounded-lg">
                        ${(result.similarity * 100).toFixed(1)}%
                    </span>
                </div>
                <p class="text-xs text-gray-500 mb-3">ID: ${result.id}</p>
                <div class="text-sm text-gray-600 mb-4">
                    <p class="line-clamp-2 leading-relaxed" title="${result.display_tags}">
                        ${result.display_tags.length > 80 ? result.display_tags.slice(0, 80) + '...' : result.display_tags}
                    </p>
                </div>
                <div class="flex justify-between items-center">
                    <span class="text-xs flex items-center ${result.image_exists ? 'text-green-600' : 'text-red-600'}">
                        <i class="fas ${result.image_exists ? 'fa-check-circle' : 'fa-times-circle'} mr-1"></i>
                        ${result.image_exists ? '文件存在' : '文件不存在'}
                    </span>
                    <div class="flex gap-2">
                        <button onclick="app.downloadImage(${index})" 
                                class="w-8 h-8 flex items-center justify-center text-green-600 hover:text-white hover:bg-green-500 rounded-lg transition-all duration-200" 
                                title="下载图片">
                            <i class="fas fa-download text-sm"></i>
                        </button>
                        <button onclick="app.searchSimilarToResult(${index})" 
                                class="w-8 h-8 flex items-center justify-center text-purple-600 hover:text-white hover:bg-purple-500 rounded-lg transition-all duration-200" 
                                title="搜索相似图片">
                            <i class="fas fa-search-plus text-sm"></i>
                        </button>
                        <button onclick="app.showImageDetail(${index})" 
                                class="w-8 h-8 flex items-center justify-center text-blue-500 hover:text-white hover:bg-blue-500 rounded-lg transition-all duration-200"
                                title="查看详情">
                            <i class="fas fa-expand-alt text-sm"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;

        // 添加动画延迟
        setTimeout(() => {
            card.style.transition = 'all 0.5s ease-out';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 50);

        return card;
    }

    createAIResultCard(result, index) {
        const card = document.createElement('div');
        
        let borderColor = 'border-purple-400';
        let tagColor = 'bg-purple-500';
        if (result.source === 'pexels') {
            borderColor = 'border-green-500';
            tagColor = 'bg-green-500';
        } else if (result.source === 'unsplash') {
            borderColor = 'border-blue-500';
            tagColor = 'bg-blue-500';
        } else if (result.source === 'pixabay') {
            borderColor = 'border-yellow-500';
            tagColor = 'bg-yellow-500';
        }
        
        card.className = `result-card rounded-2xl overflow-hidden border-l-4 ${borderColor} group`;
        card.style.opacity = '0';
        card.style.transform = 'translateY(30px)';

        const imageHtml = `<img src="${result.thumbnail_url}" alt="${result.title}" 
                               class="w-full h-48 object-cover cursor-pointer group-hover:scale-105 transition-transform duration-300" 
                               onclick="app.showAIImageDetail(${index})">`;

        let extraInfo = '';
        if (result.downloads) extraInfo += `📥 ${result.downloads} `;
        if (result.views) extraInfo += `👀 ${result.views} `;
        if (result.likes) extraInfo += `❤️ ${result.likes}`;

        card.innerHTML = `
            <div class="overflow-hidden">
                ${imageHtml}
            </div>
            <div class="p-4">
                <div class="flex justify-between items-start mb-2">
                    <h3 class="font-semibold text-gray-800 truncate cursor-pointer hover:text-blue-600 transition-colors" 
                        title="${result.title}" onclick="app.showAIImageDetail(${index})">
                        ${result.title.length > 30 ? result.title.substring(0, 30) + '...' : result.title}
                    </h3>
                    <div class="text-right ml-2">
                        <span class="text-xs px-2 py-1 rounded-lg text-white ${tagColor}">
                            ${result.source.toUpperCase()}
                        </span>
                    </div>
                </div>
                <p class="text-xs text-gray-500 mb-2">
                    📷 ${result.photographer} | ${result.width}×${result.height}
                </p>
                <div class="text-sm text-gray-600 mb-3">
                    <p class="line-clamp-2 leading-relaxed" title="${result.description}">
                        ${result.description || '专业摄影作品'}
                    </p>
                </div>
                ${extraInfo ? `<div class="text-xs text-gray-500 mb-3 bg-gray-50 rounded-lg p-2">${extraInfo}</div>` : ''}
                <div class="flex justify-between items-center">
                    <a href="${result.url}" target="_blank" class="text-xs text-blue-600 hover:text-blue-800 transition-colors">
                        <i class="fas fa-external-link-alt mr-1"></i>查看原页面
                    </a>
                    <div class="flex gap-2">
                        <button onclick="app.downloadExternalImage(${index})" 
                                class="w-8 h-8 flex items-center justify-center text-green-600 hover:text-white hover:bg-green-500 rounded-lg transition-all duration-200" 
                                title="下载图片">
                            <i class="fas fa-download text-sm"></i>
                        </button>
                        <button onclick="app.showAIImageDetail(${index})" 
                                class="w-8 h-8 flex items-center justify-center text-blue-500 hover:text-white hover:bg-blue-500 rounded-lg transition-all duration-200"
                                title="查看详情">
                            <i class="fas fa-expand-alt text-sm"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;

        // 添加动画延迟
        setTimeout(() => {
            card.style.transition = 'all 0.5s ease-out';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 50);

        return card;
    }

    showImageDetail(index) {
        if (!this.currentResults[index]) return;
        
        const result = this.currentResults[index];
        this.currentModalImageData = result;
    
        // 更新模态框索引信息
        this.updateModalIndexInfo(index + 1, this.currentResults.length);
    
        const modalImage = document.getElementById('modalImage');
        const modalFilename = document.getElementById('modalFilename');
        const modalSource = document.getElementById('modalSource');
        const modalPhotographer = document.getElementById('modalPhotographer');
        const modalImageSize = document.getElementById('modalImageSize');
        const modalSimilarity = document.getElementById('modalSimilarity');
        const modalFileStatus = document.getElementById('modalFileStatus');
        const modalOriginalUrl = document.getElementById('modalOriginalUrl');
        const modalTags = document.getElementById('modalTags');
        const similarSearchBtn = document.getElementById('similarSearchBtn');
        
        if (modalImage) {
            modalImage.src = result.image_base64 || '';
            modalImage.style.cursor = 'zoom-in';
            modalImage.title = '点击放大查看';
            
            // 清除之前的事件监听器
            const newModalImage = modalImage.cloneNode(true);
            modalImage.parentNode.replaceChild(newModalImage, modalImage);
            
            // 添加新的点击事件监听器
            newModalImage.addEventListener('click', () => {
                console.log('模态框图片被点击');
                if (this.fullscreenViewer && result.image_base64) {
                    this.fullscreenViewer.show(result.image_base64, result);
                } else {
                    console.error('全屏查看器未初始化或图片数据缺失');
                }
            });
        }
        if (modalFilename) modalFilename.textContent = result.filename || '未知';
        if (modalSource) modalSource.textContent = '本地数据库';
        if (modalPhotographer) modalPhotographer.textContent = '未知';
        if (modalImageSize) modalImageSize.textContent = `ID: ${result.id}`;
        if (modalSimilarity) modalSimilarity.textContent = result.similarity ? `${(result.similarity * 100).toFixed(2)}%` : '-';
        if (modalFileStatus) modalFileStatus.textContent = result.image_exists ? '✅ 存在' : '❌ 不存在';
        
        if (modalOriginalUrl) {
            modalOriginalUrl.href = result.url || '#';
            modalOriginalUrl.textContent = result.url || '无';
        }
        
        if (modalTags) modalTags.textContent = result.display_tags || '无标签信息';
    
        // 显示相似搜索按钮（本地数据库图片支持相似搜索）
        if (similarSearchBtn) {
            similarSearchBtn.style.display = 'flex';
            similarSearchBtn.title = '搜索与此图片相似的图片';
        }
    
        this.showModal();
    }
    

    showAIImageDetail(index) {
        if (!this.currentResults[index]) return;
        
        const result = this.currentResults[index];
        this.currentModalImageData = result;
    
        // 更新模态框索引信息
        this.updateModalIndexInfo(index + 1, this.currentResults.length);
    
        const modalImage = document.getElementById('modalImage');
        if (modalImage) {
            modalImage.src = result.image_url || result.thumbnail_url;
            modalImage.style.cursor = 'zoom-in';
            modalImage.title = '点击放大查看';
            
            // 清除之前的事件监听器
            const newModalImage = modalImage.cloneNode(true);
            modalImage.parentNode.replaceChild(newModalImage, modalImage);
            
            // 添加新的点击事件监听器
            newModalImage.addEventListener('click', () => {
                console.log('AI图片模态框被点击');
                if (this.fullscreenViewer) {
                    const fullImageUrl = result.large_url || result.original_url || result.image_url;
                    this.fullscreenViewer.show(fullImageUrl, result);
                } else {
                    console.error('全屏查看器未初始化');
                }
            });
        }
        
        const modalFilename = document.getElementById('modalFilename');
        const modalSource = document.getElementById('modalSource');
        const modalPhotographer = document.getElementById('modalPhotographer');
        const modalImageSize = document.getElementById('modalImageSize');
        const modalSimilarity = document.getElementById('modalSimilarity');
        const modalOriginalUrl = document.getElementById('modalOriginalUrl');
        const modalTags = document.getElementById('modalTags');
        const modalFileStatus = document.getElementById('modalFileStatus');
        const similarSearchBtn = document.getElementById('similarSearchBtn');
    
        if (modalFilename) modalFilename.textContent = result.title;
        if (modalSource) modalSource.textContent = result.source.toUpperCase();
        if (modalPhotographer) modalPhotographer.textContent = result.photographer;
        if (modalImageSize) modalImageSize.textContent = `${result.width}×${result.height}`;
        if (modalSimilarity) modalSimilarity.textContent = '-';
        if (modalFileStatus) modalFileStatus.textContent = '外部图片';
        
        if (modalOriginalUrl) {
            modalOriginalUrl.href = result.url || '#';
            modalOriginalUrl.textContent = result.url || '无';
        }
        
        if (modalTags) modalTags.textContent = result.description || '专业摄影作品';
    
        // 隐藏相似搜索按钮（外部图片不支持相似搜索）
        if (similarSearchBtn) {
            similarSearchBtn.style.display = 'none';
        }
    
        this.showModal();
    }


    updateModalIndexInfo(current, total) {
        const modalImageIndex = document.getElementById('modalImageIndex');
        const modalImageTotal = document.getElementById('modalImageTotal');
        
        if (modalImageIndex) modalImageIndex.textContent = current;
        if (modalImageTotal) modalImageTotal.textContent = total;
    }

    showModal() {
        const modal = document.getElementById('imageModal');
        if (modal) {
            modal.style.display = 'flex';
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
            
            // 模态框显示动画
            modal.style.opacity = '0';
            setTimeout(() => {
                modal.style.transition = 'opacity 0.3s ease-out';
                modal.style.opacity = '1';
            }, 10);
            
            const modalBody = modal.querySelector('.overflow-y-auto');
            if (modalBody) {
                modalBody.scrollTop = 0;
            }
        }
    }

    closeModal() {
        const modal = document.getElementById('imageModal');
        if (modal) {
            modal.style.transition = 'opacity 0.3s ease-out';
            modal.style.opacity = '0';
            
            setTimeout(() => {
                modal.style.display = 'none';
                modal.classList.add('hidden');
                document.body.style.overflow = 'auto';
            }, 300);
        }
        this.currentModalImageData = null;
    }

    showPreviousImage() {
        if (!this.currentModalImageData || !this.currentResults.length) return;
        
        const currentIndex = this.currentResults.findIndex(r => r.id === this.currentModalImageData.id);
        if (currentIndex > 0) {
            const newIndex = currentIndex - 1;
            if (this.currentSearchType === 'ai') {
                this.showAIImageDetail(newIndex);
            } else {
                this.showImageDetail(newIndex);
            }
        }
    }

    showNextImage() {
        if (!this.currentModalImageData || !this.currentResults.length) return;
        
        const currentIndex = this.currentResults.findIndex(r => r.id === this.currentModalImageData.id);
        if (currentIndex < this.currentResults.length - 1) {
            const newIndex = currentIndex + 1;
            if (this.currentSearchType === 'ai') {
                this.showAIImageDetail(newIndex);
            } else {
                this.showImageDetail(newIndex);
            }
        }
    }

    downloadImageByData(imageData) {
        if (imageData.image_path) {
            // 本地图片
            this.downloadImage(this.currentResults.indexOf(imageData));
        } else if (imageData.image_url) {
            // 外部图片
            this.downloadExternalImage(imageData.image_url, `${imageData.title || 'image'}.jpg`);
        }
    }

    async downloadImage(index) {
        if (!this.currentResults[index]) return;
        
        const result = this.currentResults[index];
        if (!result.image_exists || !result.image_path) {
            this.showError('图片文件不存在');
            return;
        }

        try {
            const response = await fetch('/api/download_image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image_path: result.image_path })
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = result.filename || 'image.jpg';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                this.showSuccess(`图片 ${result.filename} 下载成功`);
            } else {
                this.showError('下载失败');
            }
        } catch (error) {
            this.showError('下载请求失败: ' + error.message);
        }
    }

    async downloadExternalImage(index) {
        if (!this.currentResults[index]) return;
        
        const result = this.currentResults[index];
        
        try {
            const response = await fetch('/api/download_external', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    image_url: result.large_url || result.image_url,
                    filename: `${result.source}_${result.title.replace(/[^a-zA-Z0-9]/g, '_')}.jpg`
                })
            });

            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${result.source}_${result.title.replace(/[^a-zA-Z0-9]/g, '_')}.jpg`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                
                this.showSuccess(`图片 ${result.title} 下载成功`);
            } else {
                this.showError('下载失败');
            }
        } catch (error) {
            this.showError('下载请求失败: ' + error.message);
        }
    }

    downloadCurrentImage() {
        if (!this.currentModalImageData) return;
        
        if (this.currentModalImageData.source && this.currentModalImageData.source !== '本地') {
            const index = this.currentResults.findIndex(r => r.id === this.currentModalImageData.id);
            if (index >= 0) {
                this.downloadExternalImage(index);
            }
        } else {
            const index = this.currentResults.findIndex(r => r.id === this.currentModalImageData.id);
            if (index >= 0) {
                this.downloadImage(index);
            }
        }
    }

    copyImagePath() {
        if (!this.currentModalImageData) {
            this.showError('无路径信息');
            return;
        }

        if (this.currentModalImageData.source && this.currentModalImageData.source !== '本地') {
            navigator.clipboard.writeText(this.currentModalImageData.image_url).then(() => {
                this.showSuccess('图片URL已复制到剪贴板');
            }).catch(() => {
                this.showError('复制失败');
            });
        } else {
            if (!this.currentModalImageData.image_path) {
                this.showError('无路径信息');
                return;
            }
            navigator.clipboard.writeText(this.currentModalImageData.image_path).then(() => {
                this.showSuccess('路径已复制到剪贴板');
            }).catch(() => {
                this.showError('复制失败');
            });
        }
    }

    copyImageUrl() {
        if (!this.currentModalImageData) {
            this.showError('无URL信息');
            return;
        }

        const url = this.currentModalImageData.url || this.currentModalImageData.image_url;
        if (!url) {
            this.showError('无URL信息');
            return;
        }

        navigator.clipboard.writeText(url).then(() => {
            this.showSuccess('URL已复制到剪贴板');
        }).catch(() => {
            this.showError('复制失败');
        });
    }

    async searchSimilarToThis(customCount = 9) {
        if (!this.currentModalImageData) {
            this.showError('无法进行相似搜索：缺少图片信息');
            return;
        }
    
        // 检查是否为外部图片源
        if (this.currentModalImageData.source && this.currentModalImageData.source !== '本地') {
            this.showError('相似搜索功能仅适用于本地数据库中的图片');
            return;
        }
    
        const imageId = this.currentModalImageData.id;
        
        if (!imageId) {
            this.showError('图片ID缺失，无法进行相似搜索');
            return;
        }
    
        this.closeModal();
        this.showLoading(`正在搜索与此图片相似的 ${customCount} 张图片...`);
    
        try {
            const response = await fetch('/api/search/similar_by_id', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_id: imageId,
                    top_k: customCount,
                    exclude_self: true
                })
            });
    
            const result = await response.json();
    
            if (result.success) {
                this.currentResults = result.data.results;
                this.displayResults(result.data);
                this.showSuccess(`找到 ${result.data.results.length} 张相似图片`);
                
                // 滚动到结果区域
                setTimeout(() => {
                    const resultsSection = document.getElementById('resultsSection');
                    if (resultsSection) {
                        resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }
                }, 100);
            } else {
                this.showError('相似图搜索失败: ' + result.error);
            }
    
        } catch (error) {
            this.showError('相似图搜索请求失败: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }

    async searchSimilarToResult(index) {
        if (!this.currentResults[index]) return;
        
        const result = this.currentResults[index];
        const originalModalData = this.currentModalImageData;
        this.currentModalImageData = result;
        
        try {
            await this.searchSimilarToThis();
        } finally {
            this.currentModalImageData = originalModalData;
        }
    }

    async downloadAllImages() {
        if (this.currentSearchType === 'ai') {
            const validResults = this.currentResults;
            
            if (validResults.length === 0) {
                this.showError('没有可下载的图片');
                return;
            }

            if (validResults.length > 10) {
                if (!confirm(`将下载 ${validResults.length} 张外部图片，可能需要较长时间，确认继续？`)) {
                    return;
                }
            }

            this.showInfo(`开始批量下载 ${validResults.length} 张图片...`);

            for (let i = 0; i < validResults.length; i++) {
                try {
                    await this.downloadExternalImage(i);
                    await new Promise(resolve => setTimeout(resolve, 1000));
                } catch (error) {
                    console.error(`下载图片 ${validResults[i].title} 失败:`, error);
                }
            }
        } else {
            const validResults = this.currentResults.filter(r => r.image_exists);
            
            if (validResults.length === 0) {
                this.showError('没有可下载的图片');
                return;
            }

            if (validResults.length > 20) {
                if (!confirm(`将下载 ${validResults.length} 张图片，可能需要较长时间，确认继续？`)) {
                    return;
                }
            }

            this.showInfo(`开始批量下载 ${validResults.length} 张图片...`);

            for (let i = 0; i < validResults.length; i++) {
                const result = validResults[i];
                const index = this.currentResults.findIndex(r => r.id === result.id);
                
                try {
                    await this.downloadImage(index);
                    await new Promise(resolve => setTimeout(resolve, 500));
                } catch (error) {
                    console.error(`下载图片 ${result.filename} 失败:`, error);
                }
            }
        }
    }

    showLoading(message = '加载中...') {
        const loadingText = document.getElementById('loadingText');
        const loadingArea = document.getElementById('loadingArea');
        
        if (loadingText) loadingText.textContent = message;
        if (loadingArea) loadingArea.classList.remove('hidden');
        this.clearResults();
    }

    hideLoading() {
        const loadingArea = document.getElementById('loadingArea');
        if (loadingArea) loadingArea.classList.add('hidden');
    }

    clearResults() {
        const resultsSection = document.getElementById('resultsSection');
        const noResults = document.getElementById('noResults');
        const queryAnalysis = document.getElementById('queryAnalysis');
        const welcomeView = document.getElementById('welcomeView');
        
        if (resultsSection) resultsSection.classList.add('hidden');
        if (noResults) noResults.classList.add('hidden');
        if (queryAnalysis) queryAnalysis.classList.add('hidden');
        if (welcomeView) welcomeView.classList.remove('hidden'); // 显示欢迎界面
        
        // 清除AI搜索信息
        const aiInfoDiv = document.getElementById('aiSearchInfo');
        if (aiInfoDiv) {
            aiInfoDiv.remove();
        }
        
        this.currentResults = [];
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showSuccess(message) {
        this.showNotification(message, 'success');
    }

    showInfo(message) {
        this.showNotification(message, 'info');
    }

    showNotification(message, type = 'info', duration = 3000) {
        const colors = {
            error: 'from-red-500 to-red-600',
            success: 'from-green-500 to-green-600', 
            info: 'from-blue-500 to-blue-600'
        };

        const icons = {
            error: 'fas fa-exclamation-circle',
            success: 'fas fa-check-circle',
            info: 'fas fa-info-circle'
        };

        const notification = document.createElement('div');
        notification.className = `fixed top-6 right-6 bg-gradient-to-r ${colors[type]} text-white px-6 py-4 rounded-2xl shadow-2xl z-50 transform translate-x-full transition-all duration-300 max-w-sm`;
        notification.innerHTML = `
            <div class="flex items-start">
                <i class="${icons[type]} mr-3 mt-0.5 text-lg"></i>
                <div class="flex-1">
                    <div class="font-medium">${type === 'error' ? '错误' : type === 'success' ? '成功' : '提示'}</div>
                    <div class="text-sm opacity-90 mt-1">${message}</div>
                </div>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-3 text-white hover:text-gray-200 transition-colors">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        `;

        document.body.appendChild(notification);

        // 显示动画
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
        }, 10);

        // 自动消失
        if (duration > 0) {
            setTimeout(() => {
                notification.style.transform = 'translateX(100%)';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }, duration);
        }

        return notification;
    }

    // 新增：删除上传的图片
    removeUploadedImage() {
        const uploadArea = document.getElementById('uploadArea');
        const previewArea = document.getElementById('previewArea');
        const imageInput = document.getElementById('imageInput');
        const imageSearchBtn = document.getElementById('imageSearchBtn');
        
        if (uploadArea) uploadArea.style.display = 'block';
        if (previewArea) previewArea.classList.add('hidden');
        if (imageInput) imageInput.value = ''; // 清空文件选择
        if (imageSearchBtn) imageSearchBtn.disabled = true;
        
        this.showSuccess('图片已删除');
    }

    // 新增：重新选择图片
    reSelectImage() {
        const imageInput = document.getElementById('imageInput');
        if (imageInput) {
            imageInput.click();
        }
    }

    // 新增：格式化文件大小
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // 修改 performImageSearch 方法，添加验证
    async performImageSearch() {
        const imageInput = document.getElementById('imageInput');
        if (!imageInput || !imageInput.files[0]) {
            this.showError('请先选择图片');
            return;
        }

        const imageCustomResultCount = document.getElementById('imageCustomResultCount');
        const topK = parseInt(imageCustomResultCount ? imageCustomResultCount.value : 9) || 9;
        const formData = new FormData();
        formData.append('image', imageInput.files[0]);
        formData.append('top_k', topK);

        this.showLoading('正在执行以图搜图...');

        try {
            const response = await fetch('/api/search/image', {
                method: 'POST',
                body: formData
            });

            const result = await response.json();
            
            if (result.success) {
                this.currentResults = result.data.results;
                this.displayResults(result.data);
                this.showSuccess(`找到 ${result.data.results.length} 张相似图片`);
            } else {
                this.showError(result.error);
            }
        } catch (error) {
            this.showError('图片搜索失败: ' + error.message);
        } finally {
            this.hideLoading();
        }
    }
}

// 初始化应用
let app;
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        app = new ImageSearchApp();
    });
} else {
    app = new ImageSearchApp();
}