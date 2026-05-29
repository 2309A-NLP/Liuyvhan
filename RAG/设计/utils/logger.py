from __future__ import annotations
"""
logger.py 作用：创建一个既能在控制台显示，又能保存到文件的日志系统。
 程序运行时，既能实时在控制台看到运行信息，又能把信息保存到文件中供以后查看。
"""
import logging  # Python 标准日志库

from config import SETTINGS   #导入配置（获取日志文件路径）

"""
get_logger 相当于一个日志记录器
"""
def get_logger(name: str) -> logging.Logger: # 返回的类型 配置好的 Logger 对象
    logger = logging.getLogger(name) # 获取指定名称的日志器
    if logger.handlers:              # 判断日志是否已存在 if 判断如果日志器有输出工具 说明配置过了 直接返回
    # handlers 是logger对象的属性 他是一个列表 存储日志器的输出
        return logger

    logger.setLevel(logging.INFO) #  设置日志器只记录 INFO 级别及以上 的日志
    # 拓展：
    # logging.DEBUG     # 10 - 调试信息（最详细）
    # logging.INFO      # 20 - 常规信息 ← 你的设置
    # logging.WARNING   # 30 - 警告信息
    # logging.ERROR     # 40 - 错误信息
    # logging.CRITICAL  # 50 - 严重错误

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        # %(asctime)s -    时间          2024-01-15 10:30:45,123
        # %(levelname)s - 日志级别        INFO, ERROR, WARNING
        # %(name)s -      日志器名称      app, mysql_client
        # %(message)s     日志内容        服务器启动成功
        # 示例：2024-01-15 10:30:45,123 | INFO | app | 服务器启动成功
    )   # 定义日志的输出格式

    # 创建文件处理器  将日志写入文件
    file_handler = logging.FileHandler(SETTINGS.log_path, encoding="utf-8")
    #                                  日志文件路径            支持中文
    file_handler.setFormatter(formatter)
    #                    使用上面定义的格式
    logger.addHandler(file_handler)
    # 把文件处理器添加到日志器

    """
    创建控制台处理器
    将日志输出到控制台（屏幕）
    运行程序时，终端会实时显示日志
    """
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
