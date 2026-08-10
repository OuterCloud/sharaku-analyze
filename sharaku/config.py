"""路径和配置"""

import os
from os.path import abspath, dirname, join


class Path:
    """路径配置类"""

    sharaku_dir = dirname(abspath(__file__))
    root_dir = dirname(sharaku_dir)
    static_dir = join(root_dir, "static")
    data_dir = join(root_dir, "data")

    @classmethod
    def knowledge_dir(cls) -> str:
        """知识库目录（支持通过 KNOWLEDGE_DIR 环境变量覆盖，可为绝对路径）"""
        configured = os.getenv("KNOWLEDGE_DIR", "knowledge")
        if os.path.isabs(configured):
            return configured
        return join(cls.root_dir, configured)
