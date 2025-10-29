"""
简单的配置管理器
"""
import os
import yaml
from typing import Dict, Any

class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')

        self.config_path = config_path
        self._config = None

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        if self._config is None:
            self._load_config()
        return self._config

    def _load_config(self):
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            self._config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            'apis': {
                'binance': {
                    'api_key': '',
                    'api_secret': '',
                    'testnet': True
                },
                'deepseek': {
                    'api_key': '',
                    'base_url': 'https://api.deepseek.com'
                }
            },
            'trading': {
                'symbols': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']
            }
        }