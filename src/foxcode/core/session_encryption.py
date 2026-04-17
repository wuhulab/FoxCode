"""
FoxCode 会话加密模块

提供会话数据的加密存储功能，保护敏感信息

安全要求：
- 必须安装 cryptography 库
- 使用 Fernet 对称加密（AES-128-CBC + HMAC）
- 密钥文件权限设置为 600
"""

from __future__ import annotations

import base64
import json
import logging
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.error(
        "cryptography 库未安装。会话加密功能需要此库。"
        "请安装: pip install cryptography"
    )


@dataclass
class EncryptionConfig:
    """
    加密配置
    
    Attributes:
        enabled: 是否启用加密
        key_file: 密钥文件路径（默认存储在用户主目录）
        auto_generate_key: 是否自动生成密钥
    """
    enabled: bool = True
    key_file: str = field(default_factory=lambda: str(Path.home() / ".foxcode" / "session_key"))
    auto_generate_key: bool = True


class SessionEncryptor:
    """
    会话加密器
    
    提供会话数据的加密和解密功能
    """

    def __init__(self, config: EncryptionConfig | None = None):
        """
        初始化加密器
        
        Args:
            config: 加密配置
        """
        self.config = config or EncryptionConfig()
        self._key: bytes | None = None
        self._fernet: Any = None

        if self.config.enabled:
            self._initialize_encryption()

    def _initialize_encryption(self) -> None:
        """
        初始化加密系统
        
        密钥文件默认存储在用户主目录，而不是工作目录，以防止密钥与加密数据在同一位置
        
        Raises:
            RuntimeError: 如果 cryptography 库未安装
        """
        if not CRYPTO_AVAILABLE:
            raise RuntimeError(
                "会话加密功能需要 cryptography 库。"
                "请安装: pip install cryptography"
            )

        key_path = Path(self.config.key_file)
        key_path.parent.mkdir(parents=True, exist_ok=True)

        if key_path.exists():
            try:
                self._load_key(key_path)
                logger.debug("已加载现有加密密钥")
            except Exception as e:
                logger.warning(f"加载密钥失败: {e}")
                if self.config.auto_generate_key:
                    self._generate_and_save_key(key_path)
                else:
                    raise RuntimeError(f"无法加载加密密钥: {e}")
        else:
            if self.config.auto_generate_key:
                self._generate_and_save_key(key_path)
            else:
                raise RuntimeError(
                    "密钥文件不存在且未启用自动生成。"
                    "请手动创建密钥文件或启用 auto_generate_key 配置。"
                )

    def _load_key(self, key_path: Path) -> None:
        """
        加载密钥
        
        Args:
            key_path: 密钥文件路径
            
        Raises:
            RuntimeError: 如果 cryptography 库未安装
        """
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("加密功能需要 cryptography 库")

        with open(key_path, "rb") as f:
            key_data = f.read()

        self._key = base64.urlsafe_b64decode(key_data)
        self._fernet = Fernet(key_data)

    def _generate_and_save_key(self, key_path: Path) -> None:
        """
        生成并保存密钥
        
        Args:
            key_path: 密钥文件路径
            
        Raises:
            RuntimeError: 如果 cryptography 库未安装
        """
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("加密功能需要 cryptography 库")

        key_path.parent.mkdir(parents=True, exist_ok=True)

        key = Fernet.generate_key()
        self._key = base64.urlsafe_b64decode(key)
        self._fernet = Fernet(key)

        with open(key_path, "wb") as f:
            f.write(key)

        # 设置密钥文件权限（跨平台安全处理）
        self._set_secure_file_permissions(key_path)

        logger.info(f"已生成新的加密密钥: {key_path}")

    def _set_secure_file_permissions(self, file_path: Path) -> None:
        """
        设置文件的安全权限（跨平台）
        
        在 Unix 系统上使用 chmod 设置 600 权限。
        在 Windows 系统上使用 ACL 限制访问权限。
        
        Args:
            file_path: 文件路径
        """
        system = platform.system()

        if system != "Windows":
            # Unix/Linux/Mac: 使用 chmod 设置权限
            try:
                os.chmod(file_path, 0o600)
                logger.debug(f"已设置文件权限 600: {file_path}")
            except PermissionError as e:
                logger.warning(
                    f"无法设置文件权限 {file_path}: {e}。"
                    "文件可能被其他用户读取。"
                )
            except OSError as e:
                logger.debug(f"设置文件权限失败: {e}")
        else:
            # Windows: 使用 ACL 设置权限
            self._set_windows_acl_permissions(file_path)

    def _set_windows_acl_permissions(self, file_path: Path) -> None:
        """
        在 Windows 上设置文件 ACL 权限
        
        限制文件只能被当前用户访问。
        
        Args:
            file_path: 文件路径
        """
        try:
            import win32api
            import win32con
            import win32security
        except ImportError:
            # pywin32 未安装，使用替代方法
            logger.debug("pywin32 未安装，使用基本权限设置")
            try:
                # 使用 Windows 的 attrib 命令设置隐藏属性
                import subprocess
                subprocess.run(
                    ["attrib", "+H", str(file_path)],
                    check=False,
                    capture_output=True,
                )
                logger.debug(f"已设置文件隐藏属性: {file_path}")
            except Exception as e:
                logger.debug(f"设置 Windows 文件属性失败: {e}")
            return

        try:
            # 获取当前用户
            username = win32api.GetUserName()
            domain = win32api.GetComputerName()

            # 创建安全描述符
            sd = win32security.SECURITY_DESCRIPTOR()

            # 创建 DACL（自由访问控制列表）
            dacl = win32security.ACL()

            # 获取当前用户的 SID
            sid, _, _ = win32security.LookupAccountName(domain, username)

            # 为当前用户添加完全控制权限
            dacl.AddAccessAllowedAce(
                win32security.ACL_REVISION,
                win32con.GENERIC_ALL,  # 完全控制
                sid,
            )

            # 设置 DACL
            sd.SetSecurityDescriptorDacl(1, dacl, 0)

            # 应用安全描述符到文件
            win32security.SetFileSecurity(
                str(file_path),
                win32security.DACL_SECURITY_INFORMATION,
                sd,
            )

            logger.debug(f"已设置 Windows ACL 权限: {file_path}")

        except Exception as e:
            logger.warning(f"设置 Windows ACL 权限失败: {e}")
            # 回退到基本方法
            try:
                import subprocess
                subprocess.run(
                    ["attrib", "+H", str(file_path)],
                    check=False,
                    capture_output=True,
                )
            except Exception:
                pass

    def encrypt(self, data: str | dict[str, Any]) -> str:
        """
        加密数据
        
        Args:
            data: 要加密的数据（字符串或字典）
            
        Returns:
            加密后的字符串（Base64 编码）
            
        Raises:
            RuntimeError: 如果加密器未正确初始化
        """
        if not self.config.enabled:
            if isinstance(data, dict):
                return json.dumps(data, ensure_ascii=False)
            return data

        if not self._fernet:
            raise RuntimeError("加密器未正确初始化")

        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False)

        data_bytes = data.encode("utf-8")
        encrypted = self._fernet.encrypt(data_bytes)
        return encrypted.decode("utf-8")

    def decrypt(self, encrypted_data: str) -> str:
        """
        解密数据
        
        Args:
            encrypted_data: 加密的数据
            
        Returns:
            解密后的字符串
            
        Raises:
            RuntimeError: 如果加密器未正确初始化
            ValueError: 如果解密失败
        """
        if not self.config.enabled:
            return encrypted_data

        if not self._fernet:
            raise RuntimeError("加密器未正确初始化")

        try:
            decrypted = self._fernet.decrypt(encrypted_data.encode("utf-8"))
            return decrypted.decode("utf-8")
        except InvalidToken:
            logger.error("解密失败: 无效的加密令牌")
            raise ValueError("解密失败: 数据可能已损坏或密钥不正确")

    def decrypt_to_dict(self, encrypted_data: str) -> dict[str, Any]:
        """
        解密数据为字典
        
        Args:
            encrypted_data: 加密的数据
            
        Returns:
            解密后的字典
        """
        decrypted = self.decrypt(encrypted_data)
        return json.loads(decrypted)

    def is_encrypted(self, data: str) -> bool:
        """
        检查数据是否已加密
        
        Args:
            data: 要检查的数据
            
        Returns:
            是否已加密
        """
        if not data:
            return False

        try:
            return data.startswith("gAAAAAB")
        except Exception:
            return False


class SecureSessionStorage:
    """
    安全会话存储
    
    提供会话数据的加密存储和读取功能
    """

    def __init__(
        self,
        storage_dir: Path,
        encryptor: SessionEncryptor | None = None,
    ):
        """
        初始化安全会话存储
        
        Args:
            storage_dir: 存储目录
            encryptor: 加密器实例
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.encryptor = encryptor or SessionEncryptor()

    def save(
        self,
        session_id: str,
        data: dict[str, Any],
        encrypt: bool = True,
    ) -> Path:
        """
        保存会话数据
        
        Args:
            session_id: 会话 ID
            data: 会话数据
            encrypt: 是否加密
            
        Returns:
            保存的文件路径
        """
        file_path = self.storage_dir / f"{session_id}.json"

        if encrypt and self.encryptor.config.enabled:
            encrypted_data = self.encryptor.encrypt(data)
            storage_data = {
                "encrypted": True,
                "data": encrypted_data,
                "version": 1,
            }
        else:
            storage_data = {
                "encrypted": False,
                "data": data,
                "version": 1,
            }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(storage_data, f, ensure_ascii=False, indent=2)

        # 设置会话文件权限（使用加密器的跨平台方法）
        if hasattr(self.encryptor, '_set_secure_file_permissions'):
            self.encryptor._set_secure_file_permissions(file_path)
        else:
            try:
                os.chmod(file_path, 0o600)
            except (PermissionError, OSError) as e:
                logger.debug(f"设置文件权限失败: {e}")

        logger.debug(f"会话数据已保存: {file_path}")
        return file_path

    def load(self, session_id: str) -> dict[str, Any] | None:
        """
        加载会话数据
        
        Args:
            session_id: 会话 ID
            
        Returns:
            会话数据，如果不存在则返回 None
        """
        file_path = self.storage_dir / f"{session_id}.json"

        if not file_path.exists():
            return None

        try:
            with open(file_path, encoding="utf-8") as f:
                storage_data = json.load(f)

            if storage_data.get("encrypted", False):
                encrypted_data = storage_data.get("data", "")
                return self.encryptor.decrypt_to_dict(encrypted_data)
            else:
                return storage_data.get("data", {})

        except Exception as e:
            logger.error(f"加载会话数据失败: {e}")
            return None

    def delete(self, session_id: str) -> bool:
        """
        删除会话数据
        
        Args:
            session_id: 会话 ID
            
        Returns:
            是否成功删除
        """
        file_path = self.storage_dir / f"{session_id}.json"

        if file_path.exists():
            file_path.unlink()
            logger.debug(f"会话数据已删除: {file_path}")
            return True

        return False

    def list_sessions(self) -> list[str]:
        """
        列出所有会话 ID
        
        Returns:
            会话 ID 列表
        """
        sessions = []
        for file_path in self.storage_dir.glob("*.json"):
            sessions.append(file_path.stem)
        return sorted(sessions)

    def cleanup_old_sessions(self, max_age_days: int = 30) -> int:
        """
        清理旧会话
        
        Args:
            max_age_days: 最大保留天数
            
        Returns:
            清理的会话数量
        """
        import time

        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 3600
        cleaned = 0

        for file_path in self.storage_dir.glob("*.json"):
            file_age = current_time - file_path.stat().st_mtime
            if file_age > max_age_seconds:
                file_path.unlink()
                cleaned += 1

        if cleaned > 0:
            logger.info(f"清理了 {cleaned} 个过期会话")

        return cleaned


_encryptor: SessionEncryptor | None = None


def get_session_encryptor() -> SessionEncryptor:
    """
    获取全局会话加密器实例
    
    Returns:
        SessionEncryptor 实例
    """
    global _encryptor
    if _encryptor is None:
        _encryptor = SessionEncryptor()
    return _encryptor


def set_session_encryptor(encryptor: SessionEncryptor) -> None:
    """
    设置全局会话加密器实例
    
    Args:
        encryptor: SessionEncryptor 实例
    """
    global _encryptor
    _encryptor = encryptor
