import webview
import pystray
from PIL import Image
import threading
import os
import json
import http.server
import socketserver
from functools import partial
import logging as lg
import tmlib
import datetime as dt

from backend import timeManagerBackend



class WebViewApp(object):
    def __init__(self,iconPath):
        #initialize
        
        if os.path.exists('./config.json'):
            try:
                self.config=json.load(open('./config.json'))
            except json.JSONDecodeError:
                self.config={}
        tmlib.initialize_folders(['data',
                                  'log'])

        self.window=None
        self.icon_path=iconPath
        self.logger_init()
        self.logger.info('Object Initializing...')
        pass


    def logger_init(self):
        """
        初始化日志系统
        
        创建日志目录，配置日志格式和输出方式，
        包括文件输出和控制台输出
        """
        self.logger = lg.getLogger(__name__)
        try:  # 创建日志目录
            os.makedirs("./log")
        except:
            pass
        
        # 清除已存在的处理器，避免重复日志
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 日志基础设置
        lg.basicConfig(
            filename="./log/" + str(dt.datetime.today().strftime("%Y-%m-%d")) + ".log",
            format="[%(asctime)s][%(levelname)s][%(name)s][%(funcName)s]%(message)s",
            level=lg.INFO,
            encoding="utf-8",
        )
        
        # 添加控制台输出
        console_handler = lg.StreamHandler()
        console_handler.setLevel(lg.INFO)
        formatter = lg.Formatter("[%(asctime)s][%(levelname)s][%(name)s][%(funcName)s]%(message)s")
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        self.logger.info("Started")

    def __init_backend(self):
        """启动HTTP服务器提供frontend目录内容"""

        # 检查frontend目录是否存在
        if not os.path.exists('frontend'):
            print("警告: frontend目录不存在")
            return False
            
        # 更改当前工作目录到frontend
        handler = partial(http.server.SimpleHTTPRequestHandler, directory='frontend')
        
        # 创建HTTP服务器
        try:
            self.httpd = socketserver.TCPServer(("localhost", 50000), handler)
            # 在单独线程中启动服务器
            server_thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
            server_thread.start()
            print("HTTP服务器已在localhost:50000上启动，提供frontend目录内容")
        except Exception as e:
            print(f"启动HTTP服务器失败: {e}")
        
        return True
    

    def create_window(self):
        self.logger.info('create window')
        self.window = webview.create_window(
            "Time Manager Py", 
            "http://localhost:50000", # URL 末尾空格已移除
            width=800, 
            height=600
        )
        self.window.events.closing += self.on_window_closing
        webview.start(debug=False)
        
        self.logger.info('started')

    def on_window_closing(self):
        """
        当主窗口关闭时被调用的处理函数。
        它隐藏窗口并创建系统托盘图标。
        返回 False 以阻止窗口真正关闭。
        """
        self.window.hide()
        # 返回 False 阻止 webview 窗口真正关闭
        return False


    def quit_app(self, icon_obj, item):
        self.logger.info("退出窗口")
        self.window.destroy()
        self.icon.stop()
        self.httpd.server_close()
        self.logger.info("已退出")
        self.backend.stop_()
        os._exit(0)


    def show_tray(self):
        # 创建系统托盘菜单

        def on_tray_icon_clicked():
            """
            当托盘图标被左键单击时调用此方法。
            """
            self.logger.info("左键单击托盘图标，显示窗口。")
            self.window.show()
        self.menu = pystray.Menu(
            pystray.MenuItem('显示 (Show)', on_tray_icon_clicked),
            pystray.MenuItem('退出 (Exit)', self.quit_app)
        )

        # 加载图标文件
        try:
            image = Image.open(self.icon_path)
        except FileNotFoundError:
            self.logger.info(f"警告: 图标文件 '{self.icon_path}' 未找到，使用默认蓝色方块图标。")
            # 如果找不到图标文件，则创建一个简单的蓝色图像
            image = Image.new('RGB', (64, 64), color='blue')

        # 创建并启动托盘图标
        self.icon = pystray.Icon(
            "timeManager", # 托盘图标名称
            image,
            "time manager", # 托盘图标提示文本
            self.menu,
            on_click=on_tray_icon_clicked
        )
        self.icon.run()


    def run(self):
        if not self.__init_backend():
            return False
        
        self.logger.info("初始化成功")
        self.backend=timeManagerBackend(self.logger,True,self.config['auto_save_query'],self.config['data_path'])
        self.logger.info("启动后端服务")
        
        #图标线程
        self.logger.info("启动图标")
        self.stray_thread=threading.Thread(target=self.show_tray)
        self.stray_thread.start()

        self.backend.start()

        #create_window 仅限主线程中
        self.logger.info("启动webview")
        self.create_window()


main_webview = WebViewApp('./icon.ico')

main_webview.run()