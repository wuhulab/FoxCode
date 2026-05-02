"""
FoxCode 编码检测模块 - 智能文件编码检测

这个文件提供文件编码检测功能:
1. 自动检测：尝试多种编码，找到正确的编码格式
2. 多编码支持：支持 Unicode、中文、日文、韩文等编码
3. BOM 检测：检测带 BOM 的 UTF 文件
4. 回退机制：检测失败时回退到默认编码

支持的编码（按检测优先级排序）:
- Unicode: utf-8, utf-8-sig, utf-16, utf-32
- 中文: gbk, gb2312, gb18030, big5
- 日文: shift_jis, cp932, euc-jp
- 韩文: euc-kr, cp949
- 西文: iso-8859-1, cp1252

使用方式:
    from foxcode.utils.encoding import detect_encoding

    encoding = detect_encoding(Path("file.txt"))
    content = Path("file.txt").read_text(encoding=encoding)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# 支持的编码列表（按检测优先级排序）
SUPPORTED_ENCODINGS = [
    # Unicode 编码
    "utf-8",
    "utf-8-sig",      # 带 BOM 的 UTF-8
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "utf-32",
    "utf-32-le",
    "utf-32-be",

    # 中文编码
    "gbk",            # 简体中文 Windows
    "gb2312",         # 简体中文
    "gb18030",        # 中文超集
    "big5",           # 繁体中文
    "big5hkscs",      # 繁体中文（香港）

    # 日文编码
    "shift_jis",      # 日文
    "cp932",          # 日文 Windows
    "euc-jp",         # 日文

    # 韩文编码
    "euc-kr",         # 韩文
    "cp949",          # 韩文 Windows

    # 西欧编码
    "iso-8859-1",     # Latin-1
    "iso-8859-2",     # Latin-2
    "iso-8859-3",     # Latin-3
    "iso-8859-4",     # Latin-4
    "iso-8859-5",     # Cyrillic
    "iso-8859-6",     # Arabic
    "iso-8859-7",     # Greek
    "iso-8859-8",     # Hebrew
    "iso-8859-9",     # Latin-5
    "iso-8859-10",    # Latin-6
    "iso-8859-13",    # Latin-7
    "iso-8859-14",    # Latin-8
    "iso-8859-15",    # Latin-9
    "iso-8859-16",    # Latin-10

    # Windows 编码
    "cp1250",         # Windows 中欧
    "cp1251",         # Windows Cyrillic
    "cp1252",         # Windows 西欧
    "cp1253",         # Windows 希腊
    "cp1254",         # Windows 土耳其
    "cp1255",         # Windows 希伯来
    "cp1256",         # Windows 阿拉伯
    "cp1257",         # Windows 波罗的海
    "cp1258",         # Windows 越南

    # 其他编码
    "koi8-r",         # 俄文
    "koi8-u",         # 乌克兰文
    "mac-roman",      # Mac Roman
    "mac-cyrillic",   # Mac Cyrillic
]


class EncodingDetector:
    """
    编码检测器
    
    智能检测文件编码，支持多种检测策略
    """

    def __init__(self):
        """初始化编码检测器"""
        self._chardet_available = self._check_chardet()

    def _check_chardet(self) -> bool:
        """检查 chardet 库是否可用"""
        try:
            import chardet
            return True
        except ImportError:
            logger.debug("chardet 库不可用，将使用内置检测方法")
            return False

    def detect(self, data: bytes) -> tuple[str, float]:
        """
        检测字节流的编码
        
        Args:
            data: 原始字节数据
            
        Returns:
            (编码名称, 置信度) 元组
        """
        # 空数据
        if not data:
            return ("utf-8", 1.0)

        # 1. 检查 BOM（字节顺序标记）
        encoding, confidence = self._check_bom(data)
        if encoding:
            return (encoding, confidence)

        # 2. 使用 chardet 库（如果可用）
        if self._chardet_available:
            encoding, confidence = self._detect_with_chardet(data)
            if confidence > 0.9:
                return (encoding, confidence)

        # 3. 尝试常见编码
        encoding, confidence = self._try_common_encodings(data)
        if encoding:
            return (encoding, confidence)

        # 4. 使用 chardet 结果（即使置信度较低）
        if self._chardet_available:
            return (encoding, confidence)

        # 5. 默认返回 UTF-8
        return ("utf-8", 0.5)

    def _check_bom(self, data: bytes) -> tuple[str | None, float]:
        """
        检查 BOM（字节顺序标记）
        
        Args:
            data: 原始字节数据
            
        Returns:
            (编码名称, 置信度) 或 (None, 0)
        """
        # BOM 标记及其对应的编码
        boms = [
            (b"\xef\xbb\xbf", "utf-8-sig"),      # UTF-8 BOM
            (b"\xff\xfe\x00\x00", "utf-32-le"),  # UTF-32 LE
            (b"\x00\x00\xfe\xff", "utf-32-be"),  # UTF-32 BE
            (b"\xff\xfe", "utf-16-le"),          # UTF-16 LE
            (b"\xfe\xff", "utf-16-be"),          # UTF-16 BE
        ]

        for bom, encoding in boms:
            if data.startswith(bom):
                logger.debug(f"检测到 BOM: {encoding}")
                return (encoding, 1.0)

        return (None, 0.0)

    def _detect_with_chardet(self, data: bytes) -> tuple[str, float]:
        """
        使用 chardet 库检测编码
        
        Args:
            data: 原始字节数据
            
        Returns:
            (编码名称, 置信度)
        """
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get("encoding", "utf-8")
            confidence = result.get("confidence", 0.0)

            # 规范化编码名称
            encoding = self._normalize_encoding(encoding)

            logger.debug(f"chardet 检测结果: {encoding} (置信度: {confidence:.2f})")
            return (encoding, confidence)
        except Exception as e:
            logger.warning(f"chardet 检测失败: {e}")
            return ("utf-8", 0.0)

    def _try_common_encodings(self, data: bytes) -> tuple[str | None, float]:
        """
        尝试常见编码
        
        Args:
            data: 原始字节数据
            
        Returns:
            (编码名称, 置信度) 或 (None, 0)
        """
        # 优先尝试的编码
        priority_encodings = [
            "utf-8",
            "utf-8-sig",
            "gbk",
            "gb18030",
            "big5",
            "shift_jis",
            "euc-kr",
            "iso-8859-1",
        ]

        for encoding in priority_encodings:
            try:
                decoded = data.decode(encoding)
                # 检查解码结果是否合理（没有过多的替换字符）
                replacement_count = decoded.count("\ufffd")
                total_chars = len(decoded)

                if total_chars > 0:
                    valid_ratio = 1 - (replacement_count / total_chars)
                    if valid_ratio > 0.95:
                        confidence = valid_ratio
                        logger.debug(f"编码 {encoding} 验证成功 (有效率: {valid_ratio:.2%})")
                        return (encoding, confidence)
            except (UnicodeDecodeError, LookupError):
                continue

        return (None, 0.0)

    def _normalize_encoding(self, encoding: str) -> str:
        """
        规范化编码名称
        
        Args:
            encoding: 原始编码名称
            
        Returns:
            规范化后的编码名称
        """
        # 编码别名映射
        aliases = {
            "ascii": "utf-8",  # ASCII 兼容 UTF-8
            "gb2312": "gbk",   # GBK 是 GB2312 的超集
            "gb18030": "gb18030",
            "big5": "big5",
            "shift-jis": "shift_jis",
            "shift_jis": "shift_jis",
            "euc-kr": "euc-kr",
            "iso-8859-1": "iso-8859-1",
            "latin-1": "iso-8859-1",
            "latin1": "iso-8859-1",
        }

        encoding_lower = encoding.lower()
        return aliases.get(encoding_lower, encoding_lower)

    def decode(self, data: bytes, encoding: str | None = None) -> tuple[str, str]:
        """
        解码字节数据
        
        Args:
            data: 原始字节数据
            encoding: 指定编码（如果为 None 则自动检测）
            
        Returns:
            (解码后的文本, 实际使用的编码)
        """
        if not data:
            return ("", "utf-8")

        if encoding:
            # 使用指定编码
            try:
                return (data.decode(encoding), encoding)
            except (UnicodeDecodeError, LookupError):
                logger.warning(f"指定编码 {encoding} 解码失败，尝试自动检测")

        # 自动检测编码
        detected_encoding, confidence = self.detect(data)

        try:
            return (data.decode(detected_encoding), detected_encoding)
        except (UnicodeDecodeError, LookupError):
            # 检测失败，尝试其他编码
            for fallback_encoding in SUPPORTED_ENCODINGS:
                try:
                    return (data.decode(fallback_encoding), fallback_encoding)
                except (UnicodeDecodeError, LookupError):
                    continue

            # 所有编码都失败，使用 replace 模式
            return (data.decode("utf-8", errors="replace"), "utf-8")


# 全局编码检测器实例
encoding_detector = EncodingDetector()


def detect_encoding(data: bytes) -> tuple[str, float]:
    """
    检测字节流的编码
    
    Args:
        data: 原始字节数据
        
    Returns:
        (编码名称, 置信度) 元组
    """
    return encoding_detector.detect(data)


def decode_bytes(data: bytes, encoding: str | None = None) -> tuple[str, str]:
    """
    解码字节数据
    
    Args:
        data: 原始字节数据
        encoding: 指定编码（如果为 None 则自动检测）
        
    Returns:
        (解码后的文本, 实际使用的编码)
    """
    return encoding_detector.decode(data, encoding)


def get_supported_encodings() -> list[str]:
    """
    获取支持的编码列表
    
    Returns:
        编码名称列表
    """
    return SUPPORTED_ENCODINGS.copy()
