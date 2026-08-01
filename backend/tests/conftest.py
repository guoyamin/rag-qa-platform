"""
智能问答平台 - pytest 配置
"""

import sys
from pathlib import Path

# 将 backend 目录加入 Python 路径（app 包所在目录，使 `import app` 在容器内外均可用）
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))
