/**
 * FoxCode Desktop - Monaco Editor 通信和初始化逻辑
 * 
 * 本文件负责：
 * 1. 初始化 Monaco Editor 实例
 * 2. 处理与主应用（NiceGUI）的双向通信（postMessage）
 * 3. 管理编辑器状态（当前文件、语言、主题等）
 * 4. 提供文件操作接口（加载、保存、格式化）
 * 
 * @author FoxCode Team
 * @version 1.0.0
 * @license AGPL-3.0-or-later
 */

// ==================== 全局变量 ====================

/** @type {monaco.editor.IStandaloneCodeEditor} Monaco 编辑器实例 */
let editor = null;

/** @type {string|null} 当前打开的文件路径 */
let currentFile = null;

/** @type {string} 当前编程语言标识符 */
let currentLanguage = 'python';

/** @type {boolean} 是否已初始化完成 */
let isInitialized = false;

/** @type {Object} 编辑器配置 */
let editorConfig = {
    theme: 'vs-dark',
    fontSize: 14,
    fontFamily: 'Consolas, "Courier New", monospace',
    minimap: { enabled: true },
    lineNumbers: 'on',
    roundedSelection: false,
    scrollBeyondLastLine: false,
    readOnly: false,
    wordWrap: 'on',
    folding: true,
    bracketPairColorization: { enabled: true },
    automaticLayout: true,
    tabSize: 4,
    insertSpaces: true,
    renderWhitespace: 'selection',
    guides: {
        indentation: true,
        bracketPairs: true
    }
};

// ==================== 语言映射表 ====================

/**
 * 文件扩展名到 Monaco 语言标识符的映射
 * 支持主流编程语言和常见文件类型
 */
const LANGUAGE_MAP = {
    // Python
    'py': 'python',
    'pyw': 'python',
    'pyx': 'python',
    
    // JavaScript/TypeScript
    'js': 'javascript',
    'jsx': 'javascript',
    'mjs': 'javascript',
    'cjs': 'javascript',
    'ts': 'typescript',
    'tsx': 'typescript',
    
    // Web 技术
    'html': 'html',
    'htm': 'html',
    'css': 'css',
    'scss': 'scss',
    'sass': 'scss',
    'less': 'less',
    'vue': 'html',
    'svelte': 'html',
    
    // 数据格式
    'json': 'json',
    'jsonc': 'json',
    'xml': 'xml',
    'yaml': 'yaml',
    'yml': 'yaml',
    'toml': 'ini',  // Monaco 没有 toml 支持，使用 ini
    'ini': 'ini',
    'cfg': 'ini',
    'conf': 'ini',
    
    // Markdown 和文档
    'md': 'markdown',
    'markdown': 'markdown',
    'rst': 'plaintext',
    'txt': 'plaintext',
    'log': 'plaintext',
    
    // Shell 脚本
    'sh': 'shell',
    'bash': 'shell',
    'zsh': 'shell',
    'fish': 'shell',
    'ps1': 'powershell',
    'bat': 'bat',
    'cmd': 'bat',
    
    // 编程语言
    'java': 'java',
    'kt': 'kotlin',
    'kts': 'kotlin',
    'c': 'c',
    'h': 'c',
    'cpp': 'cpp',
    'hpp': 'cpp',
    'cc': 'cpp',
    'cxx': 'cpp',
    'cs': 'csharp',
    'go': 'go',
    'rs': 'rust',
    'rb': 'ruby',
    'php': 'php',
    'swift': 'swift',
    'scala': 'scala',
    'r': 'r',
    'lua': 'lua',
    'pl': 'perl',
    'pm': 'perl',
    'ex': 'elixir',
    'exs': 'elixir',
    'erl': 'erlang',
    'hrl': 'erlang',
    
    // 数据科学
    'ipynb': 'json',  // Jupyter notebook
    
    // SQL 和数据库
    'sql': 'sql',
    
    // 配置文件
    'dockerfile': 'dockerfile',
    'makefile': 'plaintext',
    'cmake': 'cmake',
    
    // 其他
    'graphql': 'graphql',
    'proto': 'protobuf',
    'env': 'plaintext',
    'gitignore': 'plaintext',
    'editorconfig': 'yaml'
};

// ==================== 初始化函数 ====================

/**
 * 初始化 Monaco Editor
 * 从 URL 参数获取初始配置，创建编辑器实例并设置事件监听器
 */
async function initEditor() {
    console.log('[Monaco] 开始初始化编辑器...');
    
    try {
        // 显示加载指示器
        showLoading(true);
        
        // 从 URL 获取参数
        const urlParams = new URLSearchParams(window.location.search);
        const filePath = urlParams.get('file') || '';
        const language = urlParams.get('lang') || 'python';
        const theme = urlParams.get('theme') || 'vs-dark';
        const readonly = urlParams.get('readonly') === 'true';
        
        console.log(`[Monaco] 初始参数: file=${filePath}, lang=${language}, theme=${theme}`);
        
        // 更新配置
        currentLanguage = language;
        if (theme) {
            editorConfig.theme = theme;
        }
        if (readonly) {
            editorConfig.readOnly = true;
        }
        
        // 配置 Monaco 加载器
        require.config({
            paths: {
                vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs'
            }
        });
        
        // 异步加载 Monaco
        await new Promise((resolve, reject) => {
            require(['vs/editor/editor.main'], () => {
                resolve();
            }, (error) => {
                reject(error);
            });
        });
        
        console.log('[Monaco] Monaco 核心库加载完成');
        
        // 创建编辑器实例
        createEditorInstance();
        
        // 设置消息监听器
        setupMessageListener();
        
        // 设置窗口大小变化监听
        setupResizeListener();
        
        // 如果有初始文件路径，请求加载
        if (filePath) {
            loadFile(filePath);
        } else {
            // 显示欢迎内容
            showWelcomeContent();
        }
        
        // 隐藏加载指示器
        showLoading(false);
        
        isInitialized = true;
        console.log('[Monaco] 编辑器初始化完成');
        
        // 通知父窗口初始化完成
        postMessageToParent({
            type: 'editor-ready',
            config: editorConfig
        });
        
    } catch (error) {
        console.error('[Monaco] 初始化失败:', error);
        showError('编辑器初始化失败: ' + error.message);
        showLoading(false);
    }
}

/**
 * 创建 Monaco 编辑器 DOM 实例
 */
function createEditorInstance() {
    const container = document.getElementById('editor-container');
    
    if (!container) {
        throw new Error('找不到编辑器容器元素 #editor-container');
    }
    
    // 创建编辑器
    editor = monaco.editor.create(container, {
        value: '',  // 初始值为空，稍后通过消息加载
        language: currentLanguage,
        theme: editorConfig.theme,
        ...editorConfig
    });
    
    console.log(`[Monaco] 编辑器实例已创建，语言: ${currentLanguage}`);
    
    // 监听内容变更事件
    editor.onDidChangeModelContent((event) => {
        handleContentChange(event);
    });
    
    // 监听光标位置变更（更新状态栏）
    editor.onDidChangeCursorPosition((event) => {
        updateStatusBar(event.position);
    });
    
    // 监听焦点事件
    editor.onDidFocusEditorText(() => {
        postMessageToParent({ type: 'focus' });
    });
    
    // 监听失焦事件
    editor.onDidBlurEditorText(() => {
        postMessageToParent({ type: 'blur' });
    });
}

// ==================== 消息通信系统 ====================

/**
 * 设置来自父窗口的消息监听器
 * 处理主应用发送的各种命令和数据
 */
function setupMessageListener() {
    window.addEventListener('message', (event) => {
        // 安全检查：验证来源（生产环境应限制为具体域名）
        // if (event.origin !== window.location.origin) return;
        
        const data = event.data;
        
        if (!data || !data.type) {
            console.warn('[Monaco] 收到无效消息:', data);
            return;
        }
        
        console.log(`[Monaco] 收到消息: ${data.type}`, data);
        
        switch (data.type) {
            case 'file-content':
                handleFileContent(data);
                break;
                
            case 'save-file':
                handleSaveRequest();
                break;
                
            case 'update-config':
                handleConfigUpdate(data.config);
                break;
                
            case 'format-code':
                handleFormatCode();
                break;
                
            case 'load-file':
                handleLoadFile(data.file, data.language);
                break;
                
            case 'set-theme':
                handleSetTheme(data.theme);
                break;
                
            case 'set-language':
                handleSetLanguage(data.language);
                break;
                
            case 'get-content':
                handleGetContent();
                break;
                
            case 'undo':
                editor?.trigger('external', 'undo', null);
                break;
                
            case 'redo':
                editor?.trigger('external', 'redo', null);
                break;
                
            default:
                console.warn(`[Monaco] 未知的消息类型: ${data.type}`);
        }
    });
    
    console.log('[Monaco] 消息监听器已设置');
}

/**
 * 向父窗口发送消息
 * 
 * @param {Object} message - 要发送的消息对象
 * @param {string} message.type - 消息类型
 * @param {*} [message.*] - 其他数据字段
 */
function postMessageToParent(message) {
    try {
        if (window.parent && window.parent !== window) {
            window.parent.postMessage(message, '*');
            console.log(`[Monaco] 发送消息: ${message.type}`);
        }
    } catch (error) {
        console.error('[Monaco] 发送消息失败:', error);
    }
}

// ==================== 消息处理函数 ====================

/**
 * 处理接收到的文件内容
 * 将内容设置到编辑器中
 * 
 * @param {Object} data - 消息数据
 * @param {string} data.file - 文件路径
 * @param {string} data.content - 文件内容
 */
function handleFileContent(data) {
    if (!editor) {
        console.error('[Monaco] 编辑器未初始化');
        return;
    }
    
    const { file, content } = data;
    
    console.log(`[Monaco] 接收文件内容: ${file} (${content.length} 字符)`);
    
    // 检测语言（如果未指定）
    let language = currentLanguage;
    if (file) {
        const ext = file.split('.').pop()?.toLowerCase() || '';
        language = getLanguageFromExtension(ext) || currentLanguage;
    }
    
    // 创建或更新模型
    const model = monaco.editor.createModel(content, language);
    editor.setModel(model);
    
    // 更新状态
    currentFile = file;
    currentLanguage = language;
    
    // 更新状态栏
    updateStatusBarLanguage(language);
    
    // 通知加载完成
    postMessageToParent({
        type: 'file-loaded',
        file: file,
        language: language,
        lineCount: model.getLineCount()
    });
}

/**
 * 处理保存请求
 * 获取编辑器内容并发送给父窗口保存
 */
function handleSaveRequest() {
    if (!editor || !currentFile) {
        console.warn('[Monaco] 无法保存：编辑器未初始化或无当前文件');
        return;
    }
    
    const content = editor.getValue();
    
    console.log(`[Monaco] 请求保存文件: ${currentFile} (${content.length} 字符)`);
    
    postMessageToParent({
        type: 'save-content',
        file: currentFile,
        content: content
    });
}

/**
 * 处理编辑器配置更新
 * 
 * @param {Object} config - 新的配置项
 */
function handleConfigUpdate(config) {
    if (!editor || !config) return;
    
    console.log('[Monaco] 更新配置:', config);
    
    // 合并配置
    Object.assign(editorConfig, config);
    
    // 应用到编辑器
    editor.updateOptions(config);
    
    // 特殊处理主题
    if (config.theme) {
        monaco.editor.setTheme(config.theme);
    }
}

/**
 * 处理代码格式化请求
 */
function handleFormatCode() {
    if (!editor) return;
    
    console.log('[Monaco] 格式化代码');
    
    // 执行格式化操作
    editor.getAction('editor.action.formatDocument')?.run();
}

/**
 * 处理加载文件请求
 * 
 * @param {string} filePath - 文件路径
 * @param {string} [language] - 语言标识符
 */
function handleLoadFile(filePath, language) {
    if (!filePath) return;
    
    console.log(`[Monaco] 加载文件: ${filePath}`);
    
    currentFile = filePath;
    if (language) {
        currentLanguage = language;
    }
    
    // 向父窗口请求文件内容
    postMessageToParent({
        type: 'request-file',
        file: filePath
    });
}

/**
 * 处理主题切换
 * 
 * @param {string} theme - 主题名称
 */
function handleSetTheme(theme) {
    if (!theme || !monaco) return;
    
    console.log(`[Monaco] 切换主题: ${theme}`);
    
    monaco.editor.setTheme(theme);
    editorConfig.theme = theme;
}

/**
 * 处理语言切换
 * 
 * @param {string} language - 语言标识符
 */
function handleSetLanguage(language) {
    if (!editor || !language) return;
    
    console.log(`[Monaco] 切换语言: ${language}`);
    
    const model = editor.getModel();
    if (model) {
        const newModel = monaco.editor.createModel(model.getValue(), language);
        editor.setModel(newModel);
        currentLanguage = language;
        
        updateStatusBarLanguage(language);
    }
}

/**
 * 处理获取内容请求
 */
function handleGetContent() {
    if (!editor) return;
    
    const content = editor.getValue();
    
    postMessageToParent({
        type: 'content-response',
        file: currentFile,
        content: content
    });
}

// ==================== 事件处理函数 ====================

/**
 * 处理编辑器内容变更
 * 当用户修改代码时触发，通知父窗口
 * 
 * @param {Object} event - 变更事件对象
 */
function handleContentChange(event) {
    if (!editor) return;
    
    const content = editor.getValue();
    
    // 防抖处理：避免频繁发送消息
    debounce(() => {
        postMessageToParent({
            type: 'content-changed',
            file: currentFile,
            content: content,
            changeEvent: {
                isDirty: editor.isDirty(),
                lineCount: editor.getModel()?.getLineCount() || 0
            }
        });
    }, 150)();
}

// ==================== 工具函数 ====================

/**
 * 根据文件扩展名获取 Monaco 语言标识符
 * 
 * @param {string} extension - 文件扩展名（不含点号）
 * @returns {string} Monaco 语言标识符
 */
function getLanguageFromExtension(extension) {
    if (!extension) return 'plaintext';
    
    return LANGUAGE_MAP[extension.toLowerCase()] || 'plaintext';
}

/**
 * 加载指定文件
 * 向父窗口请求文件内容
 * 
 * @param {string} filePath - 文件的绝对或相对路径
 */
function loadFile(filePath) {
    if (!filePath) {
        console.warn('[Monaco] 文件路径为空');
        return;
    }
    
    console.log(`[Monaco] 请求加载文件: ${filePath}`);
    
    currentFile = filePath;
    
    // 自动检测语言
    const ext = filePath.split('.').pop()?.toLowerCase() || '';
    currentLanguage = getLanguageFromExtension(ext);
    
    // 向父窗口请求文件内容
    postMessageToParent({
        type: 'request-file',
        file: filePath
    });
}

/**
 * 显示/隐藏加载指示器
 * 
 * @param {boolean} show - 是否显示
 */
function showLoading(show) {
    const indicator = document.getElementById('loading-indicator');
    if (indicator) {
        indicator.style.display = show ? 'flex' : 'none';
    }
}

/**
 * 显示错误消息
 * 
 * @param {string} message - 错误消息文本
 */
function showError(message) {
    const errorEl = document.getElementById('error-message');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
        
        // 5 秒后自动隐藏
        setTimeout(() => {
            errorEl.style.display = 'none';
        }, 5000);
    }
    
    console.error('[Monaco]', message);
}

/**
 * 显示欢迎内容（当没有打开文件时）
 */
function showWelcomeContent() {
    if (!editor) return;
    
    const welcomeText = `// Welcome to FoxCode Desktop!
// 
// 这是一个基于 Monaco Editor 的代码编辑器。
// 
// 功能特性：
// - 语法高亮（支持 ${Object.keys(LANGUAGE_MAP).length} 种语言）
// - 智能代码补全
// - 代码折叠
// - 多光标编辑
// - 查找替换
//
// 快捷键：
// Ctrl+S  - 保存文件
// Ctrl+Z  - 撤销
// Ctrl+Y  - 重做
// Ctrl+F  - 查找
// Ctrl+H  - 替换
// Shift+Alt+F - 格式化代码
//
// 请从左侧文件浏览器中选择一个文件开始编辑。
`;
    
    editor.setValue(welcomeText);
    
    // 设置为只读模式
    editor.updateOptions({ readOnly: true });
}

/**
 * 更新状态栏信息
 * 
 * @param {Object} position - 光标位置 {lineNumber, column}
 */
function updateStatusBar(position) {
    const posEl = document.getElementById('status-position');
    if (posEl && position) {
        posEl.textContent = `行 ${position.lineNumber}, 列 ${position.column}`;
    }
}

/**
 * 更新状态栏的语言显示
 * 
 * @param {string} language - 语言名称
 */
function updateStatusBarLanguage(language) {
    const langEl = document.getElementById('status-language');
    if (langEl) {
        // 语言名首字母大写
        const displayName = language.charAt(0).toUpperCase() + language.slice(1);
        langEl.textContent = displayName;
    }
}

/**
 * 防抖函数 - 限制函数调用频率
 * 
 * @param {Function} func - 要防抖的函数
 * @param {number} wait - 等待时间（毫秒）
 * @returns {Function} 防抖后的函数
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * 设置窗口大小变化监听器
 * 确保编辑器在窗口调整大小时正确重绘
 */
function setupResizeListener() {
    let resizeTimeout;
    
    window.addEventListener('resize', () => {
        // 防抖处理
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            if (editor) {
                editor.layout();
                console.log('[Monaco] 编辑器布局已调整');
            }
        }, 100);
    });
    
    console.log('[Monaco] 窗口尺寸监听器已设置');
}

// ==================== 启动入口 ====================

/**
 * DOM 加载完成后初始化编辑器
 */
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEditor);
} else {
    // DOM 已经加载完成
    initEditor();
}

// 导出全局函数（供调试使用）
window.monacoEditor = {
    getEditor: () => editor,
    getCurrentFile: () => currentFile,
    getLanguage: () => currentLanguage,
    loadFile: loadFile,
    saveFile: handleSaveRequest,
    formatCode: handleFormatCode
};

console.log('[Monaco] editor.js 已加载');
