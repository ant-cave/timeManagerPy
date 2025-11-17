import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import time

import tmlib


import threading

import logging as lg

import os
import datetime as dt





class timeManagerBackend():
    def __init__(self,logger:lg.Logger=None,auto_save=False,auto_save_query=0,data_path='./data'):



        self.auto_save_query=auto_save_query

        self.logger=logger
        self.data_path=data_path
        self.auto_save=auto_save

        if not self.logger:
            self.logger_init()
        self.app = FastAPI()
        # 添加CORS中间件以允许跨域请求
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.logger.info("backend initializing...")
        self.__setup_routes()
        self.stop = False


        if os.path.exists(self.data_path+'/'+ str(dt.datetime.today().strftime("%Y-%m-%d")) + ".json"):
            with open(self.data_path+'/'+ str(dt.datetime.today().strftime("%Y-%m-%d")) + ".json",'r',encoding='utf-8') as f:
                file_str=f.read()
            try:
                loaded_data = json.loads(file_str)
                # 转换旧数据格式到新格式
                self.main_data = {}
                for key, value in loaded_data.items():
                    if 'totalTime' in value and 'lastTime' in value:
                        # 已经是新格式，直接使用
                        self.main_data[key] = value
                    elif 'total_time' in value and 'last_time' in value:
                        # 旧格式，转换为新格式
                        self.main_data[key] = {
                            'totalTime': value['total_time'],
                            'lastTime': value['last_time']
                        }
                    else:
                        # 未知格式，使用默认值
                        self.main_data[key] = {'totalTime': 0, 'lastTime': 0.0}
            except:
                self.main_data = {}
        else:
            self.main_data = {}

        self.main_loop_thread = threading.Thread(target=self.main_loop,daemon=True)
        self.backend_thread=threading.Thread(target=self.run_backend,daemon=True)
        self.auto_save_thread=threading.Thread(target=self.auto_save_,daemon=True)
        

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
    def __setup_routes(self):
        # 路由
        @self.app.get("/")
        def home():
            return self.main_data

        @self.app.get("/get_week_data")
        def get_week_data():
            """获取过去7天（包括今天）的所有数据"""
            result = {}
            today = dt.datetime.today().date()
            
            # 计算过去7天的日期
            for i in range(7):
                date = today - dt.timedelta(days=i)
                date_str = date.strftime("%Y-%m-%d")
                date_int = int(date.strftime("%Y%m%d"))
                
                # 检查数据文件是否存在
                filename = f"{self.data_path}/{date_str}.json"
                if os.path.exists(filename):
                    try:
                        with open(filename, 'r', encoding='utf-8') as f:
                            data = json.loads(f.read())
                        result[date_int] = data
                    except Exception as e:
                        self.logger.error(f"读取文件 {filename} 时出错: {e}")
                        result[date_int] = {}
                else:
                    result[date_int] = {}
            
            return result

    def run_backend(self):
        uvicorn.run(self.app, host="127.0.0.1", port=25673)

    def start(self):
        self.main_loop_thread.start()
        if self.auto_save_query:
            self.auto_save_thread.start()

        self.logger.info("已启动 计时")

        self.backend_thread.start()

        self.logger.info("已启动 后端")



    def stop_(self):

        self.stop = True

    def main_loop(self):
        """
        主循环函数，用于监控当前活动窗口并记录各程序的运行时间
        
        该函数会持续运行直到self.stop被设置为True。它通过定期检查前台窗口的可执行文件路径，
        并累加对应程序的时间计数来实现时间跟踪功能。时间统计精度为0.1秒。
        """
        current_data = None
        last_check_time = time.time()
        current_date = dt.datetime.today().date()

        while True:
            # 检查是否需要停止主循环
            if self.stop:
                break

            # 每0.1秒检查一次前台窗口
            time.sleep(0.1)
            current_time = time.time()
            today = dt.datetime.today().date()
            
            # 检测日期变化
            if today != current_date:
                self._save_current_data(current_date)
                self._switch_to_new_date(today)
                current_date = today
            
            # 检测时间跳跃（睡眠/休眠导致）
            time_diff = current_time - last_check_time
            if time_diff > 1.0:
                # 时间跳跃，不累加时间，只更新lastTime
                if current_data:
                    current_data['lastTime'] = current_time
                last_check_time = current_time
                continue
                
            last_check_time = current_time
            
            info_data = tmlib.get_foreground_window_executable_info()
            if info_data:
                current_exe_path = info_data.exe_path

                # 尝试获取当前可执行文件路径对应的时间统计数据
                if current_exe_path not in self.main_data:
                    # 如果当前路径未在main_data中记录，则初始化记录
                    self.main_data[current_exe_path] = {'totalTime': 0, 'lastTime': 0.0}
                
                current_data = self.main_data[current_exe_path]

                # 累加当前程序的使用时间计数
                if 0<current_data['lastTime'] - int(current_data['lastTime']) < 0.1:
                    current_data['totalTime'] += 1
                current_data['lastTime'] = current_time

    def _save_current_data(self, date):
        """保存指定日期的数据"""
        if self.main_data:
            filename = f"{self.data_path}/{date.strftime('%Y-%m-%d')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json.dumps(self.main_data, indent=4, ensure_ascii=False))
            self.logger.info(f'跨天切换：已保存 {date.strftime("%Y-%m-%d")} 的数据')

    def _switch_to_new_date(self, new_date):
        """切换到新日期的数据文件"""
        filename = f"{self.data_path}/{new_date.strftime('%Y-%m-%d')}.json"
        
        # 加载新日期的数据（如果存在）
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                file_str = f.read()
            try:
                loaded_data = json.loads(file_str)
                # 使用与 __init__ 中相同的数据格式转换逻辑
                self.main_data = {}
                for key, value in loaded_data.items():
                    if 'totalTime' in value and 'lastTime' in value:
                        self.main_data[key] = value
                    elif 'total_time' in value and 'last_time' in value:
                        self.main_data[key] = {
                            'totalTime': value['total_time'],
                            'lastTime': value['last_time']
                        }
                    else:
                        self.main_data[key] = {'totalTime': 0, 'lastTime': 0.0}
            except:
                self.main_data = {}
        else:
            self.main_data = {}
        
        self.logger.info(f'跨天切换：已切换到 {new_date.strftime("%Y-%m-%d")} 的数据')

    def auto_save_(self):
        while 1:
            time.sleep(self.auto_save_query)
            if self.stop:
                break
            with open(self.data_path+'/'+ str(dt.datetime.today().strftime("%Y-%m-%d")) + ".json",'w+',encoding='utf-8') as f:
                f.write(json.dumps(self.main_data,indent=4,ensure_ascii=False))
            self.logger.info('saved data automatically.')


if __name__ == "__main__":
    backend = timeManagerBackend()
    backend.start()
