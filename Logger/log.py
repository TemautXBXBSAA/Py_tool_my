import logging
import typing
import os,sys
import functools

class _SysExcInfoFormatter(logging.Formatter):
    def formatException(self, ei) -> str:
        tb_str = super().formatException(ei)

        border = "=" * 60
        formatted = f"{border}\n{tb_str}\n{border}"
        
        return formatted

class _ColorFormatter(logging.Formatter):
    COLOR = {
        'DEBUG': '\033[0m',
        'INFO': '\033[0;32m',
        'WARNING': '\033[1;33m',
        'ERROR': '\033[1;31m',
        'CRITICAL': '\033[1;35m'
    }
    END = '\033[0m'
    
    def format(self, record):
        super().format(record)
        astime = self.formatTime(record,"%Y-%m-%d %H:%M:%S")
        msg = f"{self.COLOR[record.levelname]}{astime} | {record.levelname:<8} | {record.name}:{record.lineno} -> {record.message}{self.END}"
        if record.exc_info:
            error=self.formatException(record.exc_info)
            msg = msg + '\n\n' + error + '\n'
        return msg
    
    def formatException(self, ei) -> str:
        color = self.COLOR["ERROR"]
        tb_str = super().formatException(ei)
        border = "=" * 60
        formatted = f"{color}{border}\n{tb_str}\n{border}{self.END}"
        
        return formatted

class Logger:
    '''
    Logger:
        Basced on logging module. Improved by color and exc_info.
        For a symple start, just use `logger = Logger()` to create a logger, and use `logger.info("message")` to log.
        You can remove defuault log handler by using `self.removeHandler(self.file_handler / self.stream_handler)` and using `self.addHandler(handler)` to use your own handler.
        If you want to DIY your own Logger, use self.logger.function to modify log style.

    Remember:
        If you want to use your own handler:
          Firstly, using `self.removeHandler(self.file_handler / self.stream_handler)` to remove the default handler.
          Secondly, using `self.addHandler(handler)` to add your own handler.
    '''
    def __init__(self,logger_name = __name__,save_path = "", encoding = "utf-8"):
        self.encoding = encoding
        self.logger = logging.getLogger(logger_name)
        if self.logger.handlers:
            return
        self.logger.setLevel(logging.WARNING)

        if save_path != "":
            if not os.path.exists(os.path.dirname(os.path.abspath(save_path))): 
                os.makedirs(os.path.dirname(os.path.abspath(save_path)))
        
            self.file_handler = logging.FileHandler(save_path,encoding=self.encoding)
            self.file_format = _SysExcInfoFormatter(
                fmt='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d -> %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S')

            self.file_handler.setFormatter(self.file_format)
            self.logger.addHandler(self.file_handler)

        self.stream_handler = logging.StreamHandler()
        if sys.stderr.isatty():
            self.stream_format = _ColorFormatter()
        else:
            self.stream_format = logging.Formatter(
                fmt='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d -> %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S')
        self.stream_handler.setFormatter(self.stream_format)
        self.logger.addHandler(self.stream_handler)
    
    def set_log_path(self,save_path,encoding = "utf-8"):
        '''
        set_log_path:
            Set log path for logger. if empty, FileHandler will be removed.
        
        :param save_path: Log path.
        '''
        self.encoding = encoding
        if save_path:
            if not os.path.exists(os.path.dirname(os.path.abspath(save_path))): 
                #I think it's bettter to not use try...except. Just let developer know what's wrong.
                os.makedirs(os.path.dirname(os.path.abspath(save_path)))

            if hasattr(self, 'file_handler') and self.file_handler in self.logger.handlers:
                self.logger.removeHandler(self.file_handler)
                self.file_handler.close()

            self.file_handler = logging.FileHandler(save_path,encoding=self.encoding)
            self.file_format = _SysExcInfoFormatter(
                fmt='%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d -> %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S')
            self.file_handler.setFormatter(self.file_format)
            self.logger.addHandler(self.file_handler)
        else:
            if hasattr(self, 'file_handler') and self.file_handler in self.logger.handlers:
                self.logger.removeHandler(self.file_handler)
                self.file_handler.close()
            else:
                print("[-] FileHandler is not exist.")
    def addHandler(self,handler):
        self.logger.addHandler(handler)
    def removeHandler(self,handler):
        self.logger.removeHandler(handler)
    def addFilter(self,filter_):
        self.logger.addFilter(filter_)
    def removeFilter(self,filter_):
        self.logger.removeFilter(filter_)
    def setLevel(self,level):
        self.logger.setLevel(level)
    def info(self, msg, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)
    def debug(self, msg, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)
    def warning(self, msg, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)
    def error(self, msg, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)
    def critical(self, msg, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)
    def log(self,level,msg, *args, **kwargs):
        self.logger.log(level,msg, *args, **kwargs)
    def exception(self, msg, *args, **kwargs):
        self.logger.exception(msg, *args, **kwargs)
    def isEnabledFor(self,level):
        return self.logger.isEnabledFor(level)

auto_logger = Logger()
def add_auto_log(func:typing.Callable):
    '''
    add_auto_log: 
        This is a decorator, will add log for function automatically.
        The Logger is auto created in the module, name `model.auto_logger`, defult log level is `logging.WARNING`.
        If you want to change log leavel, before using this decorator, use `modle.auto_logger.setLevel(level)` to change log level.
        If you want to add/change log path, before using this decorator, use `modle.auto_logger.set_log_path(path)` to change log path.
        But if you want to use your own logger, you can use `modle.auto_logger = YourOwnLogger` to overwrite the auto logger.

    '''
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        auto_logger.info(f"'{func.__name__}' is called.")
        try:
            result = func(*args, **kwargs)
            auto_logger.info(f"'{func.__name__}' is done.")
        except Exception as e:
            auto_logger.exception(f"'{func.__name__}': An error occurred.")
            raise
        return result
    return wrapper

def main():

    import logging
    import os
    import sys
    import tempfile
    from io import StringIO
    from contextlib import redirect_stdout, redirect_stderr

    """执行所有功能测试，使用 ./exam 目录存储日志文件"""
    print("=" * 70)
    print("开始执行 Logger 模块全面测试（使用 ./exam 目录）")
    print("=" * 70)

    # 使用项目根目录下的 exam 文件夹（自动创建）
    exam_dir = os.path.join(os.getcwd(), "exam")
    os.makedirs(exam_dir, exist_ok=True)
    print(f"\n📁 日志将保存到目录: {exam_dir}")

    log_path1 = os.path.join(exam_dir, "test1.log")
    log_path2 = os.path.join(exam_dir, "test2.log")
    exception_log = os.path.join(exam_dir, "exception.log")
    decorator_log = os.path.join(exam_dir, "decorator.log")

    # ===== 测试1: 基础日志功能 =====
    print("\n" + "-" * 50)
    print("🧪 测试1: 基础日志功能 (控制台+文件)")
    print("-" * 50)
    logger1 = Logger("test1", log_path1)
    logger1.setLevel(logging.DEBUG)

    logger1.debug("调试信息")
    logger1.info("普通信息")
    logger1.warning("警告信息")
    logger1.error("错误信息")
    logger1.critical("严重错误")

    print(f"\n📄 日志已写入: {log_path1}")

    # ===== 测试2: 动态修改日志路径 =====
    print("\n" + "-" * 50)
    print("🧪 测试2: 动态修改日志路径")
    print("-" * 50)
    logger1.set_log_path(log_path2)
    logger1.info("路径切换后的新日志")
    logger1.warning("另一条新路径日志")

    print(f"\n📄 新日志已写入: {log_path2}")

    # ===== 测试3: 移除文件日志 =====
    print("\n" + "-" * 50)
    print("🧪 测试3: 移除文件日志")
    print("-" * 50)
    try:
        logger1.set_log_path("")  # 移除文件处理器
        logger1.error("仅输出到控制台（无文件）")
        print("✅ 成功移除了文件日志处理器")
    except ValueError as e:
        print(f"⚠️  注意：{e}")

    # ===== 测试4: 异常格式 =====
    print("\n" + "-" * 50)
    print("🧪 测试4: 异常处理格式")
    print("-" * 50)
    logger_ex = Logger("exception_test", exception_log)

    try:
        raise RuntimeError("这是一个测试异常")
    except Exception:
        logger_ex.exception("捕获到异常并记录")

    print(f"\n📄 异常日志已写入: {exception_log}")

    # ===== 测试5: @add_auto_log 装饰器 =====
    print("\n" + "-" * 50)
    print("🧪 测试5: @add_auto_log 装饰器")
    print("-" * 50)

    # 重置 auto_logger 并指定日志文件
    global auto_logger
    auto_logger = Logger("decorator_test", decorator_log)
    auto_logger.setLevel(logging.INFO)

    @add_auto_log
    def add_numbers(a, b):
        return a + b

    @add_auto_log
    def fail_on_purpose():
        raise ValueError("装饰器异常测试")

    # 正常调用
    result = add_numbers(10, 20)
    print(f"✅ add_numbers 返回: {result}")

    # 异常调用
    try:
        fail_on_purpose()
    except ValueError:
        print("✅ 捕获到装饰器抛出的异常")

    print(f"\n📄 装饰器日志已写入: {decorator_log}")

    # ===== 测试6: 非TTY环境（无颜色）=====
    print("\n" + "-" * 50)
    print("🧪 测试6: 非TTY环境（模拟无颜色输出）")
    print("-" * 50)

    # 临时禁用 TTY
    original_isatty = sys.stderr.isatty
    sys.stderr.isatty = lambda: False

    output_buffer = StringIO()
    logger6 = Logger("non_tty_test")

    with redirect_stderr(output_buffer):
        logger6.warning("非TTY警告消息")

    sys.stderr.isatty = original_isatty  # 恢复

    output_text = output_buffer.getvalue()
    print(f"📝 非TTY输出内容: {output_text.strip()}")
    if '\033[' in output_text:
        print("❌ 错误：非TTY环境中仍包含 ANSI 颜色代码")
    else:
        print("✅ 非TTY环境中无颜色代码")

    # ===== 测试7: 高级 API =====
    print("\n" + "-" * 50)
    print("🧪 测试7: 高级 API（addHandler 等）")
    print("-" * 50)

    logger7 = Logger("advanced_test")
    logger7.setLevel(logging.DEBUG)
    logger7.debug("此消息是由原始日志处理器输出的")
    stream = StringIO()
    custom_handler = logging.StreamHandler(stream)
    custom_handler.setFormatter(logging.Formatter("CUSTOM: %(message)s"))
    logger7.removeHandler(logger7.stream_handler)
    logger7.addHandler(custom_handler)

    logger7.debug("通过自定义处理器输出")
    logger7.removeHandler(custom_handler)
    logger7.warning("此消息不应出现在自定义处理器中")

    custom_output = stream.getvalue()
    print(f"📤 自定义处理器捕获: {custom_output.strip()}")
    if "此消息不应" not in custom_output:
        print("✅ 自定义处理器正确移除")
    else:
        print("❌ 自定义处理器未正确移除")

    print("\n" + "=" * 70)
    print("🎉 所有测试完成！请检查 ./exam 目录中的日志文件")
    print("=" * 70)

if __name__ == "__main__":
    main()
