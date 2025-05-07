import shutil
import airsim
import threading
import os
import time
from PIL import Image
import io
import json


# 创建目录的函数
def create_directory(folder_name):
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)


# 获取第一视角图像并保存为JPG的函数
def capture_video(client, drone_name, folder_name, duration=10):
    create_directory(folder_name)
    start_time = time.time()

    while time.time() - start_time < duration:
        # 获取压缩的PNG图像
        responses = client.simGetImages([airsim.ImageRequest("0", airsim.ImageType.Scene, False, True)],
                                        vehicle_name=drone_name)
        response = responses[0]

        # 将图像数据转换为PIL Image对象
        img_data = response.image_data_uint8
        img = Image.open(io.BytesIO(img_data))

        # 如果图像是RGBA模式，转换为RGB模式
        if img.mode == 'RGBA':
            img = img.convert('RGB')

        # 生成文件名
        image_filename = os.path.join(folder_name, f"{drone_name}_{time.time():.6f}.jpg")

        # 将图像保存为JPG文件
        img.save(image_filename, format="JPEG")

        # 控制帧率
        time.sleep(0.1)


class Drone:
    def __init__(self, total_memory, current_memory_usage, cpu_frequency, x=0, y=0, z=-10, drone_name=""):
        self.total_memory = total_memory  # 内存总量
        self.current_memory_usage = current_memory_usage  # 当前内存使用量
        self.cpu_frequency = cpu_frequency  # CPU频率
        self.memory_usage_rate = (self.current_memory_usage / self.total_memory) * 100
        self.cpu_usage_rate = 0.0
        self.x = x
        self.y = y
        self.z = z
        self.drone_name = drone_name

    def get_memory_usage_rate(self):
        return self.memory_usage_rate

    def get_cpu_usage_rate(self):
        return self.cpu_usage_rate

    def move_to_position(self, client, new_x, new_y, speed=5, drone_name=""):
        self.x = new_x
        self.y = new_y
        client.moveToPositionAsync(self.x, self.y, self.z, speed, vehicle_name=drone_name).join()

    def generate_path(self):
        import random
        new_x = max(0, min(self.x + random.randint(-25, 25), 100))
        new_y = max(0, min(self.y + random.randint(-25, 25), 100))
        return new_x, new_y

    def task_computing(self, required_memory, total_cpu_clock, duration):
        if required_memory > self.total_memory - self.current_memory_usage:
            raise ValueError("Not enough memory to complete the task.")

        # 分配内存
        self.current_memory_usage += required_memory
        self.memory_usage_rate = (self.current_memory_usage / self.total_memory) * 100

        # 计算CPU使用率
        cpu_load_per_second = (total_cpu_clock / self.cpu_frequency) * 100 / duration
        start_time = time.time()

        print(
            f"Task started. Memory Usage Rate: {self.get_memory_usage_rate():.2f}%, CPU Usage Rate: {self.get_cpu_usage_rate():.2f}%")

        while time.time() - start_time < duration:
            # 模拟CPU计算工作负载
            for _ in range(10 ** 6):  # 这里可以根据需要调整工作负载
                pass

            elapsed_time = time.time() - start_time
            self.cpu_usage_rate = cpu_load_per_second * elapsed_time

        # 释放内存和CPU
        self.current_memory_usage -= required_memory
        self.memory_usage_rate = (self.current_memory_usage / self.total_memory) * 100
        self.cpu_usage_rate = 0.0

        print(
            f"Task completed. Memory Usage Rate: {self.get_memory_usage_rate():.2f}%, CPU Usage Rate: {self.get_cpu_usage_rate():.2f}%")

    def start_task(self, required_memory, total_cpu_clock, duration):
        thread1 = threading.Thread(target=self.task_computing, args=(required_memory, total_cpu_clock, duration))
        thread1.start()
        return thread1


# 无人机飞行路径的函数
def fly_drone(drone, client, drone_name, folder_name, duration, required_memory, total_cpu_clock):
    client.confirmConnection()
    client.enableApiControl(True, vehicle_name=drone_name)
    client.armDisarm(True, vehicle_name=drone_name)

    # 起飞
    client.takeoffAsync(vehicle_name=drone_name).join()

    # 飞行路径
    for _ in range(10):  # 假设执行10次路径生成和移动
        new_x, new_y = drone.generate_path()
        drone.move_to_position(client, new_x - drone.x, new_y - drone.y, )
        time.sleep(1)  # 等待一段时间再进行下一次移动

    # 开始捕获视频
    capture_video(client, drone_name, folder_name, duration)
    drone.start_task(required_memory, total_cpu_clock, duration)

    # 着陆
    client.landAsync(vehicle_name=drone_name).join()
    client.armDisarm(False, vehicle_name=drone_name)
    client.enableApiControl(False, vehicle_name=drone_name)


def init():
    with open('settings.json', 'r') as file:
        settings = json.load(file)
    vehicles = settings['Vehicles']
    num_drones = 100
    drone_names = [f'Drone{i + 1}' for i in range(num_drones)]
    folder_names = [f'Drone{i + 1}_Folder' for i in range(num_drones)]
    duration = 10  # 视频捕获时长

    drones = []

    # TODO(Dimo Zhang) : 在settings.json中加入相应的配置
    for i in range(num_drones):
        drone_name = drone_names[i]
        if drone_name in vehicles:
            x = vehicles[drone_name]['X']
            y = vehicles[drone_name]['Y']
            cpu_frequency = vehicles[drone_name]['CPU_FREQUENCY']
            current_memory_usage = vehicles[drone_name]['MEMORY_USAGE']
            total_memory = vehicles[drone_name]['MEMORY_USAGE']
            drone = Drone(total_memory=total_memory, current_memory_usage=current_memory_usage,
                          cpu_frequency=cpu_frequency, x=x, y=y, drone_name=drone_name)
            drones.append(drone)

    threads = []

    # 为每架无人机创建一个线程
    # TODO(Earl Zhu) : 任务相关参数还需要调整以适应变化
    for i in range(len(drone_names)):
        thread = threading.Thread(target=fly_drone,
                                  args=(
                                      drones[i], airsim.MultirotorClient(), drone_names[i], folder_names[i], duration,
                                      100,
                                      2500))
        threads.append(thread)
        thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    init()

# # 示例用法
# client = airsim.MultirotorClient()
# drones = [
#     Drone(total_memory=8, current_memory_usage=2, cpu_frequency=2.5, x=0, y=0),
#     Drone(total_memory=8, current_memory_usage=2, cpu_frequency=2.5, x=0, y=0),
#     Drone(total_memory=8, current_memory_usage=2, cpu_frequency=2.5, x=0, y=0)
# ]
#
# # 启动多个任务
# threads = []
# for i, drone in enumerate(drones):
#     folder_name = f"video_{i + 1}"
#     thread = threading.Thread(target=fly_drone, args=(drone, client, f'Drone{i + 1}', folder_name, 10))
#     threads.append(thread)
#     thread.start()
#
# # 等待所有任务完成
# for thread in threads:
#     thread.join()
#
# # 获取实时数据
# for i, drone in enumerate(drones):
#     print(f"Drone {i + 1}: Final Real-time Memory Usage Rate: {drone.get_memory_usage_rate():.2f}%")
#     print(f"Drone {i + 1}: Final Real-time CPU Usage Rate: {drone.get_cpu_usage_rate():.2f}%")
