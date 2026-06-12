"""路径和配置"""

from os.path import abspath, dirname, join


class Path:
    """路径配置类"""

    sharaku_dir = dirname(abspath(__file__))
    root_dir = dirname(sharaku_dir)
    static_dir = join(root_dir, "static")
    data_dir = join(root_dir, "data")
